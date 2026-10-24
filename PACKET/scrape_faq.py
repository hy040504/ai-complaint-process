"""청주톡톡 자주 묻는 민원을 수집해 분야별 JSON 파일로 저장합니다."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.cookiejar import CookieJar
import json
import re
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

from department_normalization import normalize_faq_detail


BASE_URL = "https://toktalk.cheongju.go.kr/home/sub.do"
MENU_KEY = "7403"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "db" / "자주_묻는_민원.json"
FIELDS = {
    "경제투자": "invest",
    "교통": "transport",
    "농업정책": "farming",
    "도로": "road",
    "도시부동산": "cityRealty",
    "문화체육관광": "MCST",
    "보건소": "PHC",
    "복지교육": "WE",
    "세무": "tax",
    "수도사업": "WaterSupply",
    "차량등록": "CarRegister",
    "행정지원": "AS",
    "환경": "Environment",
    "기타": "etc",
}
DETAIL_FIELDS = {
    "주요내용": "main_content",
    "접수처": "received_by",
    "대상자": "target",
    "처리기간": "processing_period",
    "주의사항": "warnings",
}
HTTP = build_opener(HTTPCookieProcessor(CookieJar()))


@dataclass
class TableRow:
    """HTML 표에서 추출한 한 행을 저장합니다.

    Attributes:
        cells: 표 셀의 텍스트 목록입니다.
        links: 표 안의 링크 주소 목록입니다.
    """

    cells: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)


class TableParser(HTMLParser):
    """외부 라이브러리 없이 HTML 표의 셀과 링크를 추출합니다."""

    def __init__(self, *, preserve_lines: bool = False) -> None:
        """HTML 파서와 행·셀 임시 저장 공간을 초기화합니다."""
        super().__init__(convert_charrefs=True)
        self.rows: list[TableRow] = []
        self._row: TableRow | None = None
        self._cell_parts: list[str] | None = None
        self._in_anchor = False
        self._anchor_href = ""
        self._preserve_lines = preserve_lines

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """HTML 시작 태그에 따라 행, 셀, 링크를 기록합니다.

        Args:
            tag: HTML 태그 이름입니다.
            attrs: 태그에 지정된 속성 목록입니다.
        """
        attributes = dict(attrs)
        if tag == "tr":
            self._row = TableRow()
        elif tag in ("td", "th") and self._row is not None:
            self._cell_parts = []
        elif tag == "a" and self._row is not None:
            self._in_anchor = True
            self._anchor_href = attributes.get("href") or ""
        elif tag == "br" and self._cell_parts is not None:
            self._cell_parts.append("\n")
        elif tag in ("p", "li", "div") and self._cell_parts is not None and self._preserve_lines:
            self._cell_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """HTML 종료 태그를 만나면 셀이나 행을 완성합니다.

        Args:
            tag: HTML 태그 이름입니다.
        """
        if tag in ("td", "th") and self._row is not None and self._cell_parts is not None:
            value = clean_text("".join(self._cell_parts), preserve_lines=self._preserve_lines)
            self._row.cells.append(value)
            self._cell_parts = None
        elif tag == "a" and self._row is not None and self._in_anchor:
            if self._anchor_href:
                self._row.links.append(self._anchor_href)
            self._in_anchor = False
            self._anchor_href = ""
        elif tag == "tr" and self._row is not None:
            if self._row.cells:
                self.rows.append(self._row)
            self._row = None
            self._cell_parts = None
        elif tag in ("p", "li", "div") and self._cell_parts is not None and self._preserve_lines:
            self._cell_parts.append("\n")

    def handle_data(self, data: str) -> None:
        """현재 셀에 텍스트를 추가합니다.

        Args:
            data: HTML에서 추출한 텍스트 조각입니다.
        """
        if self._cell_parts is not None:
            self._cell_parts.append(data)


def clean_text(value: str, *, preserve_lines: bool = False) -> str:
    """HTML 텍스트의 공백 및 보이지 않는 문자를 정리합니다.

    Args:
        value: 정리할 원본 문자열입니다.

    Returns:
        불필요한 공백을 정리한 문자열입니다.
    """
    value = value.replace("\xa0", " ").replace("\u200b", "").replace("\ufeff", "")
    if preserve_lines:
        lines = (re.sub(r"[^\S\n]+", " ", line).strip() for line in value.splitlines())
        return "\n".join(line for line in lines if line)
    return re.sub(r"\s+", " ", value).strip()


def parse_rows(document: str, *, preserve_lines: bool = False) -> list[TableRow]:
    """HTML 문서에서 표 행을 추출합니다.

    Args:
        document: 표가 포함된 HTML 문서입니다.

    Returns:
        셀 텍스트와 링크를 담은 표 행 목록입니다.
    """
    parser = TableParser(preserve_lines=preserve_lines)
    parser.feed(document)
    return parser.rows


def list_records(document: str) -> list[dict[str, object]]:
    """자주 묻는 민원 목록과 상세 페이지 주소를 추출합니다.

    Args:
        document: 민원 목록 HTML 문서입니다.

    Returns:
        번호, 분류, 제목, 상세 주소를 담은 항목 목록입니다.

    Raises:
        ValueError: 목록 항목의 상세 페이지 링크가 없는 경우 발생합니다.
    """
    records = []
    for row in parse_rows(document):
        if len(row.cells) < 5 or not row.cells[0].isdigit():
            continue
        detail_url = next(
            (link for link in row.links if "no=" in link and "mode=view" in link),
            "",
        )
        query = parse_qs(urlparse(detail_url).query)
        no = query.get("no", [""])[0]
        if not no:
            raise ValueError(f"목록 항목의 상세 링크를 찾을 수 없습니다: {row.cells[4]}")
        records.append(
            {
                "id": int(row.cells[0]),
                "major": row.cells[1],
                "medium": row.cells[2],
                "minor": row.cells[3],
                "title": row.cells[4],
                "_detail_no": no,
                "_detail_url": detail_url,
            }
        )
    return records


def parse_detail(document: str) -> tuple[dict[str, str], str | None]:
    """상세 페이지에서 주요 내용과 민원 안내 항목을 추출합니다.

    Args:
        document: 민원 상세 HTML 문서입니다.

    Returns:
        주요 내용, 접수처, 대상자, 처리기간, 주의사항을 담은 딕셔너리입니다.
    """
    values = {key: "" for key in DETAIL_FIELDS.values()}
    rows = parse_rows(document, preserve_lines=True)
    registered_date = None
    table_content = []
    metadata_labels = {
        "등록일",
        "조회",
        "대분류",
        "중분류",
        "소분류",
        "다음글",
        "이전글",
        *DETAIL_FIELDS.keys(),
    }
    for row in rows:
        if len(row.cells) < 2:
            continue
        field_name = DETAIL_FIELDS.get(row.cells[0])
        if field_name:
            values[field_name] = row.cells[1]
        elif row.cells[0] == "등록일":
            registered_date = row.cells[1] or None
        elif row.cells[0] not in metadata_labels:
            table_content.append(" | ".join(row.cells))
    if not values["main_content"] and table_content:
        values["main_content"] = "\n".join(table_content)
    normalize_faq_detail(values)
    return values, registered_date


def request_html(
    url: str,
    timeout: float,
    *,
    ajax: bool = False,
    referer: str | None = None,
    retries: int = 3,
) -> str:
    """사이트에 GET 요청을 보내고 HTML 응답을 반환합니다.

    Args:
        url: 요청할 전체 주소입니다.
        timeout: 요청별 제한 시간(초)입니다.
        ajax: 페이지 이동을 위한 AJAX 헤더가 필요한지 나타냅니다.
        referer: 요청 출처로 보낼 주소입니다.
        retries: 일시적 네트워크 오류 시 추가 재시도 횟수입니다.

    Returns:
        서버 응답을 문자로 디코딩한 HTML입니다.

    Raises:
        RuntimeError: 재시도 후에도 요청이 실패한 경우 발생합니다.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CheongjuFAQDataset/1.0)",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
        "Referer": referer or BASE_URL + "?menukey=" + MENU_KEY,
    }
    if ajax:
        headers["X-Requested-With"] = "XMLHttpRequest"
    for attempt in range(retries + 1):
        request = Request(url, headers=headers)
        try:
            with HTTP.open(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == retries:
                raise RuntimeError(f"페이지 요청에 실패했습니다 ({url}): {exc}") from exc
            retry_after = exc.headers.get("Retry-After")
            try:
                wait = min(float(retry_after), 60.0) if retry_after else 2**attempt
            except ValueError:
                wait = 2**attempt
            time.sleep(wait)
        except (URLError, TimeoutError) as exc:
            if attempt == retries:
                raise RuntimeError(f"페이지 요청에 실패했습니다 ({url}): {exc}") from exc
            time.sleep(2**attempt)

    raise RuntimeError(f"페이지 요청 재시도 횟수를 초과했습니다 ({url})")


def make_url(**params: str) -> str:
    """자주 묻는 민원 메뉴에 사용할 요청 주소를 만듭니다.

    Args:
        **params: URL에 추가할 조회 조건입니다.

    Returns:
        메뉴 키와 조회 조건이 포함된 요청 주소입니다.
    """
    return BASE_URL + "?" + urlencode({"menukey": MENU_KEY, **params})


def collect(output: Path, delay: float, timeout: float) -> dict[str, list[dict[str, object]]]:
    """모든 목록 페이지와 상세 페이지를 수집해 JSON 파일로 저장합니다.

    Args:
        output: 결과 JSON 파일을 저장할 경로입니다.
        delay: 상세 요청 사이에 둘 대기 시간(초)입니다.
        timeout: 각 HTTP 요청의 제한 시간(초)입니다.

    Returns:
        분야 코드별 민원 항목을 담은 데이터입니다.

    Raises:
        RuntimeError: 목록 조회 또는 상세 페이지 요청에 실패한 경우 발생합니다.
        ValueError: 사이트에서 지원하지 않는 분야가 발견된 경우 발생합니다.
    """
    dataset: dict[str, list[dict[str, object]]] = {field: [] for field in FIELDS.values()}
    seen_source_ids: set[str] = set()
    page = 1

    while True:
        params = {"mode": "list"}
        if page > 1:
            params["page"] = str(page)
        listing_url = make_url(**params)
        document = request_html(
            listing_url,
            timeout,
            ajax=page > 1,
            referer=make_url(mode="list") if page > 1 else None,
        )
        page_records = list_records(document)
        if not page_records:
            if page == 1:
                raise RuntimeError("목록에서 항목을 찾지 못했습니다. 페이지 구조를 확인하세요.")
            break

        for record in page_records:
            source_id = str(record["_detail_no"])
            if source_id in seen_source_ids:
                raise RuntimeError(f"목록에 동일한 상세 게시물이 다시 나타났습니다: {source_id}")
            seen_source_ids.add(source_id)
        print(f"[목록] {page}페이지: {len(page_records)}건")

        for record in page_records:
            category = str(record["major"])
            if category == "시정일반":
                continue
            output_field = FIELDS.get(category)
            if output_field is None:
                raise ValueError(f"요청한 분야 목록에 없는 대분류입니다: {category}")

            record.pop("_detail_url")
            record["source_id"] = str(record.pop("_detail_no"))
            detail_url = make_url(mode="view", no=str(record["source_id"]))
            detail, registered_date = parse_detail(
                request_html(detail_url, timeout, referer=listing_url)
            )
            record["source_url"] = detail_url
            record["registered_date"] = registered_date
            record["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            record["detail"] = detail
            dataset[output_field].append(record)
            print(f"  [상세] {record['id']}")
            if delay:
                time.sleep(delay)
        page += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if output.exists():
        temporary.chmod(output.stat().st_mode & 0o777)
    temporary.replace(output)
    print(f"[완료] {len(seen_source_ids)}건 목록 확인, 파일 저장: {output}")
    return dataset


def main() -> None:
    """명령줄 옵션을 확인하고 전체 데이터 수집을 시작합니다."""
    parser = argparse.ArgumentParser(
        description="청주톡톡 자주 묻는 민원 목록과 상세 내용을 JSON으로 저장합니다."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="저장할 JSON 파일 경로 (기본값: db/자주_묻는_민원.json)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="상세 요청 사이 대기 시간(초, 기본값: 0.5)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="각 HTTP 요청 타임아웃(초, 기본값: 20)",
    )
    args = parser.parse_args()
    if args.delay < 0 or args.timeout <= 0:
        parser.error("--delay는 0 이상, --timeout은 0보다 커야 합니다.")
    collect(args.output, args.delay, args.timeout)


if __name__ == "__main__":
    main()

"""청주톡톡 공개 민원사례를 수집해 JSON 배열 파일로 저장합니다."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from scrape_faq import BASE_URL, parse_rows, request_html
from department_normalization import normalize_public_record


MENU_KEY = "7401"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent / "rag" / "origin" / "공개_민원_사례.json"
)
DETAIL_FIELDS = {
    "민원신청일": "complaint_date",
    "민원요지": "summary",
    "담당부서": "department",
    "민원답변결과": "resolution",
}


def save_records(output: Path, records: list[dict[str, object]]) -> None:
    """확인된 부서명 표기를 통일하고 수집 결과를 UTF-8 JSON으로 저장합니다.

    Args:
        output: JSON 파일을 저장할 경로입니다.
        records: 지금까지 수집한 민원사례 목록입니다.

    Raises:
        OSError: 임시 파일 생성 또는 결과 파일 교체에 실패한 경우 발생합니다.
    """
    for record in records:
        normalize_public_record(record)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if output.exists():
        temporary.chmod(output.stat().st_mode & 0o777)
    for attempt in range(6):
        try:
            temporary.replace(output)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.2 * (attempt + 1))


def make_url(**params: str) -> str:
    """공개 민원사례 메뉴에 사용할 요청 주소를 만듭니다.

    Args:
        **params: URL에 추가할 조회 조건입니다.

    Returns:
        메뉴 키와 조회 조건이 포함된 요청 주소입니다.
    """
    return BASE_URL + "?" + urlencode({"menukey": MENU_KEY, **params})


def list_records(document: str) -> list[dict[str, object]]:
    """민원 목록에서 번호, 제목, 신청일, 상세 페이지 주소를 추출합니다.

    Args:
        document: 공개 민원사례 목록 HTML입니다.

    Returns:
        목록에서 찾은 민원사례 정보입니다.

    Raises:
        ValueError: 목록 항목에 상세 페이지 링크가 없는 경우 발생합니다.
    """
    records = []
    for row in parse_rows(document):
        if len(row.cells) < 3 or not row.cells[0].isdigit():
            continue
        detail_url = next(
            (link for link in row.links if "no=" in link and "mode=view" in link),
            "",
        )
        no = parse_qs(urlparse(detail_url).query).get("no", [""])[0]
        if not no:
            raise ValueError(f"목록 항목의 상세 링크를 찾을 수 없습니다: {row.cells[1]}")
        records.append(
            {
                "id": int(row.cells[0]),
                "title": row.cells[1],
                "complaint_date": row.cells[2],
                "_detail_no": no,
                "_detail_url": detail_url,
            }
        )
    return records


def parse_detail(document: str) -> dict[str, str]:
    """민원 상세 페이지에서 신청일, 요지, 담당부서, 답변을 추출합니다.

    Args:
        document: 공개 민원사례 상세 HTML입니다.

    Returns:
        요청한 상세 항목 네 개를 담은 딕셔너리입니다.
    """
    values = {field: "" for field in DETAIL_FIELDS.values()}
    for row in parse_rows(document):
        if len(row.cells) < 2:
            continue
        field = DETAIL_FIELDS.get(row.cells[0])
        if field:
            values[field] = row.cells[1]
    values["department_original"] = values["department"]
    return values


def fetch_detail(
    record: dict[str, object],
    listing_url: str,
    timeout: float,
) -> dict[str, str]:
    """한 민원사례의 상세 페이지를 요청하고 항목을 추출합니다.

    Args:
        record: 상세 페이지 번호를 포함한 목록 항목입니다.
        listing_url: 상세 요청의 Referer로 사용할 목록 주소입니다.
        timeout: HTTP 요청 제한 시간(초)입니다.

    Returns:
        신청일·요지·담당부서·답변·원래 부서명·출처·수집 시각입니다.

    Raises:
        RuntimeError: 재시도 후에도 상세 페이지 요청이 실패한 경우 발생합니다.
        ValueError: 상세 페이지에서 신청일을 찾지 못한 경우 발생합니다.
    """
    detail_url = make_url(mode="view", no=str(record["_detail_no"]))
    detail = parse_detail(
        request_html(detail_url, timeout, referer=listing_url)
    )
    if not detail["complaint_date"]:
        raise ValueError(f"민원 상세에서 신청일을 찾지 못했습니다: {detail_url}")
    detail["source_url"] = detail_url
    detail["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return detail


def collect(
    output: Path,
    delay: float,
    timeout: float,
    *,
    refresh_all: bool = False,
    workers: int = 4,
) -> list[dict[str, object]]:
    """전체 목록을 순회하고 새 항목 또는 모든 항목의 상세를 수집합니다.

    수집 중에는 체크포인트 파일에 저장하고, 완료된 결과만 원본 파일로 교체합니다.

    Args:
        output: 결과 JSON 파일을 저장할 경로입니다.
        delay: 상세 요청 시작 사이에 둘 대기 시간(초)입니다.
        timeout: 각 HTTP 요청의 제한 시간(초)입니다.
        refresh_all: 기존 민원도 모두 다시 요청할지 나타냅니다.
        workers: 동시에 요청할 상세 페이지의 최대 개수입니다.

    Returns:
        수집한 민원사례 목록입니다.

    Raises:
        RuntimeError: 목록 조회, 결과 파일 검증 또는 페이지 이동에 실패한 경우 발생합니다.
    """
    existing_by_source_id: dict[str, dict[str, object]] = {}
    if output.exists():
        try:
            previous_records = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"기존 결과 파일을 읽을 수 없습니다 ({output}): {exc}") from exc
        if not isinstance(previous_records, list):
            raise RuntimeError(f"기존 결과 파일의 최상위 값은 배열이어야 합니다: {output}")
        required_fields = {"id", "title", "complaint_date", *DETAIL_FIELDS.values()}
        display_ids: set[int] = set()
        for record in previous_records:
            if not isinstance(record, dict) or not required_fields.issubset(record):
                raise RuntimeError(f"기존 결과 파일에 예상하지 못한 항목이 있습니다: {output}")
            if not isinstance(record["id"], int) or record["id"] in display_ids:
                raise RuntimeError(f"기존 결과 파일에 중복되거나 잘못된 ID가 있습니다: {output}")
            display_ids.add(record["id"])
            source_id = str(record.get("source_id") or "")
            if not source_id and record.get("source_url"):
                source_id = parse_qs(urlparse(str(record["source_url"])).query).get("no", [""])[0]
            if source_id:
                if source_id in existing_by_source_id:
                    raise RuntimeError(f"기존 결과 파일에 중복된 source_id가 있습니다: {source_id}")
                record["source_id"] = source_id
                existing_by_source_id[source_id] = record
        print(f"[기존] {len(previous_records)}건, 고정 source_id {len(existing_by_source_id)}건 확인", flush=True)
        if len(existing_by_source_id) != len(previous_records):
            refresh_all = True
            print("[갱신] 고정 source_id가 없는 기존 데이터는 전건 다시 수집합니다.", flush=True)

    checkpoint = output.with_name(output.name + ".partial")
    records_by_source_id = {} if refresh_all else existing_by_source_id.copy()
    if checkpoint.exists():
        try:
            cached = json.loads(checkpoint.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"중간 저장 파일을 읽을 수 없습니다 ({checkpoint}): {exc}") from exc
        if not isinstance(cached, list):
            raise RuntimeError(f"중간 저장 파일은 배열이어야 합니다: {checkpoint}")
        for record in cached:
            if not isinstance(record, dict) or not isinstance(record.get("id"), int):
                raise RuntimeError(f"중간 저장 파일에 잘못된 항목이 있습니다: {checkpoint}")
            source_id = str(record.get("source_id") or "")
            if not source_id and record.get("source_url"):
                source_id = parse_qs(urlparse(str(record["source_url"])).query).get("no", [""])[0]
            if not source_id:
                raise RuntimeError(f"중간 저장 항목에 source_id가 없습니다: {record['id']}")
            record["source_id"] = source_id
            records_by_source_id[source_id] = record
        print(f"[재개] 중간 저장 데이터 {len(cached)}건을 확인했습니다.", flush=True)

    page = 1
    previous_listing_url = make_url()
    page_signatures: set[tuple[int, ...]] = set()
    listed_source_ids: set[str] = set()

    while True:
        params = {"mode": "list", "page": str(page)} if page > 1 else {}
        listing_url = make_url(**params)
        document = request_html(
            listing_url,
            timeout,
            ajax=page > 1,
            referer=previous_listing_url if page > 1 else None,
        )
        page_records = list_records(document)
        if not page_records:
            if page == 1:
                raise RuntimeError("목록에서 항목을 찾지 못했습니다. 페이지 구조를 확인하세요.")
            break

        signature = tuple(int(record["id"]) for record in page_records)
        if signature in page_signatures:
            raise RuntimeError(
                f"{page}페이지에서 이전 페이지와 같은 항목이 반환되었습니다. "
                "페이지 이동이 되지 않아 수집을 중단합니다."
            )
        page_signatures.add(signature)
        pending_records = []
        for record in page_records:
            source_id = str(record["_detail_no"])
            if source_id in listed_source_ids:
                raise RuntimeError(f"목록에 동일한 상세 게시물이 다시 나타났습니다: {source_id}")
            listed_source_ids.add(source_id)
            record["source_id"] = source_id
            existing = records_by_source_id.get(source_id)
            detail_url = make_url(mode="view", no=source_id)
            if existing is not None:
                existing["source_url"] = detail_url
                existing["id"] = record["id"]
                existing["title"] = record["title"]
                existing["complaint_date"] = record["complaint_date"]
            if existing is None or "retrieved_at" not in existing or "source_url" not in existing:
                pending_records.append(record)
        print(
            f"[목록] {page}페이지: {len(page_records)}건, 상세 요청 {len(pending_records)}건",
            flush=True,
        )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            pending = []
            for record in pending_records:
                pending.append(
                    (
                        record,
                        executor.submit(fetch_detail, record, listing_url, timeout),
                    )
                )
                if delay:
                    time.sleep(delay)
            for record, future in pending:
                record.update(future.result())
                record.pop("_detail_url")
                record.pop("_detail_no")
                records_by_source_id[str(record["source_id"])] = record
        if page % 5 == 0:
            save_records(checkpoint, list(records_by_source_id.values()))
        previous_listing_url = listing_url
        page += 1

    if refresh_all and set(records_by_source_id) != listed_source_ids:
        raise RuntimeError("상세 조회 결과와 현재 목록의 ID가 일치하지 않아 원본을 보존했습니다.")
    records = sorted(
        (records_by_source_id[source_id] for source_id in listed_source_ids),
        key=lambda record: int(record["id"]),
        reverse=True,
    )
    save_records(checkpoint, records)
    if output.exists():
        checkpoint.chmod(output.stat().st_mode & 0o777)
    checkpoint.replace(output)
    print(f"[완료] {len(records)}건 저장: {output}", flush=True)
    return records


def main() -> None:
    """명령줄 옵션을 확인하고 전체 데이터 수집을 시작합니다."""
    parser = argparse.ArgumentParser(
        description="청주톡톡 공개 민원사례 목록과 상세 내용을 JSON으로 저장합니다."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="저장할 JSON 파일 경로 (기본값: rag/origin/공개_민원_사례.json)",
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
    parser.add_argument(
        "--refresh-all",
        action="store_true",
        help="기존 게시물의 수정된 답변도 반영하도록 모든 상세 페이지를 다시 수집합니다.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="동시 상세 요청 수 (기본값: 4)",
    )
    args = parser.parse_args()
    if args.delay < 0 or args.timeout <= 0 or args.workers < 1:
        parser.error("--delay는 0 이상, --timeout과 --workers는 0보다 커야 합니다.")
    collect(args.output, args.delay, args.timeout, refresh_all=args.refresh_all, workers=args.workers)


if __name__ == "__main__":
    main()

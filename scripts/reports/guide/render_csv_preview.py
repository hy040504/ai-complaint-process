"""담당자 CSV 내보내기 파일을 표 계산 프로그램처럼 보이는 HTML로 그려 가이드 그림을 만듭니다.

CSV 내보내기는 화면이 바뀌지 않고 파일만 내려받으므로, 가이드에는 "내려받은 파일을 열면
이렇게 보인다"는 그림이 필요합니다. 실제로 내려받은 CSV를 그대로 읽어 열 머리(A, B, …)와
행 번호가 있는 표로 그리고, 가이드 글의 번호와 같은 번호를 열 묶음 위에 붙입니다.

사용법:
    python scripts/reports/guide/render_csv_preview.py 내려받은.csv 출력.html [화면에 보일 파일 이름]
    msedge --headless --screenshot=docs/assets/guide/s13-csv.png --window-size=1280,420 출력.html
"""

from __future__ import annotations

import csv
import html
import sys
from pathlib import Path

# (번호, 열 이름들): 가이드 글의 표와 같은 번호입니다.
GROUPS: list[tuple[int, tuple[str, ...]]] = [
    (1, ("민원ID", "등록일")),
    (2, ("상태",)),
    (3, ("배정부서", "담당자")),
    (4, ("AI판정", "AI사유")),
    (5, ("답변게시여부", "추가문의수")),
]

CSS = """
* { box-sizing: border-box; }
body { margin: 0; padding: 22px 18px 18px; background: #f3f4f6;
  font-family: 'Malgun Gothic', 'Noto Sans KR', sans-serif; color: #1f2937; }
.bar { font-size: 13px; color: #374151; margin: 0 0 10px; }
.bar b { color: #111827; }
table { border-collapse: collapse; background: #fff; font-size: 14px; }
.gap { font-size: 12px; color: #6b7280; margin: 12px 0 8px; }
th, td { border: 1px solid #d1d5db; padding: 5px 7px; white-space: nowrap; text-align: left; }
thead .letters th { background: #e5e7eb; color: #6b7280; font-weight: 600; text-align: center; font-size: 11px; }
thead .names th { background: #f9fafb; font-weight: 700; position: relative; }
thead .names th:has(.badge) { padding-left: 20px; }
td.rn, th.rn { background: #e5e7eb; color: #6b7280; text-align: center; width: 28px; font-weight: 600; }
.hl { background: #fdecea !important; box-shadow: inset 0 0 0 1px #d92d20; }
td.hl { background: #fff5f4 !important; }
.badge { position: absolute; top: -13px; left: -9px; width: 24px; height: 24px; border-radius: 50%;
  background: #d92d20; color: #fff; font-size: 13px; font-weight: 800; display: flex;
  align-items: center; justify-content: center; box-shadow: 0 0 0 2px #fff, 0 2px 5px rgba(0,0,0,.3); }
"""


def column_letter(index: int) -> str:
    """0부터 시작하는 열 번호를 표 계산 프로그램식 글자(A, B, …, Z, AA)로 바꿉니다.

    Args:
        index: 0부터 시작하는 열 번호입니다.

    Returns:
        열 머리 글자입니다.
    """
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def render_part(header: list[str], body: list[list[str]], columns: range) -> str:
    """CSV의 일부 열만 표 하나로 그립니다. 열 머리 글자는 원래 위치(A, B, …)를 유지합니다.

    Args:
        header: 전체 열 이름 목록입니다.
        body: 전체 데이터 행 목록입니다.
        columns: 이 표에 넣을 열 번호 범위입니다.

    Returns:
        `<table>` HTML 조각입니다.
    """
    group_of = {name: n for n, names in GROUPS for name in names}
    first_of = {names[0]: n for n, names in GROUPS}
    letters = "".join(f"<th>{column_letter(i)}</th>" for i in columns)
    names = []
    for i in columns:
        name = header[i]
        cls = ' class="hl"' if name in group_of else ""
        badge = (
            f'<span class="badge">{first_of[name]}</span>' if name in first_of else ""
        )
        names.append(f"<th{cls}>{badge}{html.escape(name)}</th>")
    lines = []
    for number, row in enumerate(body, start=2):
        cells = "".join(
            f'<td{' class="hl"' if header[i] in group_of else ""}>{html.escape(row[i])}</td>'
            for i in columns
        )
        lines.append(f'<tr><td class="rn">{number}</td>{cells}</tr>')
    return (
        f'<table><thead><tr class="letters"><th class="rn"></th>{letters}</tr>'
        f'<tr class="names"><td class="rn">1</td>{"".join(names)}</tr></thead>'
        f"<tbody>{''.join(lines)}</tbody></table>"
    )


def render(rows: list[list[str]], filename: str) -> str:
    """CSV 행을 번호 표시가 붙은 표 HTML로 만듭니다.

    열이 15개라 한 줄로 그리면 가이드·PDF 폭에 맞춰 줄였을 때 글자를 읽기 어렵습니다.
    그래서 앞쪽 열(A~H)과 뒤쪽 열(I~)을 위아래 두 표로 나눠 그립니다.

    Args:
        rows: 첫 행이 열 이름인 CSV 행 목록입니다.
        filename: 화면 위쪽에 보일 파일 이름입니다.

    Returns:
        완결 HTML 문자열입니다.
    """
    header, body = rows[0], rows[1:]
    split = min(8, len(header))
    first = render_part(header, body, range(0, split))
    second = render_part(header, body, range(split, len(header)))
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        f"<style>{CSS}</style></head><body>"
        f'<p class="bar">내려받은 파일 <b>{html.escape(filename)}</b>을 표 계산 프로그램으로 연 모습'
        " (열이 많아 앞쪽 A~H열과 뒤쪽 I열부터를 나눠 보였습니다)</p>"
        f'{first}<p class="gap">이어서 오른쪽 열 →</p>{second}</body></html>'
    )


def main() -> None:
    """명령줄의 CSV를 읽어 HTML을 저장합니다.

    세 번째 인자를 주지 않으면 서버가 붙이는 이름 형식(`cheongju-complaints-날짜-시각.csv`)의
    예시 이름을 씁니다.
    """
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    shown = (
        sys.argv[3] if len(sys.argv) > 3 else "cheongju-complaints-20261123-0647.csv"
    )
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    target.write_text(render(rows, shown), encoding="utf-8")
    print(f"HTML 생성: {target} ({len(rows) - 1}행)")


if __name__ == "__main__":
    main()

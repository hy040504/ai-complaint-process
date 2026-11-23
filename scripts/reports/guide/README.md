# 사용 가이드 그림·PDF 만들기 (`scripts/reports/guide/`)

[스크립트 안내](../../README.md) · [사용 가이드](../../../docs/guides/README.md)

[사용 가이드](../../../docs/guides/README.md)에 들어가는 **번호가 붙은 화면 그림**과 **PDF**를 다시 만드는 도구입니다. 화면이 바뀌어 그림이 실제와 달라졌을 때 씁니다.

| 파일 | 하는 일 |
| --- | --- |
| [`capture.mjs`](capture.mjs) | 브라우저로 화면을 열고 기능 영역에 **번호 배지와 빨간 테두리**를 그려 PNG로 저장합니다. |
| [`screens.json`](screens.json) | 어떤 주소를 열고, 무엇을 누르고, 어디에 몇 번을 붙일지 적은 **화면 목록**입니다. |
| [`build_guide_pdf.py`](build_guide_pdf.py) | 가이드 마크다운(`docs/guides/*.md`)을 인쇄용 PDF로 바꿉니다. |
| [`render_csv_preview.py`](render_csv_preview.py) | 담당자가 내려받은 CSV를 "표 계산 프로그램으로 연 모습"의 HTML로 그립니다(`s13-csv` 그림용). |

## 그림 다시 찍기

필요한 것: Node.js, Edge 또는 Chrome, 그리고 **시연 로그인을 끈** 민원 웹 서버(`COMPLAINT_DEMO_LOGIN=0`) 한 대.

1. 서버를 시연 로그인을 끈 채로 띄웁니다. 예: `COMPLAINT_DEMO_LOGIN=0 COMPLAINT_PORT=5001 python -m src`
   (`screens.json`의 `base`가 `http://127.0.0.1:5001`입니다. 다르면 고치세요.)
2. 브라우저를 원격 디버깅 모드로 띄웁니다.
   `msedge --headless --remote-debugging-port=9395 --remote-allow-origins=* --user-data-dir=<빈 폴더> about:blank`
3. 담당자·민원인 계정 정보를 **환경변수**로 넘기고 실행합니다. (비밀번호를 파일에 쓰지 않아요.) 민원인 계정(`GUIDE_CITIZEN_ID`·`GUIDE_CITIZEN_PW`)은 로그인한 민원인 화면(`c10-member`)에만 씁니다.

```bash
GUIDE_STAFF_ID=담당자아이디 GUIDE_STAFF_PW=비밀번호 \
GUIDE_CITIZEN_ID=민원인아이디 GUIDE_CITIZEN_PW=비밀번호 \
node scripts/reports/guide/capture.mjs 9395 scripts/reports/guide/screens.json docs/assets/guide
```

- 한 장만 다시 찍으려면 `screens.json` 맨 위에 `"only": ["s02-home"]`처럼 이름을 적습니다.
- 어떤 요소를 짚을 수 있는지 보려면 마지막 인자에 `dump`를 붙입니다. 화면별 버튼·입력 칸 이름과 위치가 출력돼요.

### 번호를 붙이는 방법 (`notes`)

| 적는 방식 | 뜻 |
| --- | --- |
| `css:#title` | CSS 선택자로 요소를 찾습니다. |
| `text:민원 등록하기` | 화면에 보이는 글자가 들어 있는 가장 작은 요소를 찾습니다. |
| `panel:처리 프로세스` | 그 글자가 들어 있는 **패널 전체**를 감쌉니다. |
| `xy:x,y,너비,높이` | 위치를 직접 지정합니다. (문서 좌표, 1280px 폭 기준) |
| `"badge": "right"` | 번호를 오른쪽 위에 둡니다. (글자를 가릴 때 씁니다.) |

> 열린 모달(팝업)에서는 번호 표시를 모달 안에 그려 넣습니다(브라우저가 모달을 최상위 층에 그려 일반 표시를 가리기 때문).

> 이 도구는 **시험 민원을 실제로 접수**합니다(게스트로 작성). 다시 찍은 뒤에는 DB에서 시험 민원을 지워 주세요.
>
> `c10-member`(로그인한 민원인의 내 민원)와 `s09-followup`(추가 문의 목록)은 그 계정의 민원과 추가 문의가 **미리 있어야** 의미 있는 화면이 나옵니다. 찍기 전에 민원인으로 비공개 민원을 하나 쓰고, 담당자가 "내가 담당"을 누른 뒤, 민원인이 추가 문의를 보내 두세요(찍은 뒤 삭제). `s05b-unassign`(배정 해제 창)은 목록에서 **"부서 변경" 버튼**(부서가 배정된 민원)을 찾아 누르므로, 부서가 배정된 민원이 하나 있어야 합니다.

### CSV 그림 (`s13-csv`)

CSV 내보내기는 화면이 바뀌지 않으므로, 실제로 내려받은 파일을 표로 그려 찍습니다.

```bash
python scripts/reports/guide/render_csv_preview.py 내려받은.csv preview.html
msedge --headless --screenshot=docs/assets/guide/s13-csv.png --window-size=990,405 preview.html
```

## PDF 만들기

```bash
python scripts/reports/guide/build_guide_pdf.py
```

`docs/guides/`의 두 가이드를 읽어 같은 폴더에 `.pdf`로 저장합니다. 가이드에서 쓰는 마크다운 문법(제목·표·목록·인용·그림·굵게·링크)만 해석하는 작은 변환기입니다.

그림과 표는 쪽 가운데서 잘리지 않고 통째로 다음 쪽으로 넘어갑니다. 그래서 **제목·소개·첫 그림**, **굵은 소제목·바로 뒤 표나 목록**은 한 묶음으로 처리해, 제목만 쪽 끝에 홀로 남지 않게 합니다.

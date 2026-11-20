# 팀원용 UI 실행 가이드 (원본 UI와 프로토타입 비교)

이 문서는 `ui-serve` 브랜치 기준입니다. 같은 백엔드를 두 개의 포트로 띄워 최신 UI(원본)와 구상 기능 프로토타입을 나란히 확인합니다.

- 원본 UI: `ui` 브랜치의 `ui/` 폴더 (5000번 포트)
- 프로토타입: `ui2` 브랜치의 `ui_proto/` 폴더 (5001번 포트)
- 백엔드: 이 브랜치의 `src/` (두 포트가 같은 DB를 공유합니다)

## 1. 저장소 받기

```powershell
git clone https://github.com/hy040504/ai-complaint-process.git
cd ai-complaint-process
git checkout ui-serve
git checkout origin/ui2 -- ui_proto
```

마지막 명령은 `ui2` 브랜치의 프로토타입 폴더 `ui_proto/`만 작업 폴더에 가져옵니다. 이 폴더는 커밋하지 않아도 됩니다.

## 2. 파이썬 환경

웹 서버는 `.venv-web` 환경을 씁니다. 설치 절차는 `src/README.md`를 따릅니다.

검사기가 쓰는 검색 API(8007번 포트)는 `uvicorn`이 있는 `.venv` 환경으로 실행합니다. 두 환경 모두 설치되어 있어야 검사기가 동작합니다.

## 3. PostgreSQL

- 데이터베이스 이름은 `complaints_native`입니다. 스키마 `complaint_app`과 `complaint_rag`가 필요합니다.
- 서버 접속 사용자는 `PGUSER` 환경변수로 지정합니다. 설정하지 않으면 Windows 사용자 이름이 쓰여 접속이 실패할 수 있습니다.

```powershell
$env:PGUSER = "<사용자 이름>"
$env:PGHOST = "127.0.0.1"
$env:PGDATABASE = "complaints_native"
```

비밀번호는 `pgpass.conf` 또는 `PGPASSWORD`로 설정합니다. 비밀번호는 문서나 저장소에 적지 않습니다.

## 4. 서버 실행

저장소 루트에서 두 개의 창을 엽니다.

원본 UI (5000번 포트):

```powershell
$env:PYTHONUTF8 = "1"
.\.venv-web\Scripts\python.exe -m src
```

프로토타입 (5001번 포트):

```powershell
$env:PYTHONUTF8 = "1"
$env:COMPLAINT_PORT = "5001"
$env:COMPLAINT_UI_DIR = (Resolve-Path .\ui_proto).Path
.\.venv-web\Scripts\python.exe -m src
```

`COMPLAINT_UI_DIR`을 지정하지 않으면 `ui/` 폴더를 씁니다. 이 값이 원본과 프로토타입을 나누는 유일한 차이입니다.

검사기를 쓰려면 검색 API도 함께 띄웁니다.

```powershell
.\.venv\Scripts\python.exe -m rag serve --host 127.0.0.1 --port 8007
```

검색 API가 준비되는 데 수십 초 걸릴 수 있습니다.

## 5. 접속

- 원본 UI: `http://127.0.0.1:5000/#/citizen` (담당자 화면은 `#/staff`, 검사기는 `#/lab`)
- 프로토타입: `http://127.0.0.1:5001/#/citizen` (같은 경로)

처음 접속하면 시민 또는 담당자 역할을 선택하는 시연 화면이 나옵니다.

## 6. 검사기 AI

검사기 결과는 `.env`의 AI 설정과 Codex CLI 로그인 상태에 따라 달라집니다. 응답은 1분 이상 걸릴 수 있습니다. 결과 카드에서 "이 초안으로 편집 시작"은 프로토타입에만 있습니다.

## 7. 자주 나는 문제

- 서버가 "PostgreSQL 접속 실패"로 멈춤: `PGUSER`, `PGHOST`, `PGDATABASE` 설정을 확인합니다.
- 담당자 화면에서 "서버 데이터를 불러오지 못했습니다": 같은 포트의 서버를 껐다 다시 켠 뒤 Ctrl + F5로 새로고침합니다.
- 검사기에서 검색 오류: 8007번 포트 검색 API가 떠 있는지 확인합니다.
- 프로토타입 화면이 원본과 같게 보임: `COMPLAINT_UI_DIR`이 `ui_proto`를 가리키는지, 5001번 창을 새로 띄웠는지 확인합니다.

## 8. 비교 보고서

화면 비교 캡처와 설명은 `UI_비교_20261120.pdf`에 있습니다. 이 PDF는 저장소 밖(일일 보고 폴더)에 있으므로 별도로 받아 주세요.

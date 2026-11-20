# 팀원용 실행 가이드 (원본 UI와 프로토타입 비교)

이 가이드를 따라 하면 **원본 UI**와 **프로토타입**을 내 PC에서 각각 띄워 비교할 수 있습니다.

- 원본 UI는 5000번 포트에서 열립니다.
- 프로토타입은 5001번 포트에서 열립니다.

따라 하기 전에 아래 3가지를 확인해 주세요.

1. Git이 설치되어 있어야 합니다. 설치는 https://git-scm.com 에서 합니다.
2. Python 3.12와 PostgreSQL이 설치되어 있어야 합니다. 설치 방법은 `src/README.md`에 있습니다.
3. 명령은 모두 **PowerShell** 창에 입력합니다. 시작 메뉴에서 "PowerShell"을 검색해 엽니다.

---

## 1단계. 저장소 내려받기

PowerShell 창에 아래 두 줄을 한 줄씩 입력하고 Enter를 누릅니다.

```powershell
cd $HOME\Desktop
git clone https://github.com/hy040504/ai-complaint-process.git
```

- 첫 줄은 바탕 화면으로 이동하는 명령입니다.
- 둘째 줄은 저장소를 바탕 화면에 내려받는 명령입니다. `ai-complaint-process`라는 폴더가 생깁니다.
- 실행 중 로그가 길게 나오는 것은 정상입니다.

## 2단계. 저장소 폴더로 들어가기

```powershell
cd $HOME\Desktop\ai-complaint-process
```

이 뒤의 모든 명령은 **이 폴더 안에서** 실행합니다. 창을 닫았다면 이 명령을 다시 입력해 주세요.

## 3단계. 실행 코드 브랜치로 바꾸기

```powershell
git checkout ui-serve
```

"Switched to branch 'ui-serve'"가 나오면 성공입니다.

## 4단계. 프로토타입 폴더 가져오기

```powershell
git checkout origin/ui2 -- ui_proto
```

이 명령이 끝나면 `ai-complaint-process` 폴더 안에 `ui_proto` 폴더가 생깁니다. 확인하려면 아래 명령을 입력해 봅니다.

```powershell
dir ui_proto
```

`index.html`과 `src` 같은 파일 목록이 보이면 성공입니다.

## 5단계. 데이터베이스 접속 정보 설정

PostgreSQL에 접속할 사용자 이름을 알려 줘야 합니다. 아래 `<사용자 이름>` 부분을 본인 PostgreSQL 사용자 이름으로 바꿔서 입력합니다.

```powershell
$env:PGUSER = "<사용자 이름>"
$env:PGHOST = "127.0.0.1"
$env:PGDATABASE = "complaints_native"
```

- 이 설정은 **PowerShell 창을 닫으면 사라집니다.**
- 비밀번호는 여기에 적지 않습니다. PostgreSQL 비밀번호 파일(pgpass)이나 `PGPASSWORD`에 미리 설정해 두어야 합니다.

## 6단계. 원본 UI 서버 켜기 (5000번 포트)

**새 PowerShell 창을 하나 더 열고**, 아래 명령을 차례로 입력합니다. 이 창은 닫지 않습니다.

```powershell
cd $HOME\Desktop\ai-complaint-process
$env:PGUSER = "<사용자 이름>"
$env:PGHOST = "127.0.0.1"
$env:PGDATABASE = "complaints_native"
$env:PYTHONUTF8 = "1"
.\.venv-web\Scripts\python.exe -m src
```

- 마지막 줄을 입력하면 서버가 시작됩니다. 창에 오류가 계속 나오지 않으면 정상입니다.
- 가상환경 폴더(`.venv-web`)가 없다면 `src/README.md`의 설치 절차를 먼저 진행해 주세요.

## 7단계. 프로토타입 서버 켜기 (5001번 포트)

**또 다른 새 PowerShell 창을 하나 더 열고**, 아래 명령을 차례로 입력합니다.

```powershell
cd $HOME\Desktop\ai-complaint-process
$env:PGUSER = "<사용자 이름>"
$env:PGHOST = "127.0.0.1"
$env:PGDATABASE = "complaints_native"
$env:PYTHONUTF8 = "1"
$env:COMPLAINT_PORT = "5001"
$env:COMPLAINT_UI_DIR = (Resolve-Path .\ui_proto).Path
.\.venv-web\Scripts\python.exe -m src
```

- 이 창도 닫지 않습니다. 창이 두 개 떠 있는 상태가 정상입니다.

## 8단계. 서버가 켜졌는지 확인

서버를 켠 뒤 브라우저(Chrome 또는 Edge)에서 아래 주소를 엽니다. 주소창에 그대로 붙여넣으세요.

- 원본 UI 확인: http://127.0.0.1:5000/api/v1/health
- 프로토타입 확인: http://127.0.0.1:5001/api/v1/health

화면에 `"status":"ok"`라는 글자가 보이면 서버가 정상입니다.

## 9단계. 화면 열기

- 원본 UI: http://127.0.0.1:5000/#/citizen
- 프로토타입: http://127.0.0.1:5001/#/citizen

담당자 화면은 주소 끝의 `citizen` 부분을 `staff`로 바꾸면 됩니다. 예를 들어 `http://127.0.0.1:5001/#/staff`입니다.

처음 열면 시민 또는 담당자 역할을 고르는 시연 화면이 나옵니다. 아무거나 골라 들어가면 됩니다.

---

## 자주 나는 문제

- **6단계나 7단계에서 "PostgreSQL 연결 실패" 또는 "role does not exist" 같은 오류**: 5단계의 `PGUSER` 값이 맞는지 확인합니다. 값을 바꾼 뒤에는 서버 창에서 Ctrl + C를 눌러 끄고, 6단계 또는 7단계를 다시 입력합니다.
- **화면이 열리지만 데이터가 안 보임**: 8단계의 health 주소가 `"status":"ok"`인지 확인합니다. 아니라면 서버 창의 오류 문구를 복사해서 전달해 주세요.
- **담당자 화면에 "서버 데이터를 불러오지 못했습니다"**: 서버를 껐다 다시 켠 뒤 브라우저에서 Ctrl + F5로 새로고침합니다.
- **검사기에서 결과가 오래 안 나옴**: 검사기 AI 응답은 1분 이상 걸릴 수 있습니다. 기다린 뒤에도 실패하면 오류 문구를 전달해 주세요.
- **프로토타입 화면이 원본과 똑같이 보임**: 7단계의 `COMPLAINT_UI_DIR`이 설정되었는지, 5001번 창을 새로 띄웠는지 확인합니다.

## 서버 끄기

서버를 끄려면 해당 PowerShell 창에서 Ctrl + C를 누릅니다.

## 참고

- 비교 보고서 PDF(`UI_비교_20261120.pdf`)는 이 저장소에 없습니다. 별도로 전달받아 주세요.

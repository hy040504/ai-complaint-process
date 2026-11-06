# 응대 검사기 웹

`llm` 브랜치에서 시민·담당자 화면을 빼고 응대 검사기만 추출한 작은 서버입니다. 민원 JSON을 받으면 제목·상세로 검색 API를 먼저 호출하고 `src.assist`가 판정합니다. `complaint_app`에는 저장하지 않습니다.

`search_complaint_rag`는 PostgreSQL이 제공하는 프로그램이 아닙니다. 이 저장소가 Codex에 붙인 MCP 도구이며, 내부에서 `rag serve` 검색 API만 호출합니다. 검사기 웹의 기본 경로는 그 도구를 모델이 부르기 전에 **코드가 `run_web_assist`로 같은 검색을 먼저** 돌립니다.

## 실행

저장소 루트:

```powershell
.\.venv-web\Scripts\python.exe -m src.lab_web
```

Windows [`검사기-시작.cmd`](../../검사기-시작.cmd) · [`웹-시작.cmd`](../../웹-시작.cmd), Linux [`start-lab.sh`](../../start-lab.sh) · [`start-web.sh`](../../start-web.sh). 기본 주소는 `http://127.0.0.1:5010/`입니다. 포트는 `LAB_WEB_PORT`입니다. 기존 민원 CRUD Flask `:5000`은 그대로 둡니다.

## API

| 메서드·경로 | 내용 |
| --- | --- |
| `GET /` | 추출한 작성 화면 |
| `GET /api/v1/health` | `service=lab_web`, `searchAvailable`, `llmConfigured` |
| `GET /api/v1/lab/fields` | 민원 분야·발생 지역 목록 |
| `POST /api/v1/lab/complaints` | 민원 JSON → 검색·판정. 성공 200 |

요청 본문:

```json
{
  "title": "대형폐기물 배출",
  "category": "환경·청소",
  "district": "흥덕구",
  "body": "대형폐기물 배출 방법이 궁금합니다."
}
```

`district`는 생략하거나 빈 문자열이면 `null`입니다. 허용 분야는 `도로·교통`, `환경·청소`, `공원·녹지`, `생활·복지`, `주택·건축`, `기타`입니다. 허용 지역은 `상당구`, `서원구`, `흥덕구`, `청원구`입니다. 그 밖 필드는 422입니다.

검색 질의(`searchQuery`)는 제목과 상세 내용만 합칩니다. `district`는 구 필터입니다. 민원 분야는 검색 질의에 넣지 않습니다. 응답의 `assist`는 `POST /api/v1/assist`와 같은 판정 계약입니다.

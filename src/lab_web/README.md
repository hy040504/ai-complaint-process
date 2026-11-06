# 응대 검사기 웹

`llm` 브랜치에서 시민·담당자 화면을 빼고 응대 검사기만 추출한 작은 서버입니다. 민원 내용 JSON을 받아 언어 모델에 넘길 봉투를 만듭니다. **이 단계는 모델을 호출하지 않고**, `complaint_app`에도 저장하지 않습니다.

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
| `GET /api/v1/health` | `service=lab_web`, `llmSent=false` |
| `GET /api/v1/lab/fields` | 민원 분야·발생 지역 목록 |
| `POST /api/v1/lab/complaints` | 민원 JSON 수신. 성공 202 |

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

성공 응답의 `llm.query`는 분야·제목·본문을 합친 문자열이고 `llm.sent`는 `false`입니다.

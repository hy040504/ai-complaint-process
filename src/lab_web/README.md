# 응대 검사기 웹

`llm` 브랜치에서 시민·담당자 화면을 빼고 응대 검사기만 추출한 작은 서버입니다. 민원 JSON을 받으면 제목·상세로 검색 API를 먼저 호출하고 `src.assist`가 판정합니다. `complaint_app`에는 저장하지 않습니다. 화면 오른쪽 **테스트 기록**은 `.rag-cache/lab-runs/*.json`에 남기며, 항목을 고르면 파일을 읽어 다시 보여 주고 모델을 다시 부르지 않습니다. Git에는 올리지 않습니다. [CASE-066](../../docs/cases/사례-066-검사기-테스트기록-파일저장-2026-11-06.md)

`search_complaint_rag`는 PostgreSQL이 제공하는 프로그램이 아닙니다. 이 저장소가 Codex에 붙인 MCP 도구이며, 내부에서 `rag serve` 검색 API만 호출합니다. 검사기 웹의 기본 경로는 그 도구를 모델이 부르기 전에 **코드가 `run_web_assist`로 같은 검색을 먼저** 돌립니다. Codex와의 MCP 핸드셰이크는 줄 단위 JSON-RPC입니다. [CASE-058](../../docs/cases/사례-058-Codex-MCP-핸드셰이크-줄단위JSON-2026-11-06.md)

## 실행

저장소 루트:

```powershell
.\.venv-web\Scripts\python.exe -m src.lab_web
```

Windows [`검사기-시작.cmd`](../../검사기-시작.cmd) · [`웹-시작.cmd`](../../웹-시작.cmd)(PostgreSQL·검색 API 원클릭 자동 연동 [CASE-074](../../docs/cases/사례-074-검사기-백엔드검색서비스-자동기동-2026-11-10.md)), Linux [`start-lab.sh`](../../start-lab.sh) · [`start-web.sh`](../../start-web.sh). 기본 주소는 `http://127.0.0.1:5010/`입니다. 포트는 `LAB_WEB_PORT`입니다. 기존 민원 CRUD Flask `:5000`은 그대로 둡니다.

## API

| 메서드·경로 | 내용 |
| --- | --- |
| `GET /` | 추출한 작성 화면 |
| `GET /api/v1/health` | `service=lab_web`, `searchAvailable`, `llmConfigured` |
| `GET /api/v1/lab/fields` | 민원 분야·발생 지역·공급자별 사용 가능 상태(`providers`) 목록 |
| `POST /api/v1/lab/complaints` | 민원 JSON(`provider` 포함) → 지명·장소 추적 및 검색·판정. 성공하면 `.rag-cache/lab-runs`에 JSON을 남김 |
| `POST /api/v1/lab/complaints/stream` | 같은 처리의 진행 안내 NDJSON 뒤 `done` 결과. 기록도 남김 |
| `GET /api/v1/lab/runs` | 테스트 기록 목록 |
| `GET /api/v1/lab/runs/<id>` | 기록 한 건 |
| `DELETE /api/v1/lab/runs` | 기록 파일 모두 삭제 |

요청 본문:

```json
{
  "title": "서원대 후문 가로수 쓰러짐",
  "category": "공원·녹지",
  "district": "",
  "body": "서원대학교 후문 편의점 근처 가로수가 쓰러졌습니다.",
  "provider": "exaone_api"
}
```

`district`는 생략하거나 빈 문자열이면 `null`입니다. `provider`도 생략하면 `.env` 기본 공급자를 사용하며, `"exaone_api"` · `"openai_api"` · `"codex_cli"`를 지정할 수 있습니다. 허용 분야는 `도로·교통`, `환경·청소`, `공원·녹지`, `생활·복지`, `주택·건축`, `기타`입니다. 발생 지역은 `상당구`, `서원구`, `흥덕구`, `청원구` 4개 구 및 산하 읍·면·동 세부 지역 목록(`districtAreas`)을 지원하며, 비워두면 제목·본문 지명과 네이버 지도 장소 검색(`lookup_navermap_place`)으로 구·동을 추론해 검색 `district` 필터로 자동 연결합니다. 그 밖 필드는 422입니다. [CASE-072](../../docs/cases/사례-072-검사기-청주지역선택-지명추출-2026-11-09.md) · [CASE-083](../../docs/cases/사례-083-서원대후문-장소추적-MCP연동-위치인식-2026-11-13.md)

## LLM 엔진 선택 · 키 잠금 · 장소 추적

- **엔진 선택 단추:** 화면에서 `.env` 기본 · `K-EXAONE 2.5` (`exaone_api`) · `GPT-6 Luna` (`openai_api`) · `Codex CLI` (`codex_cli`)를 전환할 수 있으며 마지막 선택을 브라우저 `localStorage`에 기억합니다. [CASE-084](../../docs/cases/사례-084-K-EXAONE-API공급자-추가와-Tabular-구상-2026-11-13.md)
- **키 미설정 비활성화:** `/api/v1/lab/fields`의 `providers`를 읽어 `.env`에 API 키(`EXAONE_API_KEY`, `OPENAI_API_KEY`)나 Codex 실행 파일이 없으면 해당 단추를 `aria-disabled="true"`와 흐림 상태로 잠그고 `키 미설정`·`미설치` 배지를 붙입니다. 잠긴 단추를 누르면 흔들림(`shake`) 피드백만 주고 선택을 바꾸지 않으며, `localStorage`에 잠긴 공급자가 남아 있어도 사용 가능한 단추로 자동 전환합니다. [CASE-085](../../docs/cases/사례-085-API키-미설정시-LLM선택-비활성화-UI효과-2026-11-13.md) · [CASE-087](../../docs/cases/사례-087-패치-주석-코드최적화-문서디자인-개선-2026-11-13.md)
- **K-EXAONE 2.5 파라미터:** `.env`의 `EXAONE_REASONING_EFFORT`(`max` 기본, `low`/`high`/`max`), `EXAONE_MAX_TOKENS`(`16384`), `EXAONE_TEMPERATURE`(`0.7`), `EXAONE_TOP_P`(`0.95`)로 추론 토큰 한도와 생성 성향을 조절합니다. [CASE-086](../../docs/cases/사례-086-K-EXAONE-추론강도-최대토큰-파라미터-최적화-2026-11-13.md)
- **결과 배지:** 결과 카드 상단에 `📍 발생 지역`, `🗺️ 장소 추적`(`assist.inferredPlace` 도로명/지번 주소), `🤖 판정 엔진` 배지를 표시합니다.

검색 질의(`searchQuery`)는 제목과 상세 내용만 합칩니다. `district`는 구 필터입니다. 민원 분야는 검색 질의에 넣지 않습니다. 응답의 `assist`는 `POST /api/v1/assist`와 같은 판정 계약입니다. `assist.codex`는 모델에 넣은 호출 목록입니다. 1차는 `PREFIX-00 + PREFIX-01`과 검색 후보·장소(`inferred_place`) JSON이고, `faq_answer`이면 `PREFIX-00 + PREFIX-02`가 이어집니다. FAQ가 아니면 `PREFIX-00 + PREFIX-03` 담당자 초안(`staffDraft`)을 만들고, 원문에 거친 표현 힌트가 있으면 `PREFIX-00 + PREFIX-04` 순화(`sanitize`)를 붙입니다. 초안은 시민 안내를 덮지 않습니다. 결과 화면에 처리 사유를 보여 줍니다. 민원을 보내는 동안 검색·판정·초안 단계 안내와 대기 애니메이션을 보여 주며, 기본 경로는 `/complaints/stream` NDJSON입니다. `assist.codex[].prompt`는 `codex exec -` 표준 입력 전문입니다. Codex 입력·보낸 민원·받은 응답 JSON 칸마다 `JSON 복사`가 있고, 프롬프트 칸마다 `프롬프트 복사`가 있습니다. FAQ 제목이 맞아도 질문이 요구하는 항목이 본문에 없으면 안내하지 않습니다. 공급자가 사용량을 주면 `assist.codex[].usage`의 `cachedTokens`·`reasoningTokens` 등에 실립니다. [CASE-061](../../docs/cases/사례-061-PREFIX-03-04-검색재평가-실측-2026-11-06.md) · [CASE-063](../../docs/cases/사례-063-여권FAQ조건부족-검사기사유표시-2026-11-06.md)

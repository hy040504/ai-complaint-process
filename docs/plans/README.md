# 계획·설계 문서 (`docs/plans/`)

[프로젝트 소개](../../README.md) · [문서 목차](../README.md) · [구조 개선안](프로젝트_구조_개선안.md)

앞으로의 구현 **계획·상세설계·제안**과 로드맵 가운데 현행 기준이 되는 것만 이 폴더 바로 아래에 둡니다(2026-11-22에 `plan/`에서 `docs/plans/`로 옮겼습니다). 초기 기획 자료는 [`archive/`](archive/)로 옮겼습니다.

| 문서 | 내용 |
| --- | --- |
| [MVP 실행 계획](harness-roadmap.md) | 다음 작업·완료 조건·결정 기록 |
| [LLM + RAG 우선 구현계획](언어모델과_검색증강생성_우선_구현계획.md) | 처리 흐름·Jev 후속 확장 |
| [시연 웹·민원 서버 구현계획](시연_웹_게시판과_민원_서버_구현계획.md) | 게시판·답변 교환·저장·API |
| [웹 상세설계·분야별 작업계획](민원_웹_MVP_상세설계와_분야별_작업계획.md) · [PDF](민원_웹_MVP_상세설계와_분야별_작업계획.pdf) | 화면·권한·버전·이벤트, UI·백엔드·AI·DB 작업 |
| [모델 선정과 미세조정 제안](모델_선정과_미세조정_제안.md) | 무료 LLM 후보·한국어 평가·LoRA 조건 |
| [Jev 1차 판정 도입 제안서 (PDF)](Jev_1차판정_도입_제안서.pdf) | Jev를 판정에 쓰는 대체·보완 방식, 변경 목록, 위험, 비교 실험 계획(제안·미구현). 생성: `scripts/reports/plan_jev_proposal.py` |
| [민원 AI 처리과정 상세설명서 (PDF)](민원_AI_처리과정_상세설명서.pdf) | 42쪽. 한눈에 보는 파이프라인 요약(3쪽), 서버·화면(제1부)과 AI 계층(제2부) 구분, AI 워커(스레드) 역할·생성 시점, 접수 API→검색→판정 입력·프롬프트→LLM 호출→코드 검증→응답·오류 경로, 갈래별(faq_answer·department_suggestion·human_handoff) 호출 레시피와 비교표, 시민용/담당자용 표시, 부록 B 코드 위치 사전, 부록 C RAG 지식베이스(두 JSON→검색 본문→임베딩·낱말 색인→pgvector DB 구조·적재·검색, 그림 4개)(현재 구현 기준). 생성: `scripts/reports/plan_ai_process.py`·`plan_ai_process_rag.py` |
| [데이터베이스 ER 다이어그램](데이터베이스_ER다이어그램.md) · [PDF](데이터베이스_ER다이어그램.pdf) | 업무 스키마 `complaint_app` 13개·검색 스키마 `complaint_rag` 8개 테이블의 칼럼·키·관계(실제 DDL 기준, Mermaid). 생성: `scripts/reports/export_er_diagram_pdf.py` |
| [프로젝트 구조 개선안](프로젝트_구조_개선안.md) | 폴더·파일 구성 정리 (구현됨/미구현 구분 포함) |

## `archive/` — 초기 기획 자료 (참고용)

| 자료 | 설명 |
| --- | --- |
| [`민원AI_계획서_상세분석.md`](archive/민원AI_계획서_상세분석.md) · [`civil_complaint_plan_enhanced_redacted.pdf`](archive/civil_complaint_plan_enhanced_redacted.pdf) | 최초 계획서와 상세 분석 |
| [`VoteLab_AI민원_상세기획안_상세분석.md`](archive/VoteLab_AI민원_상세기획안_상세분석.md) · [원본 PDF](<archive/보트랩 VoteLab _ AI 민원 상세 기획안 - 산학공동.pdf>) | VoteLab 상세 기획안 |
| [`db 설계 1차/`](<archive/db 설계 1차/2026-10-30/README.md>) | 2026-10-30 DB 설계 1차(SQL·회의록). 실행 DDL은 `rag/origin/schema/`·`src/complaints/schema/` |

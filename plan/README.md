# 계획 문서 (`plan/`)

[프로젝트 소개](../README.md) · [문서 목차](../docs/README.md) · [구조 개선안](프로젝트_구조_개선안.md)

현행 기준이 되는 구현 계획만 이 폴더 바로 아래에 둡니다. 초기 기획 자료는 [`archive/`](archive/)로 옮겼습니다.

| 문서 | 내용 |
| --- | --- |
| [MVP 실행 계획](harness-roadmap.md) | 다음 작업·완료 조건·결정 기록 |
| [LLM + RAG 우선 구현계획](언어모델과_검색증강생성_우선_구현계획.md) | 처리 흐름·Jev 후속 확장 |
| [시연 웹·민원 서버 구현계획](시연_웹_게시판과_민원_서버_구현계획.md) | 게시판·답변 교환·저장·API |
| [웹 상세설계·분야별 작업계획](민원_웹_MVP_상세설계와_분야별_작업계획.md) · [PDF](민원_웹_MVP_상세설계와_분야별_작업계획.pdf) | 화면·권한·버전·이벤트, UI·백엔드·AI·DB 작업 |
| [모델 선정과 미세조정 제안](모델_선정과_미세조정_제안.md) | 무료 LLM 후보·한국어 평가·LoRA 조건 |
| [프로젝트 구조 개선안](프로젝트_구조_개선안.md) | 폴더·파일 구성 정리 (구현됨/미구현 구분 포함) |

## `archive/` — 초기 기획 자료 (참고용)

| 자료 | 설명 |
| --- | --- |
| [`민원AI_계획서_상세분석.md`](archive/민원AI_계획서_상세분석.md) · [`civil_complaint_plan_enhanced_redacted.pdf`](archive/civil_complaint_plan_enhanced_redacted.pdf) | 최초 계획서와 상세 분석 |
| [`VoteLab_AI민원_상세기획안_상세분석.md`](archive/VoteLab_AI민원_상세기획안_상세분석.md) · [원본 PDF](<archive/보트랩 VoteLab _ AI 민원 상세 기획안 - 산학공동.pdf>) | VoteLab 상세 기획안 |
| [`db 설계 1차/`](<archive/db 설계 1차/2026-10-30/README.md>) | 2026-10-30 DB 설계 1차(SQL·회의록). 실행 DDL은 `rag/origin/schema/`·`src/complaints/schema/` |

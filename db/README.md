# 청주톡톡 민원 데이터

[프로젝트 소개](../README.md) · [문서 목차](../docs/README.md) · [데이터 계약](../docs/harness/data-contracts.md) · [변경 이력](../CHANGELOG.md)

프로젝트 목적, LLM + RAG 역할과 Jev 후속 확장, MVP 순서는 [프로젝트 README](../README.md)에 정리했습니다. 이 문서는 실제 데이터 필드와 정규화·갱신 규칙을 설명합니다.

| 데이터 | 프로젝트에서의 역할 |
| --- | --- |
| `자주_묻는_민원.json` | FAQ에 근거한 1차 안내·답변 |
| `공개_민원_사례.json` | 유사 민원과 현재 부서에 근거한 담당 부서 추천 |

두 목적의 검색 구현은 [RAG 실행 문서](../rag/README.md)에 있습니다. 원본 JSON은 유지하고, 임베딩·한국어 BM25 색인·부서 디렉터리를 별도의 PostgreSQL `complaint_rag` 스키마에 저장합니다. 공식 업무분장이 없는 부서는 검증 전 상태로 구분합니다.

프로젝트의 데이터 파일은 이 `db/` 아래에 모읍니다. 검색 코드·업무 서버·설치 스크립트는 아래 경로를 사용합니다.

| 경로 | 내용 | Git |
| --- | --- | --- |
| `자주_묻는_민원.json` | FAQ 원문 94건 | 포함 |
| `공개_민원_사례.json` | 공개 사례 원문 5,015건 | 포함 |
| `schema/complaint_rag.sql` | 검색용 PostgreSQL 스키마. `rag/store.py`가 `__EMBEDDING_DIM__`을 현재 프로필 차원으로 바꿔 적용 | 포함 |
| `schema/complaint_app.sql` | 시연 웹 jsonb `complaints`·`idempotency`. 7테이블 정규화는 후속 | 포함 |
| `dumps/complaint_rag.dump` | 벡터가 들어 있는 검색 DB 복사본 | 제외. 우분투에서 `scripts/export-rag-dump.sh` |
| `app/` | 이전 시연 SQLite 잔여 경로. 현재 업무 저장은 PostgreSQL `complaint_app` | 잔여 `*.sqlite3`는 제외 |

SQL 파일만으로는 행이 없습니다. 다른 컴퓨터에서 검색까지 바로 쓰려면 dump를 함께 복사하거나 JSON으로 `python -m rag ingest`를 실행합니다. 스키마만 적용하려면 `scripts/apply-db-schema.sh`, dump 복원은 `scripts/restore-rag-dump.sh`입니다. 현재 시연 웹은 PostgreSQL `complaint_app`에 민원을 저장합니다. 검색 색인은 `complaint_rag`입니다.

이 폴더에는 청주톡톡 사이트에서 수집한 민원 자료를 JSON으로 정리한 파일 두 개가 있습니다. JSON 파일은 UTF-8 인코딩이며, 한글이 그대로 저장됩니다. 두 파일의 상세 페이지는 2026-10-24(UTC)에 전건 재확인했습니다.

각 항목의 `source_url`은 실제 상세 페이지 주소이고, `retrieved_at`은 해당 페이지를 다시 확인한 UTC 시각입니다. **`retrieved_at`은 원문 수정일이 아닙니다.** 사이트가 최종 수정일을 제공하지 않으므로 JSON에도 확인되지 않은 수정일을 채우지 않습니다.

## 공개 민원 사례 — `공개_민원_사례.json`

시민이 공개한 민원사례와 담당 부서의 답변 **5,015건**을 담습니다. 최상위 구조는 **배열**이며, 각 배열 원소가 민원 한 건입니다.

| 필드 | 자료형 | 의미 |
| --- | --- | --- |
| `id` | 숫자 | 사이트 목록에 표시된 번호입니다. 게시물 이동·삭제에 따라 달라질 수 있습니다. |
| `title` | 문자열 | 민원사례 제목입니다. |
| `complaint_date` | 문자열 | 민원 신청일입니다. `YYYY-MM-DD` 형식입니다. |
| `summary` | 문자열 | 민원 요지입니다. |
| `department` | 문자열 | 정규화한 부서 표기입니다. 폐지된 과거 부서도 포함하므로 이관에는 `department_current`를 사용합니다. |
| `department_original` | 문자열 | 이번 정규화 직전 저장된 부서 표기입니다. 이후 새로 수집하는 항목은 사이트 표기를 보존합니다. |
| `department_current` | 문자열 또는 `null` | 확인된 현재 부서명입니다. 폐지·미확인 부서는 `null`입니다. |
| `department_status` | 문자열 | `current`, `normalized`, `renamed`, `review_required` 중 하나입니다. |
| `department_checked_on` | 문자열 | 부서 정규화 기준 확인일입니다. 상세 페이지 수집 시각과 구별합니다. |
| `resolution` | 문자열 | 민원에 대한 답변·처리 결과입니다. |
| `source_id` | 문자열 | 상세 페이지의 `no` 값입니다. 갱신할 때 같은 게시물을 식별하는 기준입니다. |
| `source_url` | 문자열 | 청주톡톡의 해당 공개 민원 상세 페이지입니다. |
| `retrieved_at` | 문자열 | 상세 페이지를 확인한 시각입니다. ISO 8601 UTC 형식입니다. |

구조 예시(일부 필드 생략, 본문은 설명용으로 축약):

```json
[
  {
    "id": 5015,
    "title": "711번 버스 운행 불만",
    "complaint_date": "2026-10-22",
    "summary": "711번 버스 운행 불편 민원",
    "department": "건설교통국 대중교통과",
    "department_original": "건설교통국 대중교통과",
    "department_current": "건설교통국 대중교통과",
    "department_status": "current",
    "department_checked_on": "2026-10-24",
    "resolution": "민원 내용을 검토하고 운수업체에 재발 방지 교육을 요청하겠다고 안내함.",
    "source_id": "638956",
    "source_url": "https://toktalk.cheongju.go.kr/home/sub.do?menukey=7401&mode=view&no=638956",
    "retrieved_at": "2026-10-24T03:53:54+00:00"
  }
]
```

사이트에 값이 없는 `summary` 또는 `resolution`은 빈 문자열(`""`)일 수 있습니다. `complaint_date`는 신청일이며, 답변 게시일이나 최종 수정일이 아닙니다. 배열은 게시물 번호 내림차순으로 저장됩니다.

2026-10-24 공식 조직도와 조직개편 기록을 대조하여 기존 `department` **505건**을 정리했습니다. 부서 표기는 **145종에서 129종**으로 줄었습니다. 이미 정리한 `건설교통국 대중교통과`는 **919건**입니다.

| 이번 변경 | 건수 | 적용 내용 |
| --- | ---: | --- |
| 상위 조직명 생략 12개 과 | 397 | 교통정책·균형건설·도로시설·공원관리·공원조성·산림관리·도시개발·도시재생·공동주택·건축디자인·문화유산·하천방재과의 소속 조직명 보완 |
| 경제일자리과 | 33 | `경제일자리과`, `경제투자국 경제일자리과` → `재정경제국 경제일자리과` |
| 기후대기과 | 66 | `환경관리본부 기후에너지과`로 변경 |
| 기업지원과·세정과·예산과 | 3 | 현재 `재정경제국` 소속 표기로 변경 |
| 미래산업과의 과거 별칭 | 6 | 과거 표기를 `경제투자국 미래산업과`로 통일하되 현재 이관 부서는 `null` 유지 |

`department_status`의 의미는 다음과 같습니다.

| 상태 | 현재 건수 | 의미 |
| --- | ---: | --- |
| `current` | 4,489 | 기존 표기로 현재 조직도의 부서를 식별할 수 있음 |
| `normalized` | 398 | 같은 부서의 소속 조직명·표기 보완 |
| `renamed` | 101 | 조직개편에 따른 현재 명칭 반영 |
| `review_required` | 27 | 현재 담당 부서 재확인 필요; `department_current`는 `null` |

확인 대상 **27건**은 폐지된 `미래산업과` 계열 **10건**, 과거 `안전정책과` **17건**입니다. 미래산업과는 에너지·투자유치·전시관 관련 업무가 섞여 있습니다. 안전정책과 사례에도 CCTV·그늘막·재난문자·수해 대응 등이 섞여 있어 현재 안전정책과·재난대응과 등과의 업무별 대응 관계를 확인해야 합니다. 이름만 보고 일괄 이관하지 않습니다.

RAG의 이관 후보에는 `department_current`를 사용하고, `null` 또는 `review_required`는 담당자 검토 대상으로 처리합니다. **현재 부서의 존재와 명칭을 확인한 것이며, 모든 과거 사례의 업무 관할을 현재 기준으로 재심사한 것은 아닙니다.** 관할 지역·구체적인 업무·검색 근거도 함께 판단해야 합니다. 상당구·서원구·흥덕구·청원구의 같은 이름 과는 별개 부서로 유지합니다.

`department_original`은 이번 변경 전 값을 보존합니다. 이전 단계에서 이미 통일한 대중교통과 표기는 당시 변경 전 원문을 복원한 값이 아닙니다. 이후 상세 페이지를 재수집하면 파서가 사이트 표기를 먼저 기록한 뒤 정규화합니다. 반복 저장·재실행 시에는 이미 보존된 원래 값을 덮어쓰지 않습니다.

판정 근거: [청주시 공식 조직도](https://www.cheongju.go.kr/www/contents.do?key=7431), [2026-08-10 조직개편 심의 기록](https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=3980), [재난안전실 업무 보고](https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=3847). 확인일은 `2026-10-24`이며, 재수집만으로 이 기준일이나 조직개편 판단이 자동 갱신되지는 않습니다.

## 자주 묻는 민원 — `자주_묻는_민원.json`

시청에서 안내하는 자주 묻는 민원 **94건**과 업무별 상세 내용을 담습니다. 최상위 구조는 **분야 코드와 민원 배열을 연결한 객체**이며, 14개 분야 키가 있습니다. 각 민원은 한 분야에 속합니다.

| 필드 | 자료형 | 의미 |
| --- | --- | --- |
| `id` | 숫자 | 사이트 목록에 표시된 번호입니다. 갱신 시 고정 식별자로 사용하지 않습니다. |
| `major` | 문자열 | 대분류 분야의 한글 이름입니다. |
| `medium` | 문자열 | 중분류입니다. |
| `minor` | 문자열 | 소분류입니다. |
| `title` | 문자열 | 업무명 또는 민원 제목입니다. |
| `detail` | 객체 | 업무 안내 상세 항목입니다. |
| `detail.main_content` | 문자열 | 주요 내용, 신청 방법, 구비 서류 등입니다. |
| `detail.received_by` | 문자열 | 접수처입니다. 확인된 동일 부서 표기는 아래 규칙으로 통일합니다. |
| `detail.received_by_original` | 문자열 | 이번 정규화 직전 접수처 표기입니다. 이후 새 수집 항목은 사이트 표기를 보존합니다. |
| `detail.target` | 문자열 | 대상자입니다. |
| `detail.processing_period` | 문자열 | 처리 기간입니다. |
| `detail.warnings` | 문자열 | 유의사항입니다. |
| `source_id` | 문자열 | 상세 페이지의 `no` 값입니다. |
| `registered_date` | 문자열 또는 `null` | 상세 페이지에 표시된 `등록일`입니다. 원문 수정일은 아닙니다. |
| `source_url` | 문자열 | 청주톡톡의 해당 자주 묻는 민원 상세 페이지입니다. |
| `retrieved_at` | 문자열 | 상세 페이지를 확인한 시각입니다. ISO 8601 UTC 형식입니다. |

이전에 대중교통과 접수처 **2건**을 통일했고, 이번에는 기업지원과 2건·균형건설과 4건·공동주택과 2건·공원관리과·건축디자인과·지적정보과·관광과·민원과 각 1건, 총 **13건**의 부서 표기를 추가 정리했습니다. 원래 접수처는 `received_by_original`에 보존합니다. 기존 대중교통과 2건은 이미 정리된 값을 보존하며, 이후 재수집부터 사이트의 원래 표기를 기록합니다.

접수처는 단일 부서뿐 아니라 온라인·팩스·방문 경로와 여러 접수기관을 포함할 수 있습니다. 건축허가의 층수·연면적 조건과 팀명·전화번호·다른 접수처는 유지하고 확인된 부서명만 바꿉니다. 접수처 전체 문구가 등록된 규칙과 일치할 때만 적용하므로, 사이트 문구가 달라지면 다시 검토해야 합니다. 이번 작업은 부서 표기 정리이며 FAQ의 정책 내용·연락처·접수팀의 현행성을 모두 확인한 것은 아닙니다. `안전정책과` 접수 안내도 업무별 재확인 대상입니다.

최상위 분야 코드와 사이트 대분류의 대응은 다음과 같습니다.

| JSON 키 | 대분류 | JSON 키 | 대분류 |
| --- | --- | --- | --- |
| `invest` | 경제투자 | `transport` | 교통 |
| `farming` | 농업정책 | `road` | 도로 |
| `cityRealty` | 도시부동산 | `MCST` | 문화체육관광 |
| `PHC` | 보건소 | `WE` | 복지교육 |
| `tax` | 세무 | `WaterSupply` | 수도사업 |
| `CarRegister` | 차량등록 | `AS` | 행정지원 |
| `Environment` | 환경 | `etc` | 기타 |

구조 예시(일부 필드 생략, 본문은 설명용으로 축약):

```json
{
  "invest": [
    {
      "id": 31,
      "major": "경제투자",
      "medium": "경제정책",
      "minor": "기타",
      "title": "협동조합 설립(변경, 해산) 신고",
      "detail": {
        "main_content": "신고 절차와 구비 서류 안내",
        "received_by": "재정경제국 기업지원과",
        "received_by_original": "기업지원과",
        "target": "협동조합 이사장, 이사 또는 조합원",
        "processing_period": "설립 신고: 20일",
        "warnings": ""
      },
      "source_id": "1303380",
      "registered_date": "2023-04-04",
      "source_url": "https://toktalk.cheongju.go.kr/home/sub.do?menukey=7403&mode=view&no=1303380",
      "retrieved_at": "2026-10-24T04:42:25+00:00"
    }
  ],
  "transport": []
}
```

요청에 따라 `시정일반`은 수집 대상에서 제외했습니다. 해당 분야에 현재 항목이 없으면 `etc`처럼 빈 배열(`[]`)로 남습니다. 상세 항목에 사이트 값이 없으면 빈 문자열로 기록됩니다. `main_content`의 원문 문단·줄바꿈은 가능한 범위에서 보존합니다.

## 갱신 및 수집 코드

- [`PACKET/scrape_faq.py`](../PACKET/scrape_faq.py): 자주 묻는 민원을 사이트에서 전건 수집해 이 폴더의 JSON을 갱신합니다.
- [`PACKET/scrape_public_cases.py`](../PACKET/scrape_public_cases.py): 공개 민원사례를 수집합니다. 공통 요청·HTML 표 파서는 `scrape_faq.py`에서 가져옵니다.
- [`PACKET/department_normalization.py`](../PACKET/department_normalization.py): 두 수집기가 사용하는 공통 부서 규칙입니다. 원래 표기 보존, 현재 부서 대조, 검토 필요 판정을 처리합니다.
- `PACKET/*.saz`: 수집 코드 작성에 참고한 HTTP 요청·응답 캡처입니다. 실행 시에는 캡처를 재생하지 않고 실제 HTTPS 요청을 보냅니다.

프로젝트 루트에서 실행합니다. 기존 파일은 수집이 완료된 뒤 교체하며, 공개 민원 수집 중에는 `.partial` 파일에 진행 상황을 저장합니다.

```bash
python3 PACKET/scrape_faq.py
python3 PACKET/scrape_public_cases.py
```

공개 민원사례 수집기는 매번 전체 목록을 확인하고 `source_id`로 게시물을 식별합니다. 기본 모드에서는 새 게시물의 상세만 요청하고 목록에서 사라진 게시물은 결과에서 제외합니다. 기존 게시물의 답변 수정까지 반영하려면 `--refresh-all`로 모든 상세 페이지를 다시 확인합니다. 전체 수집은 사이트에 많은 요청을 보내므로 `--delay`, `--workers`, `--timeout` 옵션을 상황에 맞게 조정할 수 있습니다.

```bash
python3 PACKET/scrape_public_cases.py --refresh-all
```

사이트를 다시 수집하지 않고 기존 두 JSON에 현재 등록된 정규화 규칙만 적용할 수도 있습니다. 반복 실행해도 원래 표기는 보존됩니다.

```bash
python3 PACKET/department_normalization.py
```

각 게시물의 원문 URL은 답변의 출처 표시와 검증에 활용할 수 있습니다. 다만 FAQ의 `registered_date`와 민원 사례의 `complaint_date`만으로 내용의 최신성을 보증할 수 없으므로, 실제 서비스에서는 원문 재확인과 지식베이스 승인·갱신 절차가 필요합니다.

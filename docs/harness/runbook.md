# 실행·갱신·복구 절차

기준: 2026-10-24, 저장소 루트에서 실행. 최초 설치는 [RAG 실행 문서](../../rag/README.md)를 따른다. 현재 서비스는 검색 전용이며 담당자 인계 기능은 아직 없다.

## 상태 확인

```bash
docker compose ps
python3 -m rag status
python3 -m rag search '시내버스 분실물 문의' --collection faq --no-rerank
```

DB는 기본 `127.0.0.1:55432`, API는 `127.0.0.1:8007`이다. Compose 프로젝트 이름은 `cheongju-rag`다. 상태 응답의 건수와 색인 설정을 확인하고, HTTP 성공만으로 검색 품질까지 정상이라고 판단하지 않는다.

| 저장 위치 | 역할 | 복구 시 의미 |
| --- | --- | --- |
| `db/*.json` | 수집·정규화한 원본 | 데이터 기준점; Git 이력과 별도 백업 활용 |
| `.rag-data/postgres/` | 실제 DB | 직접 삭제·복사로 초기화하지 않음 |
| `.rag-cache/` | 모델과 임베딩 체크포인트 | 재사용 가능하나 삭제하면 다운로드·계산 비용 발생 |
| `.env` | DB 비밀번호와 로컬 설정 | Git·로그에 포함하지 않음 |

다른 프로젝트의 컨테이너·GPU·디렉터리는 건드리지 않는다. `docker system prune`처럼 호스트 전체를 정리하는 명령은 이 프로젝트의 복구 절차가 아니다.

## 변경 전 백업

데이터 갱신·스키마 변경 전에는 일치하는 코드 버전·원본·DB를 보관한다. 아래는 **필요할 때 실행할 명령**이며 문서 작성 시 백업을 실행했다는 뜻이 아니다. 원본 갱신과 적재, 수동 부서 편집이 진행 중이지 않을 때 수행한다.

```bash
umask 077
RAG_BACKUP_DIR=".rag-data/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RAG_BACKUP_DIR"
git rev-parse HEAD > "$RAG_BACKUP_DIR/code-commit.txt"
git status --short > "$RAG_BACKUP_DIR/worktree-status.txt"
cp db/자주_묻는_민원.json db/공개_민원_사례.json "$RAG_BACKUP_DIR/"
sha256sum db/자주_묻는_민원.json db/공개_민원_사례.json > "$RAG_BACKUP_DIR/source-sha256.txt"
docker compose exec -T postgres pg_dump -U complaint -d complaints -Fc > "$RAG_BACKUP_DIR/complaints.dump"
test -s "$RAG_BACKUP_DIR/complaints.dump"
docker compose exec -T postgres pg_restore --list < "$RAG_BACKUP_DIR/complaints.dump" > "$RAG_BACKUP_DIR/archive-list.txt"
```

각 명령의 성공을 확인한다. 미커밋 변경이 있다면 커밋 번호만으로 코드를 복원할 수 없으므로 해당 변경도 별도로 보존한다. 백업은 Git에서 제외된 로컬 경로에 놓이며 아직 자동 주기 백업·보존 기간·외부 보관은 구성하지 않았다. 파일 존재와 목록 조회는 실제 복원 성공을 보장하지 않는다.

## 원본 갱신과 재적재

1. 백업 후 필요한 수집기·정규화기만 실행한다. [데이터 사전](../../db/README.md)의 기본 수집과 `--refresh-all` 차이를 따른다.
2. 추가·삭제 ID, 부서 변화, FAQ 조건·출처 보존을 검토한다. 부분 수집 결과나 크게 줄어든 원본을 바로 적재하지 않는다.
3. 아래 순서로 API를 정지하고 적재·검증한다. 실패하면 원인을 확인하기 전에 다음 단계로 진행하지 않는다.

```bash
docker compose stop rag
docker compose run --rm rag ingest
docker compose run --rm --no-deps --entrypoint python rag -m rag.verify
docker compose up -d --wait rag
python3 -m rag status
```

검색에 영향을 준 변경이면 [검색 회귀 평가](evaluation.md)까지 확인한다. API와 적재 프로세스에 모델을 동시에 올리지 않아 메모리 중복 사용을 줄이는 순서다. 개발용 API가 중단되므로 기존 요청이 없는 때 실행한다.

| 변경 | 적재 방식 |
| --- | --- |
| 원문·메타데이터만 갱신 | 일반 `ingest`; 본문 해시가 같은 벡터는 재사용 |
| 임베딩 모델·리비전·본문 구성 버전 변경 | 버전 변경과 `ingest --reembed`; 전체 벡터 재생성 |
| Kiwi 규칙·토크나이저 버전 변경 | 버전 갱신 후 재적재로 BM25 재구성. 임베딩 서명이 같으면 일반 `ingest`로 벡터 재사용 가능 |
| 재정렬 모델만 변경 | 임베딩 재생성 불필요; 모델 리비전·검색 품질 평가 후 API 재시작 |

`check_index`의 불일치 메시지는 `--reembed`를 안내한다. 실제 변경이 토크나이저만인지, 임베딩 서명도 바뀌었는지 확인해 위 범위를 적용한다. 데이터 적재가 실패하면 기존 검색 스냅샷은 유지되지만, 변경한 코드와 기존 색인이 호환되는지도 확인해야 API를 다시 시작할 수 있다.

## 장애 확인 순서

```bash
docker compose logs --tail 100 rag postgres
docker compose run --rm --no-deps rag status --direct
```

| 증상 | 확인·처리 |
| --- | --- |
| API 연결 안 됨 | `compose ps`, 시작 로그, 모델 다운로드, 포트 확인 |
| 색인 없음·버전 불일치 | 원본과 코드 버전을 대조한 뒤 필요한 적재 수행 |
| 메모리 부족·컨테이너 종료 | 중복 적재/모델 프로세스 여부와 이 프로젝트의 메모리 상한 확인 |
| 요청 지연 | 재정렬 여부, 동시 요청, CPU 한도 확인; `--no-rerank`는 비교 실험으로 사용 |
| 부서 후보 없음 | 검토 대상 부서인지 확인. 이름을 임의로 채워 우회하지 않음 |
| 검색/DB 실패 | 오류를 그대로 기록; 아직 없는 담당자 인계가 실행됐다고 보고하지 않음 |

`status --direct`는 DB 메타데이터 조회이며 API 준비 완료 검사를 대신하지 않는다. 진단 시 `docker compose config` 전체 출력이나 `.env` 출력으로 비밀번호를 노출하지 않는다. 로그 공유 전 민원 내용·자격 증명 포함 여부를 확인한다.

## 복구 원칙

수집만 실패했다면 완료된 원본이 교체됐는지 확인하고 이전 원본을 보존한다. 적재 트랜잭션이 실패했다면 기존 DB 스냅샷과 실행 코드의 호환성을 확인한다. 적재가 이미 완료된 뒤 잘못된 데이터임을 발견했다면 이전 원본으로 재적재할 수 있지만, 삭제된 부서의 수동 업무분장 정보까지 복원되지는 않을 수 있다.

DB 백업이 필요한 복구는 먼저 **새 임시 DB**에 복원하고 테이블·건수·부서 검증 정보를 대조한다. 운영 DB에 곧바로 `--clean`을 실행하지 않는다. 백업과 같은 원본·코드의 별도 작업 환경에서 `rag.verify` 및 검색을 확인한 뒤 서비스 연결 변경을 진행한다. 현재 기본 Compose의 DB 이름은 `complaints`로 고정되어 있으므로 별도 복원 DB로의 연결은 Compose 설정까지 함께 준비해야 한다.

아직 자동 복원 명령·복원 연습·복구 시간 목표는 없다. 원본으로 재생성하는 경로와 수동 보완 정보까지 보존하는 DB 복구 경로를 모두 확인하는 작업을 [후속 계획](../../plan/harness-roadmap.md)에 둔다.

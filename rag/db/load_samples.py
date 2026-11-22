#!/usr/bin/env python3
"""샘플 JSON 8개를 `complaint_app` 스키마 테이블 8개에 적재하는 스크립트입니다.

한눈에 보기:
    - `json` 폴더의 JSON 파일을 읽어 외래 키 순서대로 단일 트랜잭션으로 삽입합니다.
    - `--create --sql sql/02_complaint_app.sql`로 테이블 생성, `--reset`으로 초기화 재적재,
      `--map-departments`로 `complaint_rag.department_directory` 부서 번호 연결을 지원합니다.
"""
# =====================================================================
# 적재 순서(외래 키 참조 기준):
#   사용자(users) → 민원(complaints) → 작업(ai_jobs) → 결과(ai_results)
#   → 대화(messages) → 버전(message_versions) → 이력(job_events → complaint_events)
# 순환 참조 3곳은 처음에 비워 두고 모두 넣은 뒤 보완:
#   작업 결과(ai_jobs.result_id), 채택 버전(ai_results.adopted_version_id),
#   게시 버전(messages.published_version_id)
# 자동 번호 칸(GENERATED ALWAYS)은 OVERRIDING SYSTEM VALUE 후 시퀀스를 재설정합니다.
# =====================================================================
import argparse
import json
import os
import re
import sys

import psycopg2
from psycopg2.extras import Json

SCHEMA = "complaint_app"

# (테이블 이름, 나중에 채울 칸 목록) 을 넣는 순서대로 적었다.
#   - 나중에 채울 칸은 첫 입력 때 NULL 로 두고, 마지막에 UPDATE 한다.
TABLES = [
    ("users", []),
    ("complaints", []),
    ("ai_jobs", ["result_id"]),
    ("ai_results", ["adopted_version_id"]),
    ("messages", ["published_version_id"]),
    ("message_versions", []),
    ("job_events", []),
    ("complaint_events", []),
]

# JSON 안의 목록/객체를 그대로 저장하는 칸(jsonb). 글자로 바꿔서 넣어야 한다.
JSONB_COLUMNS = {
    "ai_results": {"evidence"},
    "message_versions": {"evidence_snapshot"},
}

IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def ident(name):
    """SQL 식별자가 영문 소문자·숫자·밑줄 규칙만 따르는지 검증합니다.

    Args:
        name: 검증할 테이블·컬럼 식별자 문자열입니다.

    Returns:
        검증을 통과한 식별자 문자열입니다.

    Raises:
        ValueError: 허용되지 않은 문자가 포함된 경우 발생합니다.
    """
    if not IDENT.match(name):
        raise ValueError("허용하지 않는 이름: %r" % name)
    return name


def load_json(json_dir, table):
    """테이블별 샘플 JSON 파일을 읽어 `id` 오름차순으로 정렬해 반환합니다.

    Args:
        json_dir: JSON 파일들이 들어 있는 디렉터리 경로입니다.
        table: 확장자를 제외한 대상 테이블 이름입니다.

    Returns:
        `id` 오름차순으로 정렬된 행 딕셔너리 목록입니다.
    """
    path = os.path.join(json_dir, table + ".json")
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    # id 순서대로 넣는다. (같은 테이블 안에서 앞 번호를 가리키는 경우가 있어서)
    rows.sort(key=lambda r: r["id"])
    return rows


def insert_rows(cur, table, rows, deferred):
    """지정한 테이블에 샘플 행을 삽입합니다(`deferred` 컬럼은 우선 `NULL` 처리).

    Args:
        cur: 활성 PostgreSQL 트랜잭션 커서입니다.
        table: 대상 테이블 이름입니다.
        rows: 삽입할 행 딕셔너리 목록입니다.
        deferred: 순환 참조 방지를 위해 삽입 시 `NULL`로 비워 둘 컬럼 집합입니다.
    """
    if not rows:
        return
    cols = [ident(c) for c in rows[0].keys()]
    jsonb_cols = JSONB_COLUMNS.get(table, set())
    sql = "INSERT INTO %s.%s (%s) OVERRIDING SYSTEM VALUE VALUES (%s)" % (
        SCHEMA, table, ", ".join(cols), ", ".join(["%s"] * len(cols)))
    for r in rows:
        vals = []
        for c in cols:
            v = r.get(c)
            if c in deferred:
                v = None                      # 나중에 채울 칸
            elif c in jsonb_cols and v is not None:
                v = Json(v, dumps=lambda o: json.dumps(o, ensure_ascii=False))
            vals.append(v)
        cur.execute(sql, vals)


def fill_deferred(cur, table, col, rows):
    """순환 외래 키 때문에 비워 둔 후속 참조 컬럼 값을 `UPDATE`로 채웁니다.

    Args:
        cur: 활성 PostgreSQL 트랜잭션 커서입니다.
        table: 대상 테이블 이름입니다.
        col: 값을 채울 컬럼 이름입니다.
        rows: 원본 JSON 행 딕셔너리 목록입니다.

    Returns:
        실제로 값을 갱신한 행 건수입니다.
    """
    n = 0
    for r in rows:
        if r.get(col) is not None:
            cur.execute("UPDATE %s.%s SET %s = %%s WHERE id = %%s" % (SCHEMA, table, ident(col)),
                        (r[col], r["id"]))
            n += 1
    return n


def fix_sequences(cur):
    """모든 테이블의 자동 증가 시퀀스를 현재 최대 `id` 다음 값으로 맞춥니다.

    Args:
        cur: 활성 PostgreSQL 트랜잭션 커서입니다.
    """
    for table, _ in TABLES:
        cur.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM %s.%s"
                    % ("'%s.%s'" % (SCHEMA, table), SCHEMA, table))


def map_departments(cur):
    """`ai_results.department_name`을 검색 DB 부서 사전의 `department_id`와 연결합니다.

    1순위로 정확 일치를 찾고, 2순위로 끝부분이 일치하며 후보가 1곳뿐인 경우를 연결합니다.

    Args:
        cur: 활성 PostgreSQL 트랜잭션 커서입니다.
    """
    cur.execute("SELECT to_regclass('complaint_rag.department_directory')")
    if cur.fetchone()[0] is None:
        print("  complaint_rag.department_directory 가 없어 부서 연결을 건너뜀")
        return
    cur.execute("SELECT id, department_name FROM %s.ai_results WHERE department_name IS NOT NULL" % SCHEMA)
    targets = cur.fetchall()
    ok, miss = 0, []
    for rid, name in targets:
        cur.execute("SELECT department_id FROM complaint_rag.department_directory WHERE canonical_name = %s", (name,))
        found = cur.fetchall()
        if len(found) != 1:
            cur.execute("SELECT department_id FROM complaint_rag.department_directory "
                        "WHERE canonical_name LIKE %s", ("%" + name,))
            found = cur.fetchall()
        if len(found) == 1:
            cur.execute("UPDATE %s.ai_results SET department_id = %%s WHERE id = %%s" % SCHEMA,
                        (found[0][0], rid))
            ok += 1
        else:
            miss.append((rid, name, len(found)))
    print("  부서 번호 연결: %d건 성공, %d건 실패" % (ok, len(miss)))
    for rid, name, n in miss:
        print("    - ai_results.id=%d '%s' (후보 %d곳)" % (rid, name, n))


def main():
    """CLI 인자를 해석해 샘플 8개 JSON을 `complaint_app` 스키마에 적재·검증합니다."""
    ap = argparse.ArgumentParser(description="샘플 JSON 8개를 complaint_app 테이블에 넣는다.")
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="DB 접속 문자열 (또는 환경 변수 DATABASE_URL)")
    ap.add_argument("--json-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples"), help="JSON 파일이 있는 폴더 (기본 rag/db/samples)")
    ap.add_argument("--create", action="store_true", help="--sql 파일을 먼저 실행해 테이블을 새로 만든다")
    ap.add_argument("--sql", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "sql", "02_complaint_app.sql"), help="--create 때 실행할 SQL 파일 (기본 rag/db/sql/02_complaint_app.sql)")
    ap.add_argument("--reset", action="store_true", help="이미 들어 있는 데이터를 모두 지우고 다시 넣는다")
    ap.add_argument("--map-departments", action="store_true", help="ai_results.department_id 를 부서 이름으로 연결한다")
    args = ap.parse_args()
    if not args.dsn:
        sys.exit("접속 정보가 없습니다. --dsn 또는 DATABASE_URL 을 주세요.")

    conn = psycopg2.connect(args.dsn)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        if args.create:
            print("테이블 만들기:", args.sql)
            with open(args.sql, encoding="utf-8") as f:
                cur.execute(f.read())
            cur.execute("SET search_path TO public")   # SQL 안의 search_path 변경을 되돌린다

        cur.execute("SELECT to_regclass(%s)", ("%s.users" % SCHEMA,))
        if cur.fetchone()[0] is None:
            sys.exit("complaint_app 테이블이 없습니다. rag/db/sql/02_complaint_app.sql 을 먼저 실행하거나 --create 를 쓰세요.")

        if args.reset:
            print("기존 데이터 삭제")
            # 서로 가리키는 칸이 있어서 한꺼번에 지운다. (번호표도 1부터 다시)
            cur.execute("TRUNCATE %s RESTART IDENTITY" % ", ".join("%s.%s" % (SCHEMA, t) for t, _ in TABLES))
        else:
            cur.execute("SELECT COUNT(*) FROM %s.users" % SCHEMA)
            if cur.fetchone()[0] > 0:
                sys.exit("이미 데이터가 있습니다. 지우고 다시 넣으려면 --reset 을 쓰세요.")

        data = {}
        print("입력 시작")
        for table, deferred in TABLES:
            rows = load_json(args.json_dir, table)
            data[table] = rows
            insert_rows(cur, table, rows, set(deferred))
            print("  %-18s %3d건" % (table, len(rows)))

        print("서로 가리키는 칸 채우기")
        for table, deferred in TABLES:
            for col in deferred:
                n = fill_deferred(cur, table, col, data[table])
                print("  %s.%s %d건" % (table, col, n))

        fix_sequences(cur)

        if args.map_departments:
            print("부서 번호 연결")
            map_departments(cur)

        # 입력한 건수가 JSON 건수와 같은지 확인한다.
        print("확인")
        for table, _ in TABLES:
            cur.execute("SELECT COUNT(*) FROM %s.%s" % (SCHEMA, table))
            n = cur.fetchone()[0]
            if n != len(data[table]):
                raise RuntimeError("%s 건수 불일치: DB %d, JSON %d" % (table, n, len(data[table])))
        print("  모든 테이블 건수가 JSON과 같음")

        conn.commit()
        print("완료 (저장됨)")
    except Exception:
        conn.rollback()
        print("오류가 나서 모두 취소했습니다. (아무것도 저장되지 않음)")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# =====================================================================
# load_samples.py
# 샘플 JSON 8개를 complaint_app 스키마의 테이블 8개에 넣는 스크립트
#
# 한눈에 보기
#   - 하는 일 : json 폴더의 JSON 파일을 읽어 DB에 순서대로 넣는다.
#   - 먼저 필요한 것 : 02_complaint_app.sql 을 실행해 테이블을 만들어 둔 DB
#                      (이 스크립트의 --create 옵션으로 같이 실행할 수도 있다.)
#   - 한 번에 처리한다(트랜잭션 1개). 중간에 오류가 나면 아무것도 들어가지 않는다.
#
# 사용 방법 (예)
#   - 접속 정보는 --dsn 또는 환경 변수 DATABASE_URL 로 준다.
#       python3 load_samples.py --dsn "postgresql://사용자:비밀번호@주소:5432/DB이름" --json-dir ./json
#   - 테이블을 새로 만들고 넣기 :  --create --sql 02_complaint_app.sql
#   - 이미 들어 있는 데이터를 지우고 다시 넣기 : --reset
#   - 부서 번호까지 연결하기 (complaint_rag 가 있는 DB) : --map-departments
#
# 넣는 순서가 정해져 있는 이유
#   - 서로 가리키는 칸(외래 키)이 있어서, 가리키는 행이 먼저 있어야 한다.
#       users -> complaints -> ai_jobs -> ai_results -> messages -> message_versions
#       -> job_events -> complaint_events
#   - 서로를 가리키는 3곳은 처음에 비워 두고, 모두 넣은 뒤에 값을 채운다.
#       ai_jobs.result_id, ai_results.adopted_version_id, messages.published_version_id
#
# 자동 번호 칸(GENERATED ALWAYS)
#   - id 를 JSON에 적어 둔 값 그대로 넣어야 서로 가리키는 번호가 맞는다.
#     그래서 INSERT 에 OVERRIDING SYSTEM VALUE 를 쓴다.
#   - 다 넣은 뒤 자동 번호가 이어서 커지도록 번호표(시퀀스)를 맞춘다.
#     (안 맞추면 나중에 새 민원을 넣을 때 번호가 겹쳐 오류가 난다.)
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
    # 칸 이름이 영문 소문자와 밑줄뿐인지 검사한다. (SQL에 이름을 직접 붙이므로 안전 확인)
    if not IDENT.match(name):
        raise ValueError("허용하지 않는 이름: %r" % name)
    return name


def load_json(json_dir, table):
    path = os.path.join(json_dir, table + ".json")
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    # id 순서대로 넣는다. (같은 테이블 안에서 앞 번호를 가리키는 경우가 있어서)
    rows.sort(key=lambda r: r["id"])
    return rows


def insert_rows(cur, table, rows, deferred):
    # 한 테이블의 모든 행을 넣는다. deferred 칸은 NULL 로 넣는다.
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
    # 처음에 비워 둔 칸을 JSON 값으로 채운다.
    n = 0
    for r in rows:
        if r.get(col) is not None:
            cur.execute("UPDATE %s.%s SET %s = %%s WHERE id = %%s" % (SCHEMA, table, ident(col)),
                        (r[col], r["id"]))
            n += 1
    return n


def fix_sequences(cur):
    # 자동 번호표를 현재 가장 큰 id 다음 값으로 맞춘다.
    for table, _ in TABLES:
        cur.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM %s.%s"
                    % ("'%s.%s'" % (SCHEMA, table), SCHEMA, table))


def map_departments(cur):
    # ai_results.department_name 을 complaint_rag.department_directory 의 부서 번호로 연결한다.
    #   1순위 : 부서 이름이 정확히 같은 경우
    #   2순위 : 이름 끝부분이 같고 후보가 1곳뿐인 경우 (예: "청주시 흥덕구 건설과" 와 "흥덕구 건설과")
    # 연결 못 한 것은 NULL 로 두고 목록을 출력한다. (사람이 확인)
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
    ap = argparse.ArgumentParser(description="샘플 JSON 8개를 complaint_app 테이블에 넣는다.")
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="DB 접속 문자열 (또는 환경 변수 DATABASE_URL)")
    ap.add_argument("--json-dir", default="./json", help="JSON 파일이 있는 폴더 (기본 ./json)")
    ap.add_argument("--create", action="store_true", help="--sql 파일을 먼저 실행해 테이블을 새로 만든다")
    ap.add_argument("--sql", default="02_complaint_app.sql", help="--create 때 실행할 SQL 파일")
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
            sys.exit("complaint_app 테이블이 없습니다. 02_complaint_app.sql 을 먼저 실행하거나 --create 를 쓰세요.")

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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_explain.py — Tier3 실 DB EXPLAIN 실행기 (MySQL/MariaDB/PostgreSQL)

재구성된 SELECT를 개발/로컬 DB에 EXPLAIN(비실행)으로 던져 실행계획을 얻는다.
**어떤 경우에도 db_guard를 먼저 통과해야만** 실행 단계로 진입한다.

의존성 정책(중요): 기본 사용(Tier1/Tier2)에는 DB 드라이버가 전혀 필요 없다. 이 스크립트는
Tier3(--db, opt-in)에서만 쓰인다. 단 Tier3 진입 시 설정(.query-inspector.yml) 파싱에
**PyYAML이 필요**하며(db_guard.load_config가 사용; 없으면 종료코드 2), 실제 EXPLAIN 실행은
다음 순서로 동작한다.
  1) 드라이버가 있으면 드라이버로(MySQL/MariaDB=pymysql, PostgreSQL=psycopg/psycopg2),
  2) 없으면 이미 설치된 CLI로(MySQL=`mysql`, PostgreSQL=`psql`; 추가 설치 불필요),
  3) 둘 다 없으면 실행하지 않고 Tier2로 강등하라고 안내(종료코드 3).

가드레일:
  - db_guard.evaluate() 미통과 → 즉시 중단(EXPLAIN 시도조차 안 함).
  - EXPLAIN(비실행)이 기본. EXPLAIN ANALYZE(실제 실행)는 프로파일 allow_explain_analyze=true
    + --analyze 일 때만, 드라이버 경로에서 트랜잭션을 열고 **무조건 롤백**.
  - statement timeout(max_execution_time) 적용. DML/DDL은 db_guard가 이미 차단.

접속 URL 형식(환경변수로만): mysql:// 또는 postgresql://user:pass@host:port/db  (jdbc: 접두는 자동 제거)

사용법:
  python3 scripts/run_explain.py --profile docker --config .query-inspector.yml \
      --sql-file /tmp/q.sql [--analyze]

종료 코드: 0=성공, 1=가드레일 차단, 2=입력/설정 오류, 3=드라이버·CLI 없음(Tier2 강등).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse, unquote, quote

# Windows 콘솔(cp949 등)에서도 한국어 출력이 깨지지 않게 UTF-8로 고정.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")           # Python 3.7+
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_guard  # noqa: E402


# --------------------------------------------------------------------------
def parse_url(url: str, default_port: int = 3306) -> dict:
    if url.startswith("jdbc:"):
        url = url[5:]
    try:
        u = urlparse(url)
        port = u.port or default_port
    except ValueError:
        # password에 raw 예약문자(#, @, / 등)가 들어와 netloc/port 파싱이 깨진 경우
        raise SystemExit(
            "접속 URL 파싱 실패: password의 예약문자(#, @, /, : 등)를 percent-encoding 하세요"
            " (예: # → %23, @ → %40, ! → %21). `set_db_credential.py`로 저장하면 자동 인코딩됩니다.")
    # urlparse는 컴포넌트를 디코딩하지 않으므로, 실제 접속값으로 unquote 한다.
    return {"host": u.hostname or "127.0.0.1", "port": port,
            "user": unquote(u.username or ""), "password": unquote(u.password or ""),
            "db": unquote((u.path or "").lstrip("/"))}


def _resolve_placeholder(v):
    """`${ENV}` 또는 `${ENV:default}` 형태면 환경변수로 치환한다."""
    if not v or not isinstance(v, str):
        return v
    m = re.fullmatch(r"\$\{([^:}]+)(?::([^}]*))?\}", v.strip())
    if m:
        return os.environ.get(m.group(1), m.group(2) if m.group(2) is not None else "")
    return v


def parse_datasource(path):
    """프로젝트 datasource 설정(application.yml/.properties)에서 접속 정보를 읽어
    `mysql://user:pass@host:port/db` 형태로 구성한다(값은 이 프로세스 안에서만 다루며 출력하지 않음).

    spring.datasource.{url,username,password}(없으면 spring.r2dbc.*)를 사용하고,
    `${ENV[:default]}` placeholder는 환경변수로 치환한다. 구성 실패 시 None.
    """
    if not path or not os.path.exists(path):
        return None
    raw_url = user = pw = None
    if path.endswith((".yml", ".yaml")):
        try:
            import yaml  # Tier3에서 PyYAML은 이미 필요
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return None
        spring = data.get("spring") or {}
        ds = (spring.get("datasource") or {}) or (spring.get("r2dbc") or {})
        if isinstance(ds, dict):
            raw_url, user, pw = ds.get("url"), ds.get("username"), ds.get("password")
    else:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k.endswith("datasource.url") or k.endswith("r2dbc.url"):
                        raw_url = v
                    elif k.endswith("datasource.username") or k.endswith("r2dbc.username"):
                        user = v
                    elif k.endswith("datasource.password") or k.endswith("r2dbc.password"):
                        pw = v
        except Exception:
            return None
    raw_url = _resolve_placeholder(raw_url)
    user = _resolve_placeholder(user)
    pw = _resolve_placeholder(pw)
    if not raw_url:
        return None
    u = raw_url
    for pre in ("jdbc:", "r2dbc:"):
        if u.startswith(pre):
            u = u[len(pre):]
    m = re.match(r"[a-z0-9]+://([^/?\s]+)(/[^?\s]*)?", u)
    if not m:
        return None
    hostport, path_part = m.group(1), (m.group(2) or "").split("?")[0]
    # user/pass의 예약문자(#, @ 등)를 percent-encode → parse_url이 unquote로 정확히 복원
    cred = ""
    if user:
        cred = quote(user, safe="") + ((":" + quote(pw, safe="")) if pw else "") + "@"
    return f"mysql://{cred}{hostport}{path_part}"


def summarize_mysql_json(raw: str) -> dict:
    """EXPLAIN FORMAT=JSON에서 테이블별 access_type/key/rows/filtered + filesort 플래그 추출."""
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    tables, flags = [], {}

    def walk(o):
        if isinstance(o, dict):
            t = o.get("table")
            if isinstance(t, dict) and "table_name" in t:
                tables.append({"table": t.get("table_name"), "access": t.get("access_type"),
                               "key": t.get("key"), "rows": t.get("rows_examined_per_scan"),
                               "filtered": t.get("filtered")})
            for k, v in o.items():
                if k == "using_filesort" and v:
                    flags["using_filesort"] = True
                if k == "using_temporary_table" and v:
                    flags["using_temporary_table"] = True
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(obj)
    return {"tables": tables, "flags": flags}


def summarize_postgres_json(raw: str) -> dict:
    """EXPLAIN (FORMAT JSON)에서 노드별 Node Type/Relation/Index/rows + Seq Scan/Sort 플래그 추출."""
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    nodes, flags = [], {}

    def walk(plan):
        if not isinstance(plan, dict):
            return
        nt = plan.get("Node Type")
        if nt:
            nodes.append({"node": nt, "table": plan.get("Relation Name"),
                          "index": plan.get("Index Name"), "rows": plan.get("Plan Rows")})
            if nt == "Seq Scan":
                flags["seq_scan"] = True
            if nt in ("Sort", "Incremental Sort"):
                flags["sort"] = True
        for sub in (plan.get("Plans") or []):
            walk(sub)

    root = obj[0] if isinstance(obj, list) and obj else obj
    if isinstance(root, dict):
        walk(root.get("Plan", root))
    return {"tables": nodes, "flags": flags}


# --------------------------------------------------------------------------
def explain_mysql_driver(c: dict, sql: str, timeout_ms: int, analyze: bool, dialect: str = "mysql") -> dict:
    import pymysql  # 지연 import
    conn = pymysql.connect(host=c["host"], port=c["port"], user=c["user"],
                           password=c["password"], database=c["db"],
                           connect_timeout=5, read_timeout=max(5, timeout_ms // 1000 + 3),
                           autocommit=True)
    try:
        cur = conn.cursor()
        try:
            # statement timeout 변수는 방언별로 다르다:
            #   MySQL=max_execution_time(밀리초 정수), MariaDB=max_statement_time(초 double)
            if dialect == "mariadb":
                cur.execute("SET SESSION max_statement_time=%s", (max(0.0, int(timeout_ms) / 1000.0),))
            else:
                cur.execute("SET SESSION max_execution_time=%s", (int(timeout_ms),))
        except Exception:
            pass
        if analyze:
            conn.begin()                                  # 실제 실행 → 무조건 롤백
            try:
                cur.execute("EXPLAIN ANALYZE " + sql)
                raw = "\n".join(str(r[0]) for r in cur.fetchall())
            finally:
                conn.rollback()
            return {"engine": "pymysql", "format": "analyze", "raw": raw}
        cur.execute("EXPLAIN FORMAT=JSON " + sql)
        raw = cur.fetchone()[0]
        return {"engine": "pymysql", "format": "json", "raw": raw,
                "summary": summarize_mysql_json(raw)}
    finally:
        conn.close()


def explain_mysql_cli(c: dict, sql: str, timeout_ms: int, analyze: bool, dialect: str = "mysql") -> dict:
    core = ("EXPLAIN ANALYZE " if analyze else "EXPLAIN FORMAT=JSON ") + sql
    # 드라이버 경로(explain_mysql_driver)와 동작을 일치시킨다:
    #  - statement timeout 적용. 방언별 변수가 다르다: MySQL=max_execution_time(ms 정수),
    #    MariaDB=max_statement_time(초 double). CLI는 prelude 첫 문장이 실패하면 -e 전체가
    #    중단되므로(드라이버처럼 try/except로 무시 불가), 방언에 맞는 변수를 써야 한다.
    #  - EXPLAIN ANALYZE(실제 실행)는 트랜잭션을 열고 무조건 롤백(부작용 방지, 문서 계약)
    if dialect == "mariadb":
        prelude = "SET SESSION max_statement_time=%s; " % (max(0.0, int(timeout_ms) / 1000.0))
    else:
        prelude = "SET SESSION max_execution_time=%d; " % int(timeout_ms)
    stmt = prelude + ("START TRANSACTION; " + core + "; ROLLBACK;" if analyze else core)
    env = dict(os.environ)
    env["MYSQL_PWD"] = c["password"]                       # 비밀번호는 프로세스 인자 대신 env로
    args = ["mysql", "-h", c["host"], "-P", str(c["port"]), "-u", c["user"],
            c["db"], "-N", "-e", stmt]
    proc_timeout = max(5, int(timeout_ms) // 1000 + 3)     # 드라이버 read_timeout과 같은 공식
    p = subprocess.run(args, env=env, capture_output=True, text=True, timeout=proc_timeout)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "mysql CLI 실패")
    raw = p.stdout.strip()
    out = {"engine": "mysql-cli", "format": "analyze" if analyze else "json", "raw": raw}
    if not analyze:
        out["summary"] = summarize_mysql_json(raw)
    return out


def explain_postgres_driver(c: dict, sql: str, timeout_ms: int, analyze: bool) -> dict:
    try:
        import psycopg                                   # psycopg3
        conn = psycopg.connect(host=c["host"], port=c["port"], user=c["user"],
                               password=c["password"], dbname=c["db"], connect_timeout=5)
        drv = "psycopg"
    except ImportError:
        import psycopg2                                  # psycopg2 폴백
        conn = psycopg2.connect(host=c["host"], port=c["port"], user=c["user"],
                                password=c["password"], dbname=c["db"], connect_timeout=5)
        drv = "psycopg2"
    try:
        conn.autocommit = True
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = %d" % int(timeout_ms))
        except Exception:
            pass
        if analyze:
            conn.autocommit = False                       # 실제 실행 → 무조건 롤백
            try:
                cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql)
                raw = json.dumps(cur.fetchone()[0])
            finally:
                conn.rollback()
            return {"engine": drv, "format": "analyze-json", "raw": raw,
                    "summary": summarize_postgres_json(raw)}
        cur.execute("EXPLAIN (FORMAT JSON) " + sql)
        raw = json.dumps(cur.fetchone()[0])
        return {"engine": drv, "format": "json", "raw": raw,
                "summary": summarize_postgres_json(raw)}
    finally:
        conn.close()


def explain_postgres_cli(c: dict, sql: str, timeout_ms: int, analyze: bool) -> dict:
    core = ("EXPLAIN (ANALYZE, FORMAT JSON) " if analyze else "EXPLAIN (FORMAT JSON) ") + sql
    prelude = "SET statement_timeout = %d; " % int(timeout_ms)
    # EXPLAIN ANALYZE(실제 실행)는 트랜잭션을 열고 무조건 롤백(부작용 방지, 문서 계약)
    stmt = prelude + ("BEGIN; " + core + "; ROLLBACK;" if analyze else core)
    env = dict(os.environ)
    env["PGPASSWORD"] = c["password"]                     # 비밀번호는 인자 대신 env로
    args = ["psql", "-h", c["host"], "-p", str(c["port"]), "-U", c["user"],
            "-d", c["db"], "-q", "-t", "-A", "-X", "-c", stmt]
    proc_timeout = max(5, int(timeout_ms) // 1000 + 3)
    p = subprocess.run(args, env=env, capture_output=True, text=True, timeout=proc_timeout)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "psql CLI 실패")
    raw = p.stdout.strip()
    out = {"engine": "psql", "format": "json", "raw": raw}
    if not analyze:
        out["summary"] = summarize_postgres_json(raw)
    return out


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Tier3 EXPLAIN 실행기(가드레일 강제)")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--config", default=".query-inspector.yml")
    ap.add_argument("--sql-file", required=True)
    ap.add_argument("--dialect", default="mysql", choices=["mysql", "mariadb", "postgresql", "oracle", "ansi"])
    ap.add_argument("--analyze", action="store_true", help="EXPLAIN ANALYZE(실제 실행, 롤백). 프로파일 허용 필요")
    ap.add_argument("--source-config", help="접속 정보를 읽을 프로젝트 datasource 설정 파일"
                    "(application.yml/.properties 등). url_env/.env에 URL이 없을 때 폴백으로 사용")
    args = ap.parse_args()

    with open(args.sql_file, "r", encoding="utf-8") as f:
        sql = f.read().strip().rstrip(";")

    config = db_guard.load_config(args.config)
    db_guard.load_dotenv((config.get("db", {}) or {}).get("env_file", ".env"))

    # 접속 URL 확보: 환경변수(url_env) → 없으면 프로젝트 datasource 설정(--source-config).
    # 어느 경로든 아래 db_guard가 프로덕션 차단·읽기전용을 동일하게 검증한다.
    prof = (config.get("db", {}).get("profiles", {}) or {}).get(args.profile, {}) or {}
    url = os.environ.get(prof.get("url_env", ""), "") if prof.get("url_env") else ""
    if not url and args.source_config:
        url = parse_datasource(args.source_config) or ""

    # 1) 가드레일 — 반드시 먼저(소스에서 온 URL도 동일하게 검증)
    verdict = db_guard.evaluate(config, args.profile, sql, dict(os.environ),
                                url_override=(url or None))
    if not verdict.get("allowed"):
        print(json.dumps({"stage": "guard", "blocked": True, "verdict": verdict}, ensure_ascii=False, indent=2))
        sys.stderr.write("차단: db_guard 미통과 — Tier2로 강등하세요.\n")
        return 1

    # 방언 결정 + 미지원 조기 종료(접속 전). ansi(불확실 폴백)는 MySQL로 근사.
    eff_dialect = "mysql" if args.dialect == "ansi" else args.dialect
    _PORTS = {"mysql": 3306, "mariadb": 3306, "postgresql": 5432}
    if eff_dialect not in _PORTS:
        print(json.dumps({"stage": "explain", "implemented": False,
                          "message": f"{args.dialect}는 후속 예정. 현재 MySQL/MariaDB/PostgreSQL 지원."},
                         ensure_ascii=False, indent=2))
        return 3

    c = parse_url(url, _PORTS[eff_dialect])
    # 파서 일치 확인: 접속 호스트(urlparse)와 db_guard가 검사한 호스트(정규식)가 어긋나면 중단.
    # 두 파서가 다른 호스트를 뽑으면 "가드가 통과시킨 호스트 ≠ 실제 접속 호스트"가 되어
    # 프로덕션 차단이 우회될 수 있으므로, 불일치는 조용히 접속하지 않는다.
    guard_hosts = [h.lower() for h in (verdict.get("hosts") or [])]
    if guard_hosts and c["host"].lower() not in guard_hosts:
        print(json.dumps({"stage": "guard", "blocked": True,
                          "reason": f"접속 호스트 '{c['host']}'가 가드 검사 호스트 {guard_hosts}와 불일치 "
                                    "— URL 파싱 불일치로 중단(가드 우회 방지)"},
                         ensure_ascii=False, indent=2))
        sys.stderr.write("차단: 접속 호스트와 가드 검사 호스트 불일치 — Tier2로 강등하세요.\n")
        return 1
    timeout_ms = int(prof.get("statement_timeout_ms", 3000))
    analyze = bool(args.analyze and prof.get("allow_explain_analyze", False))
    if args.analyze and not prof.get("allow_explain_analyze", False):
        sys.stderr.write("경고: 프로파일 allow_explain_analyze=false — ANALYZE 대신 EXPLAIN(비실행) 수행.\n")

    # 2) 드라이버 우선 → CLI 폴백 → 없으면 Tier2 강등 (방언별)
    if eff_dialect in ("mysql", "mariadb"):
        try:
            import pymysql  # noqa: F401
            result = explain_mysql_driver(c, sql, timeout_ms, analyze, eff_dialect)
        except ImportError:
            if shutil.which("mysql"):
                result = explain_mysql_cli(c, sql, timeout_ms, analyze, eff_dialect)
            else:
                print(json.dumps({"stage": "explain", "implemented": True, "ran": False,
                                  "reason": "pymysql·mysql CLI 모두 없음 → Tier2로 강등",
                                  "hint": "pip install pymysql  또는  mysql 클라이언트 설치"},
                                 ensure_ascii=False, indent=2))
                return 3
    else:  # postgresql
        try:
            result = explain_postgres_driver(c, sql, timeout_ms, analyze)
        except ImportError:
            if shutil.which("psql"):
                result = explain_postgres_cli(c, sql, timeout_ms, analyze)
            else:
                print(json.dumps({"stage": "explain", "implemented": True, "ran": False,
                                  "reason": "psycopg·psql 모두 없음 → Tier2로 강등",
                                  "hint": "pip install 'psycopg[binary]'  또는  psql 클라이언트 설치"},
                                 ensure_ascii=False, indent=2))
                return 3

    print(json.dumps({"stage": "explain", "guard_passed": True, "host": c["host"],
                      "analyze": analyze, "result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

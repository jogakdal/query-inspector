#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""db_guard.py — DB 접속 가드레일 (DESIGN.md §7을 코드로 강제)

Tier3(실 DB EXPLAIN)에서 어떤 DB에 어떤 SQL도 던지기 "전에" 반드시 통과해야 하는
검증기. 순수 검증만 하며 DB에 접속하지 않는다(드라이버 불필요).

강제 규칙:
  1. 프로덕션 차단 — 호스트 이름 패턴(denylist) 매칭 시 차단, allowlist 밖이면 차단.
  2. 자격증명 분리 — 접속 URL은 설정의 url_env가 가리키는 환경변수에서만 읽는다.
  3. 읽기 전용 — SELECT/EXPLAIN(+CTE) 외 문장은 차단. EXPLAIN ANALYZE는 프로파일이
     명시 허용할 때만.
  4. 단일 조회 — 복수 문장(세미콜론) 금지(문장 주입 방지).

사용법:
  python3 scripts/db_guard.py --profile dev --config .query-inspector.yml \
      --sql-file /tmp/extracted.sql
  python3 scripts/db_guard.py --self-test        # 내장 단위 테스트 실행

종료 코드: 0=통과, 1=차단(가드레일 위반), 2=설정/입력 오류.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from typing import Optional

# Windows 콘솔(cp949 등)에서도 한국어 출력이 깨지지 않게 UTF-8로 고정.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")           # Python 3.7+
    except Exception:
        pass

DEFAULT_DENY_PATTERNS = ["*prod*", "*production*", "*live*"]

READ_ONLY_STARTS = ("select", "explain", "with", "show", "describe", "desc")
# 본문(서브쿼리/CTE 포함)에 나오면 차단할 쓰기/부작용 키워드.
# 문장 시작 토큰은 READ_ONLY_STARTS 화이트리스트로 이미 통제되므로, 여기서는
# "단일 SELECT/WITH 본문에 섞여 부작용을 낼 수 있는" 키워드만 본다.
# 'comment'(컬럼/별칭 이름)·'replace'(MySQL REPLACE() 문자열 함수)는 본문에서 매우 흔하고,
# 쓰기 문장 형태(COMMENT ON …, REPLACE INTO …)는 문장 시작이면 READ_ONLY_STARTS에 없어
# 어차피 차단되므로 본문 스캔 대상에서 제외한다(정상 조회 과차단 방지).
# 반대로 'outfile'/'dumpfile'은 SELECT … INTO OUTFILE 류 파일 쓰기이므로 본문에서 차단한다.
FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "merge", "drop", "create", "alter",
    "truncate", "grant", "revoke", "call", "exec", "execute",
    "load", "lock", "set", "use", "rename", "flush", "kill",
    "begin", "commit", "rollback", "savepoint", "copy", "vacuum", "analyze",
    "outfile", "dumpfile",
)


# --------------------------------------------------------------------------
# URL → 호스트 추출
# --------------------------------------------------------------------------
def extract_hosts(url: str) -> list[str]:
    """JDBC/R2DBC 접속 URL에서 호스트 목록을 추출한다.

    임베디드(h2/sqlite/derby mem·file)는 빈 목록(안전)으로 본다.
    파싱 실패 시 빈 목록 대신 원문 일부를 넣지 않고, 호출부가 '판별 불가'로 처리한다.
    """
    if not url:
        return []
    u = url.strip()
    low = u.lower()

    # 임베디드 DB — 네트워크 호스트 없음
    if low.startswith(("jdbc:h2:mem", "jdbc:h2:file", "jdbc:sqlite", "jdbc:derby:memory")):
        return []

    # Oracle TNS DESCRIPTION: (HOST=...) 형태 다수 가능
    if "description" in low and "host" in low:
        return [h.strip().lower() for h in re.findall(r"host\s*=\s*([^)\s]+)", u, re.I)]

    # Oracle thin: jdbc:oracle:thin:@//host:port/service  또는  @host:port:sid
    # (?://)? 로 두 슬래시를 통째 옵션 처리 — 슬래시 없는 @host:port:sid 도 매칭.
    m = re.search(r"oracle:thin:@(?://)?([^:/,\s@]+)", low)
    if m:
        return [m.group(1)]

    # 일반: scheme://[user[:pass]@]host[:port][,host2[:port]]...[/db][?..]
    m = re.search(r"//([^/?\s]+)", u)
    if not m:
        return []
    authority = m.group(1)
    if "@" in authority:                      # user:pass@ 제거
        authority = authority.rsplit("@", 1)[1]
    hosts = []
    for part in authority.split(","):          # multi-host
        host = part.split(":", 1)[0].strip().lower()
        if host:
            hosts.append(host)
    return hosts


# --------------------------------------------------------------------------
# 프로덕션 차단 판정
# --------------------------------------------------------------------------
def _is_public_ip(host: str) -> bool:
    """host가 라우팅 가능한 공인 IP면 True. 호스트명·사설/로컬 IP·판정 불가는 False."""
    import ipaddress
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False                       # 호스트명 등 IP 아님 → 공인 단정 불가
    return not (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def check_hosts(hosts: list[str], allowlist: list[str], deny_patterns: list[str],
                prod_guard: bool) -> tuple[bool, list[str]]:
    """호스트 안전성 판정. (allowed, reasons)"""
    reasons: list[str] = []
    if not hosts:
        # 임베디드거나 파싱 실패 — 임베디드는 안전, 파싱 실패는 호출부에서 별도 처리
        return True, ["호스트 없음(임베디드 DB로 간주) 또는 네트워크 미대상"]

    patterns = list(deny_patterns)
    if prod_guard:
        patterns += DEFAULT_DENY_PATTERNS
    patterns = list(dict.fromkeys(p.lower() for p in patterns))  # 중복 제거

    allowed = True
    for host in hosts:
        # denylist 우선 — 하나라도 걸리면 차단
        for pat in patterns:
            if fnmatch.fnmatch(host, pat):
                reasons.append(f"차단: 호스트 '{host}'가 프로덕션 패턴 '{pat}'와 일치")
                allowed = False
        # allowlist 있으면 반드시 포함되어야 함
        if allowlist:
            if not any(fnmatch.fnmatch(host, a.lower()) for a in allowlist):
                reasons.append(f"차단: 호스트 '{host}'가 host_allowlist에 없음")
                allowed = False
        else:
            # allowlist 미설정 + prod_guard: 공인(라우팅 가능) IP는 프로덕션일 수 있어 차단.
            # 사설/로컬 IP·호스트명은 경고만(로컬/개발 환경으로 간주 — IP만으론 프로덕션 단정 불가).
            if prod_guard and _is_public_ip(host):
                reasons.append(f"차단: 호스트 '{host}'가 공인 IP인데 host_allowlist 미설정 — 프로덕션 차단(allowlist에 명시 필요)")
                allowed = False
            else:
                reasons.append(f"경고: host_allowlist 미설정 — 호스트 '{host}' 화이트리스트 권장")
    if allowed and not reasons:
        reasons.append("호스트 안전")
    return allowed, reasons


# --------------------------------------------------------------------------
# SQL 읽기 전용 판정
# --------------------------------------------------------------------------
def _mask_literals(sql: str) -> str:
    """문자열/식별자 리터럴을 공백으로 마스킹(리터럴 내부의 ; -- 오탐 방지).

    백슬래시 이스케이프(`'O\\'Brien'`)와 연속 따옴표(`'it''s'`)를 리터럴 종료로
    오인하지 않는다 — 오인하면 리터럴 뒷부분이 코드로 노출돼 정상 조회가 과차단된다.
    (인덱스 정합을 위해 출력 길이는 입력과 동일하게 유지한다.)
    """
    out = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c in ("'", '"', "`"):
            quote = c
            out.append(" ")            # 여는 따옴표
            i += 1
            while i < n:
                ch = sql[i]
                # 백슬래시 이스케이프(백틱 식별자 제외): 다음 문자를 리터럴 내부로 소비
                if ch == "\\" and quote != "`" and i + 1 < n:
                    out.append("  ")
                    i += 2
                    continue
                # 연속 따옴표 = 이스케이프된 따옴표 → 리터럴 계속
                if ch == quote and i + 1 < n and sql[i + 1] == quote:
                    out.append("  ")
                    i += 2
                    continue
                out.append(" ")
                i += 1
                if ch == quote:        # 닫는 따옴표 → 리터럴 종료
                    break
        else:
            out.append(c)
            i += 1
    return "".join(out)


def strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)   # 블록 주석
    sql = re.sub(r"--[^\n]*", " ", sql)                # 라인 주석
    return sql


def split_statements(sql: str) -> list[str]:
    """세미콜론 기준 문장 분리(리터럴 내 ; 는 무시)."""
    masked = _mask_literals(sql)
    parts, start = [], 0
    for idx, ch in enumerate(masked):
        if ch == ";":
            parts.append(sql[start:idx])
            start = idx + 1
    parts.append(sql[start:])
    return [p.strip() for p in parts if p.strip()]


def check_sql(sql: str, allow_explain_analyze: bool) -> tuple[bool, list[str]]:
    """SQL이 읽기 전용(EXPLAIN/SELECT)인지 검증. (allowed, reasons)"""
    reasons: list[str] = []
    clean = strip_comments(sql)
    statements = split_statements(clean)

    if not statements:
        return False, ["차단: 실행할 SQL 문장이 없음"]
    if len(statements) > 1:
        return False, [f"차단: 복수 문장({len(statements)}개) 감지 — 단일 조회만 허용(문장 주입 방지)"]

    stmt = statements[0]
    low = stmt.lower()
    first = re.split(r"\s+", low, maxsplit=1)[0] if low else ""

    if first not in READ_ONLY_STARTS:
        return False, [f"차단: 문장이 '{first}'로 시작 — SELECT/EXPLAIN 외 실행 금지"]

    # EXPLAIN ANALYZE(실제 실행) 여부
    if first == "explain" and re.search(r"explain\s+(\(.*\banalyze\b|analyze\b)", low):
        if not allow_explain_analyze:
            return False, ["차단: EXPLAIN ANALYZE(실제 실행)는 프로파일 allow_explain_analyze=true일 때만"]
        reasons.append("주의: EXPLAIN ANALYZE — 트랜잭션 후 무조건 롤백 필요(run_explain.py가 강제)")

    # CTE(with)/서브쿼리 안에 숨은 쓰기 키워드 차단(최상위 토큰만으론 부족)
    masked = _mask_literals(low)
    for kw in FORBIDDEN_KEYWORDS:
        if kw in ("analyze",) and allow_explain_analyze:
            continue
        if re.search(r"\b" + re.escape(kw) + r"\b", masked):
            # select/explain 정상 토큰과 겹치지 않는 쓰기 키워드가 본문에 존재
            return False, [f"차단: 쓰기/부작용 키워드 '{kw}' 포함 — 읽기 전용 위반"]

    if not reasons:
        reasons.append("읽기 전용 확인(SELECT/EXPLAIN)")
    return True, reasons


# --------------------------------------------------------------------------
# 설정 로드 & 프로파일 검증
# --------------------------------------------------------------------------
def load_config(path: str) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError:
        sys.stderr.write("오류: PyYAML 필요 — `pip install pyyaml` 후 재시도.\n")
        sys.exit(2)
    if not os.path.exists(path):
        sys.stderr.write(f"오류: 설정 파일 없음: {path}\n")
        sys.exit(2)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_dotenv(path: str = ".env") -> None:
    """.env 파일이 있으면 KEY=VALUE를 os.environ에 주입한다(기존 환경변수가 우선).

    자격증명을 매번 export하기 번거로울 때 .env(gitignore)에 두면 자동으로 읽힌다.
    이미 설정된 환경변수는 덮어쓰지 않는다(셸 주입 > .env).
    """
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.lower().startswith("export "):
                    line = line[7:]
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:            # 셸 env 우선
                    os.environ[k] = v
    except Exception:
        pass


def evaluate(config: dict, profile: str, sql: Optional[str], env: dict,
             url_override: Optional[str] = None) -> dict:
    db = (config or {}).get("db", {}) or {}
    prod_guard = db.get("prod_guard", True)
    profiles = db.get("profiles", {}) or {}
    if profile not in profiles:
        return {"allowed": False, "profile": profile,
                "reasons": [f"차단: 프로파일 '{profile}'가 설정에 없음"], "checks": []}

    p = profiles[profile] or {}
    url_env = p.get("url_env")
    allowlist = p.get("host_allowlist", []) or []
    deny_patterns = p.get("host_denylist_patterns", []) or []
    allow_analyze = p.get("allow_explain_analyze", False)
    readonly = p.get("readonly", True)

    checks: list[dict] = []
    reasons: list[str] = []
    allowed = True

    # 1) 자격증명 확보 — env(url_env) 우선. 없으면 프로젝트 datasource 설정에서 온 url_override.
    #    (프로덕션 차단·읽기전용 등 이후 검증은 출처와 무관하게 동일하게 적용된다.)
    if url_override:
        url = url_override
        checks.append({"name": "credential_separation", "ok": True,
                       "detail": "프로젝트 datasource 설정 파일에서 로드(값은 기록하지 않음)"})
    elif not url_env:
        return {"allowed": False, "profile": profile,
                "reasons": ["차단: 프로파일에 url_env 없음 — 접속 URL은 환경변수 참조 또는 소스 datasource로만 지정"],
                "checks": checks}
    else:
        url = env.get(url_env)
        if not url:
            return {"allowed": False, "profile": profile,
                    "reasons": [f"차단: 환경변수 {url_env} 미설정 — URL을 저장소에 두지 말고 env로 주입"],
                    "checks": checks}
        checks.append({"name": "credential_separation", "ok": True,
                   "detail": f"URL을 환경변수 {url_env}에서 로드"})

    # 2) 호스트 판정
    hosts = extract_hosts(url)
    host_ok, host_reasons = check_hosts(hosts, allowlist, deny_patterns, prod_guard)
    checks.append({"name": "production_guard", "ok": host_ok,
                   "detail": {"hosts": hosts, "reasons": host_reasons}})
    reasons += host_reasons
    allowed = allowed and host_ok

    # 3) 읽기 전용 계정 권장
    if not readonly:
        reasons.append("경고: 프로파일 readonly=false — 읽기 전용 계정 사용을 강력 권장")
    checks.append({"name": "readonly_recommended", "ok": bool(readonly),
                   "detail": f"readonly={readonly}"})

    # 4) SQL 읽기 전용 검증(주어진 경우)
    if sql is not None:
        sql_ok, sql_reasons = check_sql(sql, allow_analyze)
        checks.append({"name": "read_only_sql", "ok": sql_ok, "detail": sql_reasons})
        reasons += sql_reasons
        allowed = allowed and sql_ok

    return {"allowed": allowed, "profile": profile, "hosts": hosts,
            "reasons": reasons, "checks": checks}


# --------------------------------------------------------------------------
# 내장 단위 테스트 (가드레일은 반드시 테스트 — CLAUDE.md 테스트 원칙)
# --------------------------------------------------------------------------
def self_test() -> int:
    failures = []

    def expect(cond, msg):
        if not cond:
            failures.append(msg)

    # 호스트 추출
    expect(extract_hosts("jdbc:mysql://localhost:3306/app") == ["localhost"], "mysql host")
    expect(extract_hosts("jdbc:postgresql://db1:5432,db2:5432/app") == ["db1", "db2"], "pg multi-host")
    expect(extract_hosts("jdbc:oracle:thin:@//ora-host:1521/svc") == ["ora-host"], "oracle //host")
    expect(extract_hosts("jdbc:oracle:thin:@ora2:1521:sid") == ["ora2"], "oracle @host:sid")
    expect(extract_hosts("jdbc:h2:mem:test") == [], "h2 embedded")
    expect(extract_hosts("jdbc:mysql://user:pw@prod-db.internal/app") == ["prod-db.internal"], "userinfo strip")

    # 프로덕션 차단
    ok, _ = check_hosts(["prod-db.internal"], [], [], True)
    expect(not ok, "prod pattern blocks")
    ok, _ = check_hosts(["localhost"], ["localhost"], [], True)
    expect(ok, "allowlist passes localhost")
    ok, _ = check_hosts(["stealth-db"], ["localhost"], [], True)
    expect(not ok, "not-in-allowlist blocks")
    ok, _ = check_hosts(["myhost"], [], ["*internal*"], True)
    expect(ok, "custom deny not matched -> allowed (allowlist empty warns only)")
    # allowlist 미설정 + prod_guard: 공인 IP 차단, 사설/로컬 IP·호스트명은 경고만 통과
    ok, _ = check_hosts(["8.8.8.8"], [], [], True)
    expect(not ok, "public IP blocked when allowlist empty + prod_guard")
    ok, _ = check_hosts(["10.0.0.5"], [], [], True)
    expect(ok, "private IP allowed(warn) when allowlist empty")
    ok, _ = check_hosts(["db-host"], [], [], True)
    expect(ok, "hostname allowed(warn) when allowlist empty")

    # SQL 읽기 전용
    expect(check_sql("SELECT 1", False)[0], "select ok")
    expect(check_sql("EXPLAIN SELECT * FROM t", False)[0], "explain ok")
    expect(not check_sql("UPDATE t SET a=1", False)[0], "update blocked")
    expect(not check_sql("SELECT 1; DROP TABLE t", False)[0], "multi-stmt blocked")
    expect(not check_sql("EXPLAIN ANALYZE SELECT * FROM t", False)[0], "analyze blocked when disallowed")
    expect(check_sql("EXPLAIN ANALYZE SELECT * FROM t", True)[0], "analyze ok when allowed")
    expect(not check_sql("WITH x AS (SELECT 1) INSERT INTO t SELECT * FROM x", False)[0], "cte-insert blocked")
    expect(check_sql("SELECT '; DROP TABLE t --' AS s", False)[0], "literal semicolon not a stmt")
    # 흔한 컬럼/별칭 이름 과차단 방지(문장 시작이 아닌 예약어스러운 식별자)
    expect(check_sql("SELECT comment FROM articles WHERE id = 1", False)[0], "column named 'comment' ok")
    # MySQL REPLACE() 문자열 함수는 정상(REPLACE INTO 쓰기는 문장 시작이라 별도 차단)
    expect(check_sql("SELECT REPLACE(name,'a','b') FROM t WHERE id = 1", False)[0], "REPLACE() function ok")
    expect(not check_sql("REPLACE INTO t VALUES (1)", False)[0], "REPLACE INTO blocked (stmt start)")
    # 파일 쓰기(INTO OUTFILE/DUMPFILE)는 본문에서 차단
    expect(not check_sql("SELECT * FROM t INTO OUTFILE '/tmp/x'", False)[0], "SELECT INTO OUTFILE blocked")
    expect(not check_sql("SELECT * FROM t INTO DUMPFILE '/tmp/x'", False)[0], "SELECT INTO DUMPFILE blocked")
    # 리터럴 이스케이프: 백슬래시/연속 따옴표를 종료로 오인해 뒷부분을 코드로 노출하지 않음
    expect(check_sql("SELECT * FROM t WHERE name = 'O\\'Brien'", False)[0], "backslash-escaped quote literal ok")
    expect(check_sql("SELECT * FROM t WHERE name = 'it''s'", False)[0], "doubled-quote literal ok")
    expect(check_sql("SELECT 'a\\'; DROP TABLE t; --' AS s", False)[0], "escaped quote keeps ; inside literal")

    if failures:
        print("SELF-TEST 실패:")
        for m in failures:
            print("  -", m)
        return 1
    print("SELF-TEST 통과 (모든 가드레일 케이스 OK)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="DB 접속 가드레일 검증기")
    ap.add_argument("--profile", help="검증할 DB 프로파일 이름")
    ap.add_argument("--config", default=".query-inspector.yml", help="설정 파일 경로")
    ap.add_argument("--sql-file", help="검증할 SQL 파일(선택)")
    ap.add_argument("--sql", help="검증할 SQL 인라인(선택)")
    ap.add_argument("--self-test", action="store_true", help="내장 단위 테스트 실행")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if not args.profile:
        ap.error("--profile 이 필요합니다(또는 --self-test).")

    sql = None
    if args.sql_file:
        with open(args.sql_file, "r", encoding="utf-8") as f:
            sql = f.read()
    elif args.sql:
        sql = args.sql

    config = load_config(args.config)
    load_dotenv((config.get("db", {}) or {}).get("env_file", ".env"))
    result = evaluate(config, args.profile, sql, dict(os.environ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("allowed") else 1


if __name__ == "__main__":
    sys.exit(main())

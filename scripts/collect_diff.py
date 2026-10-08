#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_diff.py — Stage 0: 대상 범위 결정 + 변경분 수집 + 파일 유형 분류.

크로스플랫폼(mac/linux/Windows). git을 subprocess로 호출하므로 bash가 필요 없다.
기본은 "마지막 튜닝 이후" 증분(--since-last): 상태파일의 last_tuned_commit을
baseline으로 삼아 그 이후 커밋분 + 미커밋(working/staged)을 모두 대상으로 한다.
상태가 없으면(첫 사용) 전체 쿼리 관련 소스를 대상으로 한다. (references/state-and-followup.md)

사용법(Windows는 python 또는 py, mac/linux는 python3):
  python3 scripts/collect_diff.py                     # 기본: 마지막 튜닝 이후(첫 실행이면 전체)
  python3 scripts/collect_diff.py --all               # 전체 쿼리 관련 소스 강제
  python3 scripts/collect_diff.py --count-only        # 유형별 파일 수만(규모 파악 · 목록/diff 생략)
  python3 scripts/collect_diff.py --continue          # 점진 스캔 재개(state.json scan_progress의 다음 도메인)
  python3 scripts/collect_diff.py --staged            # staged 변경분만
  python3 scripts/collect_diff.py --range main..HEAD  # 지정 범위
  python3 scripts/collect_diff.py --files a.xml b.kt  # 특정 파일만
  python3 scripts/collect_diff.py --state <path>      # 상태파일 경로 지정

종료 코드: 0=정상, 2=인자 오류, 3=git 없음/저장소 아님.
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
from collections import Counter

# Windows 콘솔(cp949 등)에서도 한국어 출력이 깨지지 않게 UTF-8로 고정.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")           # Python 3.7+
    except Exception:
        pass

STATE_DEFAULT = "docs/query-inspector/tuning-reports/state.json"
# MyBatis 매퍼 XML 판정(설정 XML과 구분): <mapper namespace 또는 CRUD 태그.
_XML_RE = re.compile(r"<mapper\s+namespace|<(?:select|insert|update|delete)[\s>]", re.I)
# 쿼리 생성 후보 파일명(규모 추정용): JVM 네이밍 + Python(Django/SQLAlchemy) 네이밍.
_CAND_RE = re.compile(r"[Rr]epository|[Mm]apper|[Dd]ao|[Ee]ntity|models|views|serializers|managers|tasks")


def git(*args):
    """git 명령 실행 → (returncode, stdout). 실패해도 예외를 내지 않는다(returncode로 판단)."""
    try:
        p = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        sys.stderr.write("오류: git 명령을 찾을 수 없습니다. git 설치를 확인하세요.\n")
        sys.exit(3)
    return p.returncode, (p.stdout or "")


def is_git_repo() -> bool:
    return git("rev-parse", "--is-inside-work-tree")[0] == 0


# --- 파일 유형 분류 ---
def classify(f: str) -> str:
    lower = f.lower()
    if lower.endswith("mapper.xml"):
        return "mybatis-xml"
    if lower.endswith(".xml"):
        rc, content = git("show", ":" + f)          # staged/HEAD 내용으로 매퍼 여부 판정
        if rc == 0 and _XML_RE.search(content):
            return "mybatis-xml"
        return "config"
    _segs = lower.split("/")
    if (("/migration/" in lower and lower.endswith(".sql"))
            or "/db/changelog/" in lower
            or ("changelog" in lower and lower.endswith(".sql"))
            or "flyway" in lower or "liquibase" in lower
            or (lower.endswith(".py") and not lower.endswith("__init__.py")
                and any(seg in ("migrations", "versions") for seg in _segs[:-1]))):
        return "migration-sql"                      # Flyway/Liquibase(.sql) + Django(migrations/*.py)/Alembic(versions/*.py). 루트 migrations/도 포함
    if lower.endswith(".sql"):
        return "sql"
    if lower.endswith((".kt", ".kts", ".java", ".scala", ".groovy", ".py")):
        return "source"                             # JVM + Python(Django/SQLAlchemy). Node(.js/.ts)는 이후
    if lower.endswith((".html", ".htm", ".jinja", ".jinja2", ".j2")):
        return "template"                           # 서버 템플릿(Django/Jinja2/Thymeleaf) - 관계 접근 N+1 점검(서버 렌더링 스택에서만)
    if (lower.endswith((".yml", ".yaml", ".properties", ".conf", ".gradle", ".toml"))
            or lower.endswith(".gradle.kts") or posixpath.basename(lower) == "pom.xml"):
        return "config"
    return "other"


_REL = {"mybatis-xml": 3, "sql": 3, "migration-sql": 3, "source": 2, "template": 1, "config": 1}


def relevance(t: str) -> int:
    return _REL.get(t, 0)


def is_test_path(f: str) -> bool:
    """테스트 소스 판정(저장소 상대경로 기준, JVM + Python). 우선순위 최하/제외 대상."""
    p = f.lower()
    segs = p.split("/")
    if "src/test/" in p:                             # JVM(Maven/Gradle 표준 레이아웃)
        return True
    if any(seg in ("test", "tests") for seg in segs[:-1]):   # test/tests 디렉토리(예: tests/, src/<app>/test/)
        return True
    base = segs[-1]                                  # Python 테스트 파일 네이밍
    if base.startswith("test_") or base.endswith("_test.py") or base == "conftest.py":
        return True
    return False


def read_baseline(state_file: str) -> str:
    if not os.path.isfile(state_file):
        return ""
    try:
        with open(state_file, encoding="utf-8") as f:
            return json.load(f).get("last_tuned_commit", "") or ""
    except Exception:
        return ""


def read_next_domain(state_file: str):
    """scan_progress.domains_pending[0] → (name, [globs]). 없으면 (None, [])."""
    if not os.path.isfile(state_file):
        return None, []
    try:
        with open(state_file, encoding="utf-8") as f:
            sp = (json.load(f).get("scan_progress") or {})
        pend = sp.get("domains_pending") or []
        if not pend:
            return None, []
        d = pend[0]
        if isinstance(d, dict):
            return d.get("name", ""), list(d.get("globs") or [])
        if isinstance(d, str):
            return d, [d]                            # 하위호환: 경로 문자열 = name이자 단일 glob
    except Exception:
        pass
    return None, []


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="collect_diff.py", add_help=True,
        description="Stage 0: 대상 범위 결정 + 변경분 수집 + 파일 유형 분류 (크로스플랫폼).")
    ap.add_argument("--range", dest="range")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--all", dest="all_", action="store_true")
    ap.add_argument("--count-only", dest="count_only", action="store_true")
    ap.add_argument("--continue", dest="cont", action="store_true")
    ap.add_argument("--since-last", dest="since_last", action="store_true")
    ap.add_argument("--state", default=STATE_DEFAULT)
    ap.add_argument("--files", nargs="+", default=[])
    args = ap.parse_args()

    if not is_git_repo():
        sys.stderr.write("오류: git 저장소가 아닙니다. query-inspector는 git diff를 대상으로 동작합니다.\n")
        return 3

    files = list(args.files)
    display_files = list(files)                      # 사용자 표시용(:(glob) 매직 가공 전 원본)
    RANGE = args.range or ""
    if args.range:
        mode = "range"
    elif args.staged:
        mode = "staged"
    elif args.all_:
        mode = "all"
    else:
        mode = "since-last"
    effective_label = ""

    # --- --continue: 점진 스캔 다음 도메인의 globs(다중 pathspec)를 대상으로 ---
    if args.cont:
        name, globs = read_next_domain(args.state)
        if globs:
            display_files = list(globs)
            files = [f":(glob){g}" for g in globs]   # glob 매직: **/ 가 '/'를 넘어가게 명시(B3)
            mode = "all"
            effective_label = f"재개(점진 전체 스캔) — 다음 도메인: {name or '?'} (globs: {' '.join(globs)})"
        else:
            mode = "all"
            effective_label = "재개할 scan_progress가 없음 → 전체(범위 확인 권장)"

    # --- --files 명시(range/staged/continue 아님) → baseline 무관하게 지정 파일 전체 대상(B1) ---
    if files and mode == "since-last" and not args.cont:
        mode = "all"
        effective_label = f"파일 한정({len(display_files)}개) — baseline 무관 전체 대상"

    # --- since-last 해석: baseline 유효 → incremental, 아니면 → all ---
    if mode == "since-last":
        baseline = read_baseline(args.state)
        if baseline and git("cat-file", "-e", baseline + "^{commit}")[0] == 0:
            mode = "incremental"
            RANGE = baseline
            effective_label = f"증분: 마지막 튜닝({baseline[:8]}) 이후 커밋분 + 미커밋 + 새 파일"
        elif baseline:
            mode = "all"
            effective_label = "전체(저장된 baseline이 무효 — rebase/squash 추정)"
        else:
            mode = "all"
            effective_label = "첫 실행 → 전체 쿼리 관련 소스"

    # --- 대상 파일 목록 수집 ---
    changed: list[str] = []
    if mode == "all":
        rc, out = git("ls-files", *files)
        for f in out.splitlines():
            if f and classify(f) != "other":         # 쿼리 무관 제외
                changed.append(f)
    else:
        diffsel = ["--cached"] if mode == "staged" else [RANGE]
        gitargs = ["diff", "--name-only", "--diff-filter=d"] + diffsel   # d=삭제 제외(Read 실패 방지, B4)
        if files:
            gitargs += ["--"] + files
        rc, out = git(*gitargs)
        for f in out.splitlines():
            if f and classify(f) != "other":          # 쿼리 무관 제외(diff 모드에도 적용, B4)
                changed.append(f)
        if mode == "incremental":
            # git diff는 tracked만 보므로, 마지막 튜닝 이후 새로 생긴 미추적 파일을 합친다
            rc2, out2 = git("ls-files", "--others", "--exclude-standard", *files)
            for f in out2.splitlines():
                if f and classify(f) != "other":
                    changed.append(f)

    # --- 출력 ---
    print("=== query-inspector : Stage 0 대상 수집 ===")
    if args.cont:
        print(f"범위: {effective_label}")
        if display_files:
            print(f"대상 도메인 경로: {' '.join(display_files)}")
    elif display_files:
        print(f"범위: {effective_label or ('파일 한정 (' + str(len(display_files)) + '개 지정)')}")
        print(f"파일: {' '.join(display_files)}")
    else:
        if mode == "incremental":
            print(f"범위: {effective_label or '증분'}")
        elif mode == "range":
            print(f"범위: {effective_label or ('지정 범위 (' + RANGE + ')')}")
        elif mode == "staged":
            print("범위: staged (--cached)")
        elif mode == "all":
            print(f"범위: {effective_label or '전체 (--all)'}")
    print(f"상태파일: {args.state} " + ("(있음)" if os.path.isfile(args.state) else "(없음 → 첫 실행 취급)"))
    print(f"대상 파일 수: {len(changed)}")
    print()

    if args.count_only:
        print("--- 유형별 파일 수 (규모 파악용) ---")
        if changed:
            for t, n in sorted(Counter(classify(f) for f in changed).items(), key=lambda kv: (-kv[1], kv[0])):
                print(f"{n:>4} {t}")
            print()
            print("--- 디렉토리 분포 (도메인 근사 · 상위 20) ---")
            dirs = [posixpath.dirname(f) or "." for f in changed]
            for d, n in sorted(Counter(dirs).items(), key=lambda kv: (-kv[1], kv[0]))[:20]:
                print(f"{n:>4} {d}")
            print(f"고유 디렉토리 수(도메인 근사): {len(set(dirs))}")
            cand = 0
            for f in changed:
                if is_test_path(f):                  # 테스트 소스는 튜닝 후보에서 제외(노이즈)
                    continue
                if classify(f) in ("mybatis-xml", "sql", "migration-sql"):
                    cand += 1
                    continue
                if _CAND_RE.search(f):
                    cand += 1
            print(f"쿼리 생성 후보(경량 추정 · 파일명/유형 기준): {cand}  <- 전체 source가 아니라 이 수가 실제 튜닝 대상 규모에 가깝다")
        else:
            print("(대상 없음)")
        print()
        print("(SKILL Stage 0: 위 유형·도메인 규모로 범위 선택지를 제시하세요. 목록/diff는 생략됨.)")
        return 0

    if not changed:
        print("(대상 변경이 없습니다. 마지막 튜닝 이후 쿼리 관련 변경이 없거나, --all/--staged/--range를 확인하세요.)")
        return 0

    print("--- 파일 분류 (쿼리 관련 우선) ---")
    rows = []
    for f in changed:
        t = classify(f)
        r = 0 if is_test_path(f) else relevance(t)   # 테스트 소스는 최하로 강등
        rows.append((r, t, f))
    rows.sort(key=lambda x: (-x[0], x[2]))            # relevance 내림차순, 동점은 경로 알파벳(결정적)
    for _r, t, f in rows:
        print(f"[{t}]\t{f}")
    print()

    if mode == "all":
        print("--- 전체 모드: diff 없음 ---")
        print("(SKILL Stage 1: 위 각 파일의 쿼리 지점을 파일 전체를 Read 해서 추출하세요. 첫 실행/전체 리뷰입니다.)")
    else:
        print("--- 통합 diff ---")
        print("(SKILL Stage 1: 아래 diff에서 쿼리 지점을 추출하고, 매핑/시그니처가 부족하면 해당 파일 전체를 Read 하세요.)")
        if mode == "incremental":
            print("(증분: 새로 생긴 미추적 파일은 diff에 없으니 위 목록의 해당 파일을 Read 하세요.)")
        print()
        diffsel = ["--cached"] if mode == "staged" else [RANGE]
        gitargs = ["diff", "--diff-filter=d"] + diffsel
        # 본문 diff를 수집 대상(쿼리 관련 · 삭제 제외)으로 한정 — 비쿼리 노이즈 제거(B4)
        targets = files if files else changed
        if targets:
            gitargs += ["--"] + targets
        sys.stdout.write(git(*gitargs)[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())

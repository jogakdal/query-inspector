#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blame_author.py — 쿼리 원천(파일:라인)의 최종 수정자를 git blame으로 조회.

튜닝 리포트·쿼리 인벤토리의 각 항목에 "마지막으로 작성/수정한 사람"을 채우기 위한 헬퍼.
크로스플랫폼(mac/linux/Windows). git blame --porcelain을 파싱해 라인별 author·날짜를 낸다.

- 미커밋(working tree에만 있는 변경)·미추적/새 파일은 committed=false로 표기하고,
  가능하면 로컬 git 사용자(user.name)를 현재 작업자로 함께 준다.
- git 정보가 없으면(저장소 아님 등) 조용히 빈 결과를 낸다(리포트에선 생략).

사용(Windows는 python 또는 py):
  python3 scripts/blame_author.py --file src/Foo.kt --lines 42
  python3 scripts/blame_author.py --file src/Foo.kt --lines 42,88,120 --json

종료 코드: 0=정상(결과 유무 무관), 2=인자 오류.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

_ZERO = "0" * 40
_HEADER = re.compile(r"^([0-9a-f]{40}) \d+ (\d+)(?: \d+)?$")


def git(*args):
    try:
        p = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        return 127, "", "git 없음"
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def local_user():
    rc, out, _ = git("config", "user.name")
    return out.strip() if rc == 0 and out.strip() else None


def blame_lines(path, lines):
    """{line: {author, mail, date, committed, commit}} 반환. 실패 라인은 미커밋으로."""
    result = {}
    if not lines:
        return result
    args = ["blame", "--porcelain"]
    for n in lines:
        args += ["-L", f"{n},{n}"]
    args += ["--", path]
    rc, out, _err = git(*args)
    if rc != 0:
        # 미추적/새 파일 등 → 미커밋으로 간주(현재 작업자 추정)
        user = local_user()
        for n in lines:
            result[n] = {"author": user, "mail": None, "date": None,
                         "committed": False, "commit": None}
        return result

    commits = {}          # sha -> {author, mail, time}
    cur = None
    final_line = None
    for raw in out.splitlines():
        m = _HEADER.match(raw)
        if m:
            cur = m.group(1)
            final_line = int(m.group(2))
            commits.setdefault(cur, {})
            continue
        if cur is None:
            continue
        if raw.startswith("author "):
            commits[cur]["author"] = raw[len("author "):]
        elif raw.startswith("author-mail "):
            commits[cur]["mail"] = raw[len("author-mail "):].strip("<>")
        elif raw.startswith("author-time "):
            commits[cur]["time"] = raw[len("author-time "):].strip()
        elif raw.startswith("\t"):        # 코드 라인 = 이 블록 종료
            info = commits.get(cur, {})
            committed = cur != _ZERO
            date = None
            t = info.get("time")
            if t:
                try:
                    date = datetime.datetime.fromtimestamp(int(t)).strftime("%Y-%m-%d")
                except Exception:
                    date = None
            author = info.get("author")
            if not committed and not author:
                author = local_user()
            result[final_line] = {"author": author, "mail": info.get("mail"),
                                  "date": date, "committed": committed, "commit": cur}
            cur = None
    # blame이 못 준 라인은 미커밋 처리
    for n in lines:
        result.setdefault(n, {"author": local_user(), "mail": None, "date": None,
                              "committed": False, "commit": None})
    return result


def main() -> int:
    ap = argparse.ArgumentParser(prog="blame_author.py",
        description="쿼리 원천(파일:라인)의 최종 수정자를 git blame으로 조회")
    ap.add_argument("--file", required=True)
    ap.add_argument("--lines", required=True, help="콤마 구분 라인 번호(예: 42 또는 42,88,120)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        lines = [int(x) for x in args.lines.split(",") if x.strip()]
    except ValueError:
        sys.stderr.write("오류: --lines 는 콤마로 구분된 정수여야 합니다.\n")
        return 2

    if git("rev-parse", "--is-inside-work-tree")[0] != 0:
        # git 저장소가 아니면 조용히 빈 결과(리포트에서 생략)
        print(json.dumps({"file": args.file, "lines": {}}, ensure_ascii=False, indent=2)
              if args.json else "(git 저장소가 아님 — 최종 수정자 생략)")
        return 0

    info = blame_lines(args.file, lines)
    out = {"file": args.file, "lines": {str(k): v for k, v in sorted(info.items())}}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for n in sorted(info):
            v = info[n]
            who = v["author"] or "미상"
            when = f" ({v['date']})" if v.get("date") else ""
            tag = "" if v["committed"] else " [미커밋]"
            print(f"{args.file}:{n} — {who}{when}{tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

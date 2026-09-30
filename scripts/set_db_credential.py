#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""set_db_credential.py — DB 접속 URL을 화면에 표시하지 않고(마스킹) 입력받아 .env에 저장.

비밀번호가 화면·셸 히스토리·대화 기록 어디에도 남지 않도록, 파이썬 getpass로
숨김 입력을 받아 프로젝트 `.env`(권한 0600)에 저장한다. 저장 후에는 스킬이 자동 로드한다.

⚠️ 반드시 **사용자의 터미널에서 직접** 실행하세요(Claude 대화창이 아니라).
   Claude Code의 Bash 도구는 비대화형이라 숨김 입력이 안 됩니다 — 그 경우 이 스크립트는 거부합니다.

사용:
    python3 scripts/set_db_credential.py --var QT_DEV_DB_URL
    # → "QT_DEV_DB_URL 접속 URL 입력(화면 미표시):" 프롬프트에 mysql://user:pass@host:port/db 입력

종료 코드: 0=저장, 1=취소/빈 입력, 2=TTY 아님(거부).
"""
from __future__ import annotations

import argparse
import getpass
import os
import re
import stat
import sys
from urllib.parse import quote

# Windows 콘솔(cp949 등)에서도 한국어 출력이 깨지지 않게 UTF-8로 고정.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")           # Python 3.7+
    except Exception:
        pass


def normalize_url_credentials(url: str) -> str:
    """`scheme://user:pass@host…`에서 user/pass만 percent-encode 한다(raw 특수문자 안전).

    raw 예약문자(#, @, ! 등)가 비밀번호에 섞여도 **마지막 @**를 authority 구분자로 보고
    분리한 뒤 user/pass를 인코딩한다. userinfo가 없으면 URL을 그대로 반환한다.
    (사용자는 비밀번호를 있는 그대로 입력하면 되고, 저장 시 자동 인코딩된다.)
    """
    m = re.match(r"^([a-zA-Z][\w+.\-]*://)(.+)@([^@]+)$", url.strip())
    if not m:
        return url
    scheme, userinfo, host = m.group(1), m.group(2), m.group(3)
    if ":" in userinfo:
        user, pw = userinfo.split(":", 1)
    else:
        user, pw = userinfo, None
    enc = quote(user, safe="") + ((":" + quote(pw, safe="")) if pw is not None else "")
    return f"{scheme}{enc}@{host}"


def ensure_gitignore(env_path: str) -> None:
    """env 파일이 프로젝트 `.gitignore`에 없으면 추가해 자격증명 커밋을 방지한다."""
    name = os.path.basename(env_path) or ".env"
    gi = ".gitignore"
    try:
        existing = []
        if os.path.exists(gi):
            with open(gi, encoding="utf-8") as f:
                existing = [ln.strip() for ln in f]
        if name in existing or env_path in existing:
            return
        with open(gi, "a", encoding="utf-8") as f:
            f.write(("" if (not existing or existing[-1] == "") else "\n") + name + "\n")
        sys.stderr.write(f"참고: {gi}에 '{name}'을 추가해 자격증명 커밋을 방지했습니다.\n")
    except Exception:
        pass


def upsert_env(path: str, key: str, value: str) -> None:
    """`.env`에 KEY=VALUE를 추가/갱신하고 파일 권한을 0600으로 만든다."""
    lines: list[str] = []
    found = False
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s.startswith(f"{key}=") or s.startswith(f"export {key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"{key}={value}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)      # 0600 (소유자만 읽기/쓰기)


def main() -> int:
    ap = argparse.ArgumentParser(description="DB 접속 URL을 마스킹 입력해 .env에 저장")
    ap.add_argument("--var", required=True, help="환경변수 이름(예: QT_DEV_DB_URL)")
    ap.add_argument("--env-file", default=".env", help="저장할 파일(기본 .env)")
    args = ap.parse_args()

    if not sys.stdin.isatty():
        sys.stderr.write(
            "오류: 터미널(TTY)에서 직접 실행해야 숨김 입력이 됩니다.\n"
            "      Claude 대화창이 아니라 사용자 셸에서 실행하세요.\n"
            "      (또는 셸에서 `export {var}=...` / `.env`에 직접 저장)\n".format(var=args.var)
        )
        return 2

    try:
        url = getpass.getpass(f"{args.var} 접속 URL 입력(화면 미표시): ").strip()
    except (KeyboardInterrupt, EOFError):
        sys.stderr.write("\n취소되었습니다.\n")
        return 1
    if not url:
        sys.stderr.write("입력이 비어 있습니다. 취소.\n")
        return 1

    url = normalize_url_credentials(url)          # user/pass의 특수문자 자동 percent-encode
    upsert_env(args.env_file, args.var, url)
    ensure_gitignore(args.env_file)               # .env가 .gitignore에 없으면 추가
    # 값은 절대 출력하지 않는다.
    print(f"✔ {args.env_file}에 {args.var} 저장 완료(권한 0600). 값은 표시하지 않았습니다.")
    print("  이제 /query-inspector --db <profile> 를 실행하면 자동으로 사용됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

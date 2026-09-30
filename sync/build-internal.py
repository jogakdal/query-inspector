#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build-internal.py — 공개판(이 저장소)에서 내부 배포판 트리를 생성한다.

방향: 글로벌 우선 → 내부 동기화. 공개판이 정본이고, 내부 배포판은 이 스크립트의 산출물이다.
내부 고유값은 이 스크립트에 두지 않고 `sync/internal.profile`(gitignore)에서 읽는다.

처리:
  1) 공개판 트리를 출력 디렉토리로 복사(EXCLUDE 제외).
  2) 언어 승격: README.ko.md→README.md, MANUAL.ko.md→MANUAL.md, 상단 언어 스위처 줄 제거.
  3) 치환: internal.profile의 "공개값 ||| 내부값" 매핑을 전 파일에 적용(긴 값 먼저).
  4) 네임스페이스: 소문자 `query-inspector`(호출표기 /query-inspector:<skill>, 플러그인 참조
     query-inspector@<market>, 매니페스트 name, 설치 스크립트, 서술문)를 <PLUGIN_NAMESPACE>로 전량 치환.
     displayName("Query Inspector")·스킬명(tuning-report·inventory-report)은 유지.
  5) 내부값·placeholder 잔존 여부를 점검 리포트로 출력.

이 스크립트는 **산출물을 출력 디렉토리에 생성만** 한다. 내부 저장소 반영(커밋·push)은 사람이 diff 확인 후 수행한다.

사용:
  python3 sync/build-internal.py --out /tmp/qi-internal            # 생성
  python3 sync/build-internal.py --out /tmp/qi-internal --diff <현_내부 배포판경로>   # 생성 + 대조
종료: 0=정상, 2=프로파일/입력 오류.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except Exception: pass

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC_ROOT = os.path.dirname(HERE)

# 내부 배포판에서 제외: 생성 도구(sync) + 영어 원본 문서(한국어본이 승격 대체).
# LICENSE/CONTRIBUTING은 포함한다(사내판 README가 링크하므로).
EXCLUDE_DIRS = {".git", "sync"}
EXCLUDE_FILES = {"README.md", "MANUAL.md", "INSTALL.md",
                 "MANUAL-tuning-report.md", "MANUAL-inventory-report.md"}
# 한국어본을 내부 기본 문서로 승격(내부는 한국어 단일): README.ko.md → README.md
PROMOTE = {"README.ko.md": "README.md", "MANUAL.ko.md": "MANUAL.md", "INSTALL.ko.md": "INSTALL.md",
           "MANUAL-tuning-report.ko.md": "MANUAL-tuning-report.md",
           "MANUAL-inventory-report.ko.md": "MANUAL-inventory-report.md"}
# 언어 스위처 줄(제거)
SWITCHER_RE = re.compile(r'^\s*(\*\*English\*\*\s*\|\s*\[한국어\].*|\[English\].*\|\s*\*\*한국어\*\*\s*)$')


def load_profile(path):
    if not os.path.isfile(path):
        sys.stderr.write(f"오류: 프로파일 없음: {path}\n  cp sync/internal.profile.example sync/internal.profile 후 값 입력\n")
        sys.exit(2)
    pairs, special = [], {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.rstrip("\n")
            t = s.strip()
            if not t or t.startswith("#"):
                continue
            if "|||" in s:
                a, b = s.split("|||", 1)
                pairs.append((a.strip(), b.strip()))
            elif t.startswith("@") and "=" in t:
                k, v = t[1:].split("=", 1)
                special[k.strip()] = v.strip()
    pairs.sort(key=lambda ab: -len(ab[0]))       # 긴 공개값 먼저
    return pairs, special


def promote_and_switcher(text):
    return "\n".join(l for l in text.split("\n") if not SWITCHER_RE.match(l))


def apply_namespace(text, ns, is_manifest):
    # 네임스페이스 치환: 공개판 `query-inspector`(소문자)를 내부 <PLUGIN_NAMESPACE>로.
    # 저장소 URL은 profile 치환에서 이미 내부 URL로 바뀌었으므로,
    # 이 시점에 남은 소문자 `query-inspector`는 전부 네임스페이스다(호출 /query-inspector:<skill>,
    # 플러그인 참조 query-inspector@<market>, 매니페스트 "name", 설치 스크립트 PLUGIN_NAME·INSTALL_DIR,
    # 서술문 등). 스킬명(tuning-report·inventory-report)·displayName("Query Inspector", 대문자)은 유지.
    return text.replace("query-inspector", ns)


def main():
    ap = argparse.ArgumentParser(prog="build-internal.py", description="공개판 → 내부 배포판 생성")
    ap.add_argument("--out", required=True, help="내부 배포판 산출 디렉토리")
    ap.add_argument("--profile", default=os.path.join(HERE, "internal.profile"))
    ap.add_argument("--diff", help="대조할 현 내부 배포판 경로(참고용 diff 요약)")
    args = ap.parse_args()

    pairs, special = load_profile(args.profile)
    ns = special.get("PLUGIN_NAMESPACE")
    if not ns:
        sys.stderr.write("오류: 프로파일에 @PLUGIN_NAMESPACE 없음\n"); return 2

    out = os.path.abspath(args.out)
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)

    copied = promoted = subst_files = 0
    for root, dirs, files in os.walk(PUBLIC_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        rel = os.path.relpath(root, PUBLIC_ROOT)
        for fn in files:
            if rel == "." and fn in EXCLUDE_FILES:
                continue
            src = os.path.join(root, fn)
            relpath = fn if rel == "." else os.path.join(rel, fn)
            # 언어 승격(대상 파일명 변경)
            dst_rel = PROMOTE.get(relpath, relpath) if rel == "." else relpath
            dst_rel = dst_rel.replace("query-inspector", ns)   # 파일명도 네임스페이스(query-inspector-setup.sh -> <ns>-setup.sh)
            dst = os.path.join(out, dst_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                with open(src, encoding="utf-8") as f: text = f.read()
                is_text = True
            except (UnicodeDecodeError, IsADirectoryError):
                shutil.copy2(src, dst); copied += 1; continue
            orig = text
            # 승격된 문서는 스위처 줄 제거
            if rel == "." and relpath in PROMOTE:
                text = promote_and_switcher(text)
                # 한국어본 상호링크(.ko.md)는 승격 후 .md 파일명을 가리키도록 되돌린다.
                text = text.replace(".ko.md", ".md")
                promoted += 1
            # 치환(공개값→내부값)
            for a, b in pairs:
                text = text.replace(a, b)
            # 네임스페이스
            is_manifest = relpath.endswith(".json") and ".claude-plugin" in root
            text = apply_namespace(text, ns, is_manifest)
            with open(dst, "w", encoding="utf-8") as f: f.write(text)
            copied += 1
            if text != orig: subst_files += 1

    # 점검: 내부값으로 잘 바뀌었는지 + 공개값/placeholder 잔존 없는지
    print(f"[build-internal] 생성 완료 → {out}")
    print(f"  파일 복사 {copied} · 문서 승격 {promoted} · 치환 발생 {subst_files}")
    leaks = []
    for root, dirs, files in os.walk(out):
        for fn in files:
            p = os.path.join(root, fn)
            try:
                with open(p, encoding="utf-8") as f: s = f.read()
            except Exception: continue
            for pat in ("jogakdal", "github.com/jogakdal", "query-inspector-marketplace"):
                if pat in s:
                    leaks.append(f"{os.path.relpath(p, out)}: '{pat}'")
            if re.search(r"<<[A-Z_]+>>", s):     # 실제 placeholder만(heredoc <<EOF 오탐 제외)
                leaks.append(f"{os.path.relpath(p, out)}: unresolved placeholder")
    if leaks:
        print("  ⚠️ 공개값/placeholder 잔존:")
        for l in leaks[:40]: print("    -", l)
    else:
        print("  ✅ 공개값·placeholder 잔존 없음")

    if args.diff and os.path.isdir(args.diff):
        import subprocess
        print(f"\n[diff] 현 내부 배포판({args.diff})과 파일 목록 차이(참고 — 공개판 신기능으로 차이 존재 정상):")
        r = subprocess.run(["diff", "-rq", "--exclude=.git", "--exclude=docs",
                            args.diff, out], capture_output=True, text=True)
        for line in (r.stdout or "").splitlines()[:40]:
            print("  ", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())

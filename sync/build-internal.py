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

# 내부 배포판에서 제외:
#  - 생성 도구(sync), 영어 원본 문서(한국어본이 승격 대체), LICENSE(사내판 라이선스 미표기).
#  - CONTRIBUTING(공개 기여 가이드라 사내 불필요), PRIVACY(ko/영문 모두 - 사내 전용 도구라 불필요).
EXCLUDE_DIRS = {".git", "sync"}
EXCLUDE_FILES = {"README.md", "MANUAL.md", "INSTALL.md",
                 "MANUAL-tuning-report.md", "MANUAL-inventory-report.md",
                 "LICENSE", "CONTRIBUTING.md", "PRIVACY.md", "PRIVACY.ko.md"}
# 한국어본을 내부 기본 문서로 승격(내부는 한국어 단일): README.ko.md → README.md
PROMOTE = {"README.ko.md": "README.md", "MANUAL.ko.md": "MANUAL.md", "INSTALL.ko.md": "INSTALL.md",
           "MANUAL-tuning-report.ko.md": "MANUAL-tuning-report.md",
           "MANUAL-inventory-report.ko.md": "MANUAL-inventory-report.md"}
# 언어 스위처 줄(제거)
SWITCHER_RE = re.compile(r'^\s*(\*\*English\*\*\s*\|\s*\[한국어\].*|\[English\].*\|\s*\*\*한국어\*\*\s*)$')

# 사내판은 라이선스 관련 언급/정보를 전부 뺀다(사내 전용 도구).
#  - LICENSE 파일: EXCLUDE_FILES로 제외.
#  - README/CONTRIBUTING의 라이선스 섹션: 블록 삭제(선행 --- 구분선 포함, 문서 끝까지).
# 기여(CONTRIBUTING) 링크는 라이선스가 아니므로 건드리지 않는다.
LICENSE_SECTION_RE = re.compile(r'\n(?:[ \t]*\n)?(?:---[ \t]*\n[ \t]*\n)?#+[ \t]*(?:라이선스|License)\b.*?(?=\n#+[ \t]|\Z)', re.S)


def strip_license(text):
    """라이선스 섹션(선행 --- 구분선 포함)을 제거한다. 섹션이 문서 끝이면 끝까지."""
    out = LICENSE_SECTION_RE.sub("", text)
    return out.rstrip() + "\n"   # 섹션 삭제로 사라진 파일 끝 개행 복원


# README의 CONTRIBUTING 참조 줄 제거(사내판은 CONTRIBUTING을 EXCLUDE하므로 깨진 링크 방지).
CONTRIB_LINE_RE = re.compile(r'^.*\[CONTRIBUTING\.md\].*$\n?', re.M)


def strip_contrib_link(text):
    return CONTRIB_LINE_RE.sub("", text)


# DESIGN.md의 디렉토리 트리는 공개판 저장소 구조를 그린다. 사내판은 생성 도구(sync/), LICENSE,
# CONTRIBUTING이 없고 문서가 한국어 단일이므로, 트리의 해당 줄을 사내판 실제 구조로 보정한다.
#   치환 전에 호출해야 setup 스크립트명(원문 query-inspector-setup)으로 마지막 줄 커넥터를 매칭한다.
def fix_internal_doc_tree(text):
    # 문서 줄: "영어 정본 + 한국어본"(.ko.md 병기)을 한국어 단일로
    text = re.sub(
        r"(├── README\.md / MANUAL\.md / MANUAL-\{tuning,inventory\}-report\.md) \(\+ \.ko\.md\) +# 영어 정본 \+ 한국어본",
        r"\1   # 한국어 문서", text)
    # LICENSE, CONTRIBUTING 제거(사내판 미포함)
    text = text.replace("├── CHANGELOG.md / LICENSE / CONTRIBUTING.md", "├── CHANGELOG.md")
    # sync/(생성 도구) 줄 제거 + 직전 줄을 트리 마지막 커넥터(└──)로 보정
    text = re.sub(
        r"├── (query-inspector-setup\.sh / \.bat +# 설치 스크립트\(mac/linux / Windows\))\n"
        r"└── sync/ +# 내부 배포판 생성 도구\(build-internal\)\n",
        r"└── \1\n", text)
    return text


# 사내 전용 추가 블록: 생성 트리의 문서 끝에 이 디렉토리의 같은 이름 파일을 덧붙인다.
#  - 공개판엔 불필요하고 사내판에만 필요한 안내(구 버전 재설치 등)를 공개 문서를 건드리지 않고 추가.
#  - 파일명은 "생성 후" 이름(승격/치환 반영, 예: INSTALL.md). 내용은 사내 식별자로 이미 채워진 상태로 그대로 덧붙인다.
#  - gitignore라 공개 저장소엔 올라가지 않는다. 틀은 internal-append.example/ 참고.
APPEND_DIR = os.path.join(HERE, "internal-append")


def apply_appends(out):
    """APPEND_DIR의 각 파일을 생성 트리(out)의 같은 경로 문서 끝에 덧붙인다. 반환: 덧붙인 파일 수."""
    if not os.path.isdir(APPEND_DIR):
        return 0
    n = 0
    for root, _dirs, files in os.walk(APPEND_DIR):
        for fn in files:
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, APPEND_DIR)
            dst = os.path.join(out, rel)
            if not os.path.isfile(dst):
                sys.stderr.write(f"  ⚠️ append 대상 없음(건너뜀): {rel}\n")
                continue
            with open(src, encoding="utf-8") as f:
                add = f.read()
            with open(dst, encoding="utf-8") as f:
                base = f.read()
            with open(dst, "w", encoding="utf-8") as f:
                f.write(base.rstrip() + "\n" + add.rstrip() + "\n")
            n += 1
    return n


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
            # DESIGN.md 디렉토리 트리를 사내판 실제 구조로 보정(치환 전: setup 스크립트명이 원문이어야 커넥터 매칭)
            if relpath == "DESIGN.md":
                text = fix_internal_doc_tree(text)
            # 치환(공개값→내부값)
            for a, b in pairs:
                text = text.replace(a, b)
            # README: 라이선스 섹션 삭제(사내판 라이선스 미표기) + CONTRIBUTING 참조 줄 제거(사내판은 CONTRIBUTING EXCLUDE).
            base = os.path.basename(dst_rel)
            if base == "README.md":
                text = strip_contrib_link(strip_license(text))
            # 네임스페이스
            is_manifest = relpath.endswith(".json") and ".claude-plugin" in root
            text = apply_namespace(text, ns, is_manifest)
            with open(dst, "w", encoding="utf-8") as f: f.write(text)
            copied += 1
            if text != orig: subst_files += 1

    # 사내 전용 추가 블록(구 버전 재설치 안내 등)을 해당 문서 끝에 덧붙임
    appended = apply_appends(out)

    # 점검: 내부값으로 잘 바뀌었는지 + 공개값/placeholder 잔존 없는지
    print(f"[build-internal] 생성 완료 → {out}")
    print(f"  파일 복사 {copied} · 문서 승격 {promoted} · 치환 발생 {subst_files} · 추가블록 {appended}")
    leaks = []
    for root, dirs, files in os.walk(out):
        for fn in files:
            p = os.path.join(root, fn)
            try:
                with open(p, encoding="utf-8") as f: s = f.read()
            except Exception: continue
            for pat in ("jogakdal", "github.com/jogakdal", "query-inspector-marketplace",
                        "build-internal", "내부 배포판 생성"):
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

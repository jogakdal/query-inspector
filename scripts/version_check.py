#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""version_check.py — 설치 방식 감지 + 원격 최신 버전 확인 + (스킬 방식) self-update.

크로스플랫폼(mac/linux/Windows). git(ls-remote/clone)만 쓴다. 공개 저장소는 익명으로
읽히므로 별도 자격증명이 필요 없고, 비공개 저장소면 설치 때 쓴 git 자격증명을 그대로 재사용한다.

- 플러그인 방식(캐시 `~/.claude/plugins/...`): **확인만** 하고 갱신은 `claude plugin update`를
  안내한다. 캐시는 Claude Code가 버전으로 관리하는 영역이라 직접 수정하지 않는다.
- 스킬 방식(`~/.claude/skills/...`): `--apply`로 스킬 디렉토리를 clone본으로 교체(self-update).
  SKILL 본문·references·scripts는 재시작 없이 반영되고, frontmatter가 바뀐 경우만 재시작이 필요하다.

버전 비교: 원격을 얕게 clone해 `.claude-plugin/plugin.json`의 version으로 정확히 비교한다
(문서-only 커밋으로 인한 오탐 방지). 원격 조회는 하루 1회로 제한(--force로 무시).

사용(Windows는 python 또는 py):
  python3 scripts/version_check.py --skill-dir "$CLAUDE_SKILL_DIR" --json
  python3 scripts/version_check.py --skill-dir "$CLAUDE_SKILL_DIR" --apply   # 스킬 방식 self-update

종료 코드: 0=정상, 2=인자 오류, 3=확인 불가(git 없음/네트워크/인증 실패 → 조용히 skip 권장).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")           # Windows cp949에서도 한국어 깨짐 방지
    except Exception:
        pass

DEFAULT_REPO = "https://github.com/jogakdal/query-inspector.git"   # HTTPS: 공개 repo 익명 읽기, SSH 22 차단 환경 회피(B7)
# 스킬 방식에서 self-update로 교체하는 구성요소(query-inspector-setup의 COMPONENTS와 동일).
# 멀티스킬 구조: 루트 SKILL.md 대신 skills/(2개 스킬)를 통째 교체한다.
COMPONENTS = ["skills", ".claude-plugin", "references", "scripts", "assets", ".query-inspector.example.yml"]
CHECK_INTERVAL_HOURS = 24


def git(*args, timeout=60):
    env = dict(os.environ)
    # SSH 원격이 막힌 환경(22번 포트 차단)에서 매 실행 장시간 대기하지 않도록 빠른 실패 유도(B7).
    # HTTPS 비공개 원격의 자격증명 프롬프트로 무한 대기하는 것도 막는다.
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=5")
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    try:
        p = subprocess.run(["git", *args], capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout, env=env)
    except FileNotFoundError:
        return 127, "", "git 명령을 찾을 수 없음"
    except subprocess.TimeoutExpired:
        return 124, "", "git 시간 초과"
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def parse_semver(v):
    """"0.10.1" → (0,10,1). 파싱 실패 시 (0,) (가장 작은 값 취급)."""
    if not v:
        return (0,)
    out = []
    for part in str(v).strip().lstrip("v").split("."):
        num = ""
        for ch in part:
            if ch.isdigit():
                num += ch
            else:
                break
        out.append(int(num) if num else 0)
    return tuple(out) or (0,)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def detect_method(skill_dir):
    """설치 방식 감지 → 'plugin' | 'skill'."""
    if os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return "plugin"
    norm = skill_dir.replace("\\", "/")
    if "/plugins/cache/" in norm:
        return "plugin"
    if os.path.isfile(os.path.join(skill_dir, ".claude-plugin", "plugin.json")):
        return "plugin"
    return "skill"


def local_version(skill_dir, method):
    if method == "plugin":
        return read_json(os.path.join(skill_dir, ".claude-plugin", "plugin.json")).get("version")
    # 스킬 방식: 설치/업데이트 시 기록한 .qt-version
    try:
        with open(os.path.join(skill_dir, ".qt-version"), encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


def within_interval(check_state):
    last = check_state.get("last_check")
    if not last:
        return False
    try:
        t = datetime.datetime.fromisoformat(last)
    except Exception:
        return False
    return (datetime.datetime.now() - t) < datetime.timedelta(hours=CHECK_INTERVAL_HOURS)


def emit(result, as_json):
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    m = result.get("method")
    if not result.get("checked"):
        print(f"업데이트 확인 생략/불가: {result.get('reason','')}")
        return
    if result.get("update_available"):
        print(f"새 버전 있음: 로컬 {result.get('local_version')} → 원격 {result.get('remote_version')} (방식: {m})")
        print("권장 조치:", result.get("action"))
    else:
        lv = result.get("local_version"); rv = result.get("remote_version")
        if rv and parse_semver(lv) > parse_semver(rv):
            print(f"로컬이 원격보다 최신(개발 빌드): 로컬 {lv} > 원격 {rv} (방식: {m}).")
        else:
            print(f"최신입니다(로컬 {lv}, 방식: {m}).")


def main() -> int:
    ap = argparse.ArgumentParser(prog="version_check.py",
        description="설치 방식 감지 + 원격 최신 버전 확인 + (스킬 방식) self-update")
    ap.add_argument("--skill-dir", required=True, help="${CLAUDE_SKILL_DIR}")
    ap.add_argument("--report-dir", default="docs/query-inspector", help="체크 상태 저장 위치")
    ap.add_argument("--repo", default=os.environ.get("QT_REPO_URL", DEFAULT_REPO))
    ap.add_argument("--force", action="store_true", help="하루 1회 제한 무시")
    ap.add_argument("--apply", action="store_true", help="스킬 방식 self-update 수행")
    ap.add_argument("--local", action="store_true", help="원격 조회 없이 설치 방식·로컬 버전만 출력(--version용)")
    ap.add_argument("--json", action="store_true", help="기계용 JSON 출력")
    args = ap.parse_args()

    skill_dir = args.skill_dir
    method = detect_method(skill_dir)
    lver = local_version(skill_dir, method)

    # --local: 네트워크 없이 설치 방식·로컬 버전만(스킬의 --version이 사용)
    if args.local:
        if args.json:
            print(json.dumps({"method": method, "local_version": lver}, ensure_ascii=False, indent=2))
        else:
            print(f"query-inspector v{lver or 'unknown'} ({method})")
        return 0

    result = {"method": method, "local_version": lver, "checked": False,
              "update_available": False, "remote_version": None, "action": None}

    check_path = os.path.join(args.report_dir, "update-check.json")
    state = read_json(check_path)

    # --apply가 아니고, 최근 확인했고, --force도 아니면: 저장된 결과로 판단(원격 재조회 생략)
    if not args.apply and not args.force and within_interval(state):
        rver = state.get("remote_version")
        result.update(checked=True, remote_version=rver, cached=True)
        result["update_available"] = bool(rver) and parse_semver(rver) > parse_semver(lver)
        result["action"] = _action(method, result["update_available"])
        emit(result, args.json)
        return 0

    # 원격 최신 커밋 확인(가벼움). 실패는 조용히 skip(네트워크/인증 없음).
    rc, out, err = git("ls-remote", "--exit-code", args.repo, "HEAD", timeout=10)
    if rc != 0 or not out.strip():
        result["reason"] = f"원격 확인 불가({err.strip() or rc})"
        # 실패도 하루 1회 제한에 포함되게 last_check를 기록(백오프) — 매 실행 재시도/지연 방지(B7)
        if not args.force:
            _save_check(check_path, state.get("last_remote_commit"), state.get("remote_version"))
        emit(result, args.json)
        return 3

    remote_commit = out.split()[0]
    # 커밋이 지난 확인과 같고, apply도 아니면 → 재clone 없이 저장된 버전으로 판단
    if not args.apply and not args.force and state.get("last_remote_commit") == remote_commit:
        rver = state.get("remote_version")
        result.update(checked=True, remote_version=rver)
        result["update_available"] = bool(rver) and parse_semver(rver) > parse_semver(lver)
        result["action"] = _action(method, result["update_available"])
        _save_check(check_path, remote_commit, rver)
        emit(result, args.json)
        return 0

    # 얕은 clone으로 원격 버전 확정(문서-only 커밋 오탐 방지)
    tmp = tempfile.mkdtemp(prefix="qt-verchk-")
    try:
        rc, _o, err = git("clone", "--depth", "1", args.repo, tmp, timeout=180)
        if rc != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            result["reason"] = f"clone 실패({err.strip() or rc})"
            emit(result, args.json)
            return 3
        rver = read_json(os.path.join(tmp, ".claude-plugin", "plugin.json")).get("version")
        result.update(checked=True, remote_version=rver, remote_commit=remote_commit)
        result["update_available"] = bool(rver) and parse_semver(rver) > parse_semver(lver)

        if args.apply:
            if method == "plugin":
                result["action"] = ("플러그인 방식은 self-update 대상이 아닙니다 — "
                                    "`claude plugin update query-inspector@query-inspector-marketplace`(재시작)로 갱신하세요.")
                result["applied"] = False
            elif not result["update_available"]:
                result["action"] = "이미 최신입니다(적용 안 함)."
                result["applied"] = False
            else:
                _apply_skill(tmp, skill_dir, rver)
                result["applied"] = True
                result["action"] = (f"스킬을 {rver}로 갱신했습니다. 본문·스크립트는 다음 발동부터 반영됩니다. "
                                    "트리거(description)·권한(allowed-tools)이 바뀐 경우에만 새 세션이 필요합니다.")
        else:
            result["action"] = _action(method, result["update_available"])

        _save_check(check_path, remote_commit, rver)
        emit(result, args.json)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _action(method, available):
    if not available:
        return "최신"
    if method == "plugin":
        return ("`claude plugin update query-inspector@query-inspector-marketplace` 실행 후 재시작하거나, "
                "`/plugin` → Marketplaces에서 auto-update를 켜세요.")
    return "스킬 방식입니다 — 동의 시 self-update로 바로 갱신할 수 있습니다(version_check.py --apply)."


def _apply_skill(src, dst, rver):
    """clone본(src)의 구성요소를 스킬 디렉토리(dst)로 교체 복사한다."""
    os.makedirs(dst, exist_ok=True)
    for item in COMPONENTS:
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if not os.path.exists(s):
            continue
        if os.path.isdir(s):
            shutil.rmtree(d, ignore_errors=True)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
    with open(os.path.join(dst, ".qt-version"), "w", encoding="utf-8") as f:
        f.write(str(rver or "") + "\n")


def _save_check(path, remote_commit, remote_version):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"last_check": datetime.datetime.now().isoformat(),
                       "last_remote_commit": remote_commit,
                       "remote_version": remote_version}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())

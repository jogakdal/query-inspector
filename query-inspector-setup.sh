#!/usr/bin/env bash
#
# query-inspector 설치 스크립트 (플러그인 전용)
#
# 이 스킬은 멀티스킬(tuning-report + inventory-report) + 공유 자산(references/scripts/assets)
# + `/query-inspector:` 네임스페이스 구조라, 플러그인 방식으로만 설치한다.
# (스킬 직접 복사는 디렉토리 구조/네임스페이스/${CLAUDE_PLUGIN_ROOT} 경로가 맞지 않아 지원하지 않음.)
#
set -eu

# ─────────────────────────────────────────────────────────────
#   PLUGIN_NAME : 플러그인 네임스페이스(.claude-plugin/plugin.json 의 "name"과 일치)
#                 호출은 /<PLUGIN_NAME>:tuning-report · /<PLUGIN_NAME>:inventory-report
#   MARKET_NAME : .claude-plugin/marketplace.json 의 최상위 "name"과 일치
#   REPO_URL    : 마켓 소스(원격). 환경변수 QT_REPO_URL로 덮어쓸 수 있음
# ─────────────────────────────────────────────────────────────
REPO_URL="${QT_REPO_URL:-git@github.com:jogakdal/query-inspector.git}"
PLUGIN_NAME="query-inspector"
MARKET_NAME="query-inspector-marketplace"

SRC="$(cd "$(dirname "$0")" && pwd -P)"

msg() { printf '%s\n' "$*"; }
err() { printf 'error: %s\n' "$*" >&2; }
die() { err "$*"; exit 1; }

usage() {
  cat <<EOF
query-inspector 설치 스크립트 (플러그인 전용)

사용법:
  ./query-inspector-setup.sh                  플러그인 설치(개인 글로벌). 호출: /${PLUGIN_NAME}:tuning-report · :inventory-report
  ./query-inspector-setup.sh --project [DIR]  플러그인 설치(프로젝트 로컬). 대상 프로젝트 루트에서 실행(DIR로 경로 지정 가능)
  ./query-inspector-setup.sh --local          이 로컬 체크아웃을 마켓 소스로 사용(clone/포크/오프라인/검증). --project와 함께 쓸 수 있음
  ./query-inspector-setup.sh --help           이 도움말

이 스킬은 플러그인 방식으로만 설치합니다(멀티스킬 + 공유 자산 + 네임스페이스 구조라 스킬 직접 설치는 불가).
기본은 마켓(${REPO_URL})에서 받아 설치하고, --local은 이 스크립트가 있는 로컬 체크아웃을 마켓으로 등록해 설치합니다(수정판/오프라인 검증용).
claude CLI가 필요하며, 원격 마켓 사용 시 git 인증이 필요합니다.
EOF
}

SKILL_SCOPE="global"   # global | project
PROJECT_DIR="."
USE_LOCAL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --project)  SKILL_SCOPE="project"
                if [ $# -ge 2 ] && [ "${2#-}" = "$2" ]; then PROJECT_DIR="$2"; shift; fi ;;
    --global)   SKILL_SCOPE="global" ;;
    --local)    USE_LOCAL=1 ;;
    -h|--help)  usage; exit 0 ;;
    *)          die "알 수 없는 옵션: $1  (사용법은 --help)" ;;
  esac
  shift
done

command -v claude >/dev/null 2>&1 || die "claude CLI가 필요합니다(플러그인 설치)."

scope="user"
if [ "$SKILL_SCOPE" = "project" ]; then
  [ -d "$PROJECT_DIR" ] || die "프로젝트 디렉토리가 없습니다: $PROJECT_DIR"
  scope="local"
fi

# 마켓 소스: 기본=원격 REPO_URL, --local=이 체크아웃 디렉토리(로컬 마켓)
if [ "$USE_LOCAL" -eq 1 ]; then
  [ -f "$SRC/.claude-plugin/marketplace.json" ] || die "로컬 마켓 소스가 아닙니다(.claude-plugin/marketplace.json 없음): $SRC"
  MARKET_SRC="$SRC"
else
  MARKET_SRC="$REPO_URL"
fi

msg "플러그인 설치 (마켓: ${MARKET_NAME}, 소스: ${MARKET_SRC}, scope: ${scope})"

if claude plugin marketplace list 2>/dev/null | grep -q "${MARKET_NAME}"; then
  msg "  · 마켓이 이미 등록됨 → 갱신"
  claude plugin marketplace update "${MARKET_NAME}" >/dev/null 2>&1 || err "마켓 갱신 실패(계속 진행)"
else
  msg "  · 마켓 등록: ${MARKET_SRC}"
  claude plugin marketplace add "${MARKET_SRC}" || die "마켓 등록 실패 — git 인증(원격)·경로(로컬)를 확인하세요."
fi

msg "  · 플러그인 설치: ${PLUGIN_NAME}@${MARKET_NAME} (scope: ${scope})"
if [ "$scope" = "local" ]; then
  ( cd "$PROJECT_DIR" && claude plugin install "${PLUGIN_NAME}@${MARKET_NAME}" -y --scope local ) || die "플러그인 설치 실패."
else
  claude plugin install "${PLUGIN_NAME}@${MARKET_NAME}" -y --scope user || die "플러그인 설치 실패."
fi

msg ""
msg "✅ 설치 완료 — 새 세션에서  /${PLUGIN_NAME}:tuning-report  또는  /${PLUGIN_NAME}:inventory-report  로 호출하세요."
[ "$scope" = "local" ] && msg "   프로젝트 로컬 설치(이 프로젝트에서만·개인, 미공유): ${PROJECT_DIR%/}/.claude/settings.local.json"
msg "   갱신: claude plugin update ${PLUGIN_NAME}@${MARKET_NAME} (적용에 재시작)     제거: claude plugin uninstall ${PLUGIN_NAME}@${MARKET_NAME}"
exit 0

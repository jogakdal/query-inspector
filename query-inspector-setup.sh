#!/usr/bin/env bash
#
# query-inspector 설치 스크립트
# 기본은 플러그인 설치(마켓 대행), --skill 옵션은 스킬 직접 설치(파일 없으면 자동 clone).
#
set -eu

# ─────────────────────────────────────────────────────────────
# 설정 — 네임스페이스/저장소를 바꿀 때는 이 블록과 매니페스트를 함께 수정합니다.
#   PLUGIN_NAME : 플러그인 네임스페이스. .claude-plugin/plugin.json 의 "name"과 일치해야 함
#                 (호출은 /<PLUGIN_NAME>:tuning-report · /<PLUGIN_NAME>:inventory-report)
#   MARKET_NAME : .claude-plugin/marketplace.json 의 최상위 "name"과 일치해야 함
#   INSTALL_DIR : 스킬 직접 설치 시 ~/.claude/skills/ 아래 디렉토리명(플러그인 루트 전체를 복사)
#   REPO_URL    : 마켓 소스 / 스킬 clone 소스 (환경변수 QT_REPO_URL로 덮어쓸 수 있음)
# ─────────────────────────────────────────────────────────────
REPO_URL="${QT_REPO_URL:-git@github.com:jogakdal/query-inspector.git}"
PLUGIN_NAME="query-inspector"
MARKET_NAME="query-inspector-marketplace"
INSTALL_DIR="query-inspector"
CONFIG_EXAMPLE=".query-inspector.example.yml"
COMPONENTS="skills .claude-plugin references scripts assets ${CONFIG_EXAMPLE}"

SRC="$(cd "$(dirname "$0")" && pwd -P)"

msg() { printf '%s\n' "$*"; }
err() { printf 'error: %s\n' "$*" >&2; }
die() { err "$*"; exit 1; }

usage() {
  cat <<EOF
query-inspector 설치 스크립트

사용법:
  ./query-inspector-setup.sh                         플러그인 설치(기본·개인 글로벌). 호출: /${PLUGIN_NAME}:tuning-report · :inventory-report
  ./query-inspector-setup.sh --project [DIR]         플러그인 설치(프로젝트 로컬). 대상 프로젝트 루트에서 실행(DIR로 경로 지정 가능)
  ./query-inspector-setup.sh --skill                 스킬 직접 설치(개인 글로벌, 멀티스킬 전체 복사)
  ./query-inspector-setup.sh --skill --project [DIR] 스킬 직접 설치(프로젝트 로컬, DIR 기본=현재 디렉토리)
  ./query-inspector-setup.sh --skill --force         기존 설치를 확인 없이 덮어씀
  ./query-inspector-setup.sh --help                  이 도움말

플러그인 방식(권장): claude CLI + git 인증이 필요합니다. 이 스크립트 한 파일만 있어도 동작합니다(마켓에서 내려받음).
스킬 방식:          로컬에 파일이 없으면 저장소를 자동 clone해 복사합니다. 멀티스킬 직접 설치는 실동작 확인이 필요합니다(플러그인 방식 권장).
EOF
}

MODE="plugin"         # plugin | skill
SKILL_SCOPE="global"  # global | project
PROJECT_DIR="."
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --skill)    MODE="skill" ;;
    --plugin)   MODE="plugin" ;;
    --global)   SKILL_SCOPE="global" ;;
    --project)  SKILL_SCOPE="project"
                if [ $# -ge 2 ] && [ "${2#-}" = "$2" ]; then PROJECT_DIR="$2"; shift; fi ;;
    --force|-f) FORCE=1 ;;
    -h|--help)  usage; exit 0 ;;
    *)          die "알 수 없는 옵션: $1  (사용법은 --help)" ;;
  esac
  shift
done

# ───────── 플러그인 방식 (기본) ─────────
install_plugin() {
  command -v claude >/dev/null 2>&1 || die "claude CLI가 필요합니다(플러그인 설치). 스킬 방식은 './query-inspector-setup.sh --skill'을 쓰세요."

  local scope="user"
  if [ "$SKILL_SCOPE" = "project" ]; then
    [ -d "$PROJECT_DIR" ] || die "프로젝트 디렉토리가 없습니다: $PROJECT_DIR"
    scope="local"
  fi
  msg "플러그인 방식으로 설치합니다 (마켓: ${MARKET_NAME}, scope: ${scope})"

  if claude plugin marketplace list 2>/dev/null | grep -q "${MARKET_NAME}"; then
    msg "  · 마켓이 이미 등록됨 → 갱신"
    claude plugin marketplace update "${MARKET_NAME}" >/dev/null 2>&1 || err "마켓 갱신 실패(계속 진행)"
  else
    msg "  · 마켓 등록: ${REPO_URL}"
    claude plugin marketplace add "${REPO_URL}" || die "마켓 등록 실패 — git 인증(SSH 키/App Password)과 저장소 접근 권한을 확인하세요."
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
}

# ───────── 스킬 방식 (--skill) ─────────
install_skill() {
  local src="$SRC" tmp=""

  # 소스 확보: 로컬에 플러그인 구조(skills/)가 없으면 clone
  if [ ! -d "$SRC/skills" ]; then
    command -v git >/dev/null 2>&1 || die "git이 필요합니다(스킬 파일이 없어 clone이 필요)."
    tmp="$(mktemp -d 2>/dev/null || mktemp -d -t qtskill)"
    msg "스킬 파일이 없어 저장소를 clone합니다: ${REPO_URL}"
    git clone --depth 1 "${REPO_URL}" "$tmp" >/dev/null 2>&1 || { rm -rf "$tmp"; die "clone 실패 — git 인증·접근 권한을 확인하세요."; }
    src="$tmp"
  fi
  [ -d "$src/skills" ] || { rm -rf "$tmp"; die "skills/ 를 찾을 수 없습니다: $src"; }

  # 대상 경로(플러그인 루트 전체를 한 디렉토리에 복사 — 멀티스킬 + 공유 자산)
  local dest
  if [ "$SKILL_SCOPE" = "project" ]; then
    [ -d "$PROJECT_DIR" ] || { rm -rf "$tmp"; die "프로젝트 디렉토리가 없습니다: $PROJECT_DIR"; }
    dest="${PROJECT_DIR%/}/.claude/skills/${INSTALL_DIR}"
  else
    dest="$HOME/.claude/skills/${INSTALL_DIR}"
  fi

  # 기존 설치 처리
  if [ -e "$dest" ]; then
    if [ "$(cd "$dest" && pwd -P)" = "$(cd "$src" && pwd -P)" ]; then
      rm -rf "$tmp"; die "소스와 대상이 동일합니다: $dest"
    fi
    if [ "$FORCE" -ne 1 ]; then
      if [ -t 0 ]; then
        printf '이미 설치돼 있습니다: %s\n덮어쓸까요? [y/N]: ' "$dest"
        read yn
        case "$yn" in y|Y|yes|YES) : ;; *) rm -rf "$tmp"; die "취소되었습니다." ;; esac
      else
        rm -rf "$tmp"; die "이미 존재합니다: $dest  (덮어쓰려면 --force)"
      fi
    fi
    rm -rf "$dest"
  fi

  # 복사(플러그인 루트 구조 그대로: skills/ + .claude-plugin/ + 공유 자산)
  mkdir -p "$dest"
  for item in $COMPONENTS; do
    if [ -e "$src/$item" ]; then cp -R "$src/$item" "$dest/"; else err "구성 요소 누락(건너뜀): $item"; fi
  done
  if [ -d "$dest/scripts" ]; then
    find "$dest/scripts" -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod +x {} +
  fi

  # self-update 버전 기준 기록(매니페스트 version에서 파생)
  ver="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "$src/.claude-plugin/plugin.json" 2>/dev/null || true)"
  [ -n "$ver" ] && printf '%s\n' "$ver" > "$dest/.qt-version"

  rm -rf "$tmp"   # 임시 clone 정리(없으면 무시)

  msg ""
  msg "✅ 설치 완료: $dest"
  msg "   새 세션에서  /${INSTALL_DIR}:tuning-report  또는  /${INSTALL_DIR}:inventory-report  로 호출하세요."
  msg "   (멀티스킬 직접 설치는 실동작 확인이 필요합니다 — 안 되면 플러그인 방식을 쓰세요.)"
  [ "$SKILL_SCOPE" = "project" ] && msg "   이 프로젝트에서만 사용됩니다(다른 프로젝트엔 영향 없음)."
}

case "$MODE" in
  plugin) install_plugin ;;
  skill)  install_skill ;;
esac
exit 0

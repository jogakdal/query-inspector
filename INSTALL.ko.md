# 설치

[English](./INSTALL.md) | **한국어**

> 설치 전용 상세 문서 - 설치 스크립트와, 그 스크립트가 대신 실행하는 **수동 설치** 단계를 플러그인/스킬 두 방식 모두 설명합니다.
> 설치 후 사용/옵션/설정/Tier 3/문제 해결은 **[MANUAL.ko.md](./MANUAL.ko.md)** 를 보세요.

---

## 빠른 설치

```bash
# 플러그인 설치 (권장)
claude plugin marketplace add jogakdal/query-inspector
claude plugin install query-inspector@query-inspector-marketplace

# 또는 설치 스크립트 (저장소 clone 후)
bash query-inspector-setup.sh              # 플러그인, 개인 글로벌(기본) -> /query-inspector:tuning-report
bash query-inspector-setup.sh --project    # 플러그인, 프로젝트 로컬(이 프로젝트에서만)
bash query-inspector-setup.sh --skill      # 스킬로 직접 설치(개인 글로벌)
```

**Windows**에서는 같은 옵션으로 `query-inspector-setup.bat`을 실행합니다. 런타임 스크립트가 모두 파이썬이라 mac / Linux / Windows에서 동일하게 동작합니다(실행에 bash 불필요).

---

## 플러그인 vs 스킬

|  | 플러그인(기본)                                                    | 스킬(`--skill`) |
|---|-------------------------------------------------------------|---|
| 관리 주체 | Claude Code 플러그인 시스템                                        | `~/.claude/skills/` 아래 일반 파일 |
| 갱신 | `claude plugin update ...` (간편)                             | 파일 재복사 |
| 전제 조건 | `claude` CLI                                                | 파일 복사만(없으면 git으로 clone) |
| 필요 파일 | 설치 스크립트(`query-inspector-setup.sh`) 한 파일(나머지는 자동으로 마켓에서 내려받음) | 저장소 파일 |
| 호출 | `/query-inspector:tuning-report` / `:inventory-report`      | `/query-inspector:tuning-report` / `:inventory-report` |

갱신이 편한 **플러그인 방식을 권장**합니다.

---

## 요구사항

- **기본(Tier 1 / 2):** `git`, 그리고 `python3`(mac/linux) 또는 `python`/`py`(Windows) - 표준 라이브러리만 쓰며 추가 설치가 없습니다.
- **Tier 3(실 DB EXPLAIN, 선택):** MySQL이면 `mysql` CLI(대부분 이미 설치되어 있음) 또는 `pymysql`, PostgreSQL이면 `psql` 또는 `psycopg`, 그리고 설정 파싱용 `PyYAML`.
- **비공개** 저장소는 git 인증(SSH 키 / PAT(Personal Access Token))이 필요하고, **공개** 저장소는 필요 없습니다.

---

## A. 스크립트 설치 (권장)

설치 스크립트가 아래 B의 단계를 대신 처리합니다. 저장소를 clone했다면 루트에 이미 있고, 아니면 스크립트 파일만 내려받으세요 - [`query-inspector-setup.sh`](https://raw.githubusercontent.com/jogakdal/query-inspector/main/query-inspector-setup.sh)(Windows는 [`query-inspector-setup.bat`](https://raw.githubusercontent.com/jogakdal/query-inspector/main/query-inspector-setup.bat)). 받은 위치 또는 적용할 프로젝트 루트에서 실행하세요.

### 플러그인(기본)

```bash
bash query-inspector-setup.sh              # 개인 글로벌
bash query-inspector-setup.sh --project    # 프로젝트 로컬 - 프로젝트 루트에서 실행하거나 --project <경로> 전달
```

마켓플레이스를 등록하고 플러그인을 설치합니다. 새 세션에서 `/query-inspector:tuning-report` 또는 `/query-inspector:inventory-report`로 호출합니다.

### 스킬(`--skill`)

```bash
bash query-inspector-setup.sh --skill              # 개인 글로벌 -> ~/.claude/skills/query-inspector/
bash query-inspector-setup.sh --skill --project    # 프로젝트 로컬 -> <project>/.claude/skills/query-inspector/
bash query-inspector-setup.sh --skill --force      # 기존 설치를 확인 없이 덮어씀
```

플러그인 트리 전체(두 스킬 + 공유 자산)를 하나의 skills 디렉토리에 복사합니다. 로컬에 파일이 없으면 저장소를 자동으로 clone합니다.

### Windows

`cmd`에서 `query-inspector-setup.bat`을 실행하거나 더블클릭합니다. 옵션은 동일합니다: `query-inspector-setup.bat --project`, `--skill`, `--force`.

---

## B. 수동 설치 (스크립트 없이)

설치 스크립트는 아래 단계를 감싼 것뿐입니다. 스크립트를 쓰기 싫거나, 정확히 무슨 일이 일어나는지 보고 싶다면 직접 실행하세요.

### B-1. 플러그인 수동 설치

```bash
# 1) 이 저장소를 마켓플레이스로 등록
claude plugin marketplace add https://github.com/jogakdal/query-inspector
#    (공개 저장소는 owner/repo 축약형도 됩니다)
#    비공개 저장소: SSH URL을 대신 사용 -
#    claude plugin marketplace add git@github.com:jogakdal/query-inspector.git

# 2) 플러그인 설치
claude plugin install query-inspector@query-inspector-marketplace -y --scope user
#    프로젝트 로컬로 하려면: 프로젝트 루트에서 --scope local 사용
```

새 세션에서 `/query-inspector:tuning-report`로 호출합니다.

### B-2. 스킬 수동 설치 (mac / Linux)

```bash
# 1) 파일 확보
git clone --depth 1 git@github.com:jogakdal/query-inspector.git

# 2) 플러그인 트리 '전체'를 하나의 skills 디렉토리에 복사
mkdir -p ~/.claude/skills/query-inspector
cp -R query-inspector/{skills,.claude-plugin,references,scripts,assets,.query-inspector.example.yml} \
      ~/.claude/skills/query-inspector/

# 3) 스크립트에 실행 권한 부여
chmod +x ~/.claude/skills/query-inspector/scripts/*.py
```

프로젝트 로컬이면 `<project>/.claude/skills/query-inspector/`에 복사합니다. 호출은 `/query-inspector:tuning-report`.

> **왜 스킬 폴더만이 아니라 루트 전체를 복사하나요?**<br>
> 두 스킬(`tuning-report`/`inventory-report`)이 `references/`/`scripts/`/`assets/`를 `${CLAUDE_PLUGIN_ROOT}`로 공유하므로, 이들이 `skills/`와 같은 위치에 있어야 합니다.

---

## 갱신 / 제거

- **플러그인** 
  - 갱신: `claude plugin update query-inspector@query-inspector-marketplace`(적용에 Claude Code 재시작). 
  - 카탈로그를 먼저 새로 읽으려면: `claude plugin marketplace update query-inspector-marketplace`. 
  - 제거: `claude plugin uninstall query-inspector@query-inspector-marketplace`.
- **스킬**
  - 갱신: 복사를 다시 실행(또는 `--skill --force`). 
  - 제거: `~/.claude/skills/query-inspector/` 디렉토리 삭제.
- **자동 갱신**
  - 스킬은 실행 시 새 버전도 확인합니다. [tuning-report 매뉴얼 8절](./MANUAL-tuning-report.ko.md) 참고(두 스킬 동일).

---

## 설치 확인

```bash
/query-inspector:tuning-report --version    # 예: query-inspector v1.0.0 (plugin)
/query-inspector:tuning-report --help
```

설치 후 플러그인/스킬이 로드되려면 **claude 새 세션**이 필요합니다.

> 사용 / 옵션 / 설정 / Tier 3 / 문제 해결: **[MANUAL.ko.md](./MANUAL.ko.md)**.

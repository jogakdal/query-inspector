# 설치

[English](./INSTALL.md) | **한국어**

> 설치 전용 상세 문서 - 설치 스크립트와, 그 스크립트가 대신 실행하는 **수동 설치** 단계를 설명합니다.
> 설치 후 사용/옵션/설정/Tier 3/문제 해결은 **[MANUAL.ko.md](./MANUAL.ko.md)** 를 보세요.

---

## 빠른 설치

```bash
# 플러그인 설치 (공개 마켓플레이스에서)
claude plugin marketplace add jogakdal/query-inspector
claude plugin install query-inspector@query-inspector-marketplace

# 또는 설치 스크립트 (저장소 clone 후)
bash query-inspector-setup.sh              # 개인 글로벌(기본) -> /query-inspector:tuning-report
bash query-inspector-setup.sh --project    # 프로젝트 로컬(이 프로젝트에서만)
bash query-inspector-setup.sh --local      # 이 체크아웃을 마켓 소스로 등록(clone/포크/오프라인)
```

**Windows**에서는 같은 옵션으로 `query-inspector-setup.bat`을 실행합니다. 런타임 스크립트가 모두 파이썬이라 mac / Linux / Windows에서 동일하게 동작합니다(실행에 bash 불필요).

---

## 플러그인 전용 (`--skill` 복사 방식이 없는 이유)

query-inspector는 스킬 폴더를 손으로 복사하는 방식이 아니라 **플러그인으로** 설치합니다. 두 스킬(`tuning-report`/`inventory-report`)이 `references/`/`scripts/`/`assets/`를 `${CLAUDE_PLUGIN_ROOT}`로 공유하고, 둘 다 `/query-inspector:` 네임스페이스로 호출됩니다. 이 구조는 Claude Code가 플러그인으로 로드할 때만 해석되므로, 스킬 폴더 하나를 `~/.claude/skills/`에 복사하면 공유 자산 경로와 네임스페이스가 깨집니다. 그래서 스킬 복사 설치는 제공하지 않습니다.

저장소를 clone/포크했거나 오프라인/수정판을 설치하려면 **`--local`** 을 쓰세요. 로컬 체크아웃을 마켓 소스로 등록해 거기서 플러그인을 설치합니다 - 결과는 동일하고 네트워크가 필요 없습니다.

---

## 요구사항

- **기본(Tier 1 / 2):** `claude` CLI, `git`, 그리고 `python3`(mac/linux) 또는 `python`/`py`(Windows) - 표준 라이브러리만 쓰며 추가 설치가 없습니다.
- **Tier 3(실 DB EXPLAIN, 선택):** MySQL이면 `mysql` CLI(대부분 이미 설치되어 있음) 또는 `pymysql`, PostgreSQL이면 `psql` 또는 `psycopg`, 그리고 설정 파싱용 `PyYAML`.
- **비공개** 저장소는 git 인증(SSH 키 / PAT(Personal Access Token))이 필요하고, **공개** 저장소는 필요 없습니다.

---

## A. 스크립트 설치 (권장)

설치 스크립트가 아래 B의 단계를 대신 처리합니다. 저장소를 clone했다면 루트에 이미 있고, 아니면 스크립트 파일만 내려받으세요 - [`query-inspector-setup.sh`](https://raw.githubusercontent.com/jogakdal/query-inspector/main/query-inspector-setup.sh)(Windows는 [`query-inspector-setup.bat`](https://raw.githubusercontent.com/jogakdal/query-inspector/main/query-inspector-setup.bat)). 받은 위치 또는 적용할 프로젝트 루트에서 실행하세요.

```bash
bash query-inspector-setup.sh              # 개인 글로벌
bash query-inspector-setup.sh --project    # 프로젝트 로컬 - 프로젝트 루트에서 실행하거나 --project <경로> 전달
bash query-inspector-setup.sh --local      # 이 체크아웃을 마켓 소스로 사용(clone/포크/오프라인/검증)
```

- **기본** - 공개 마켓플레이스(`jogakdal/query-inspector`)를 등록하고 플러그인을 개인 글로벌로 설치합니다.
- **`--project [DIR]`** - 한 프로젝트에만 설치합니다(`--scope local`). 프로젝트 루트에서 실행하거나 경로를 전달하세요.
- **`--local`** - 스크립트가 있는 디렉토리를 마켓으로 등록하고(그 안에 `.claude-plugin/marketplace.json`이 있어야 함) 거기서 설치합니다. `--project`와 함께 쓰면 체크아웃에서 바로 프로젝트 로컬 설치가 됩니다.

새 세션에서 `/query-inspector:tuning-report` 또는 `/query-inspector:inventory-report`로 호출합니다.

### Windows

`cmd`에서 `query-inspector-setup.bat`을 실행하거나 더블클릭합니다. 옵션은 동일합니다: `--project`, `--local`.

---

## B. 수동 설치 (스크립트 없이)

설치 스크립트는 아래 단계를 감싼 것뿐입니다. 스크립트를 쓰기 싫거나, 정확히 무슨 일이 일어나는지 보고 싶다면 직접 실행하세요.

### B-1. 공개 마켓플레이스에서

```bash
# 1) 이 저장소를 마켓플레이스로 등록
claude plugin marketplace add https://github.com/jogakdal/query-inspector
#    (공개 저장소는 owner/repo 축약형도 됩니다: jogakdal/query-inspector)
#    비공개 저장소: SSH URL을 대신 사용 -
#    claude plugin marketplace add git@github.com:jogakdal/query-inspector.git

# 2) 플러그인 설치
claude plugin install query-inspector@query-inspector-marketplace -y --scope user
#    프로젝트 로컬로 하려면: 프로젝트 루트에서 --scope local 사용
```

새 세션에서 `/query-inspector:tuning-report`로 호출합니다.

### B-2. 로컬 체크아웃에서 (clone / 포크 / 오프라인)

```bash
# 1) 파일 확보
git clone --depth 1 git@github.com:jogakdal/query-inspector.git

# 2) 체크아웃 디렉토리를 마켓플레이스로 등록 (안에 .claude-plugin/marketplace.json 이 들어 있음)
claude plugin marketplace add ./query-inspector

# 3) 거기서 플러그인 설치
claude plugin install query-inspector@query-inspector-marketplace -y --scope user
#    프로젝트 로컬로 하려면: 프로젝트 루트에서 --scope local 사용
```

이것이 `query-inspector-setup.sh --local`이 하는 일 그대로입니다 - 어디에도 push하지 않고 수정판/오프라인 빌드를 돌릴 때 쓰세요. 호출은 `/query-inspector:tuning-report`.

> **왜 스킬 폴더만이 아니라 체크아웃 전체를 등록하나요?**<br>
> 두 스킬(`tuning-report`/`inventory-report`)이 `references/`/`scripts/`/`assets/`를 `${CLAUDE_PLUGIN_ROOT}`로 공유하고, 둘 다 `/query-inspector:` 네임스페이스 아래에 있습니다 - 이 구조는 트리를 플러그인으로 로드할 때만 해석됩니다.

---

## 갱신 / 제거

- **갱신** - `claude plugin update query-inspector@query-inspector-marketplace`(적용에 Claude Code 재시작). 카탈로그를 먼저 새로 읽으려면: `claude plugin marketplace update query-inspector-marketplace`. `--local` 설치라면 체크아웃에서 `git pull` 후 `claude plugin marketplace update ...` 와 `claude plugin update ...` 를 실행합니다.
- **제거** - `claude plugin uninstall query-inspector@query-inspector-marketplace`.
- **자동 갱신** - 스킬은 실행 시 새 버전도 확인합니다. [tuning-report 매뉴얼 8절](./MANUAL-tuning-report.ko.md) 참고(두 스킬 동일).

---

## 설치 확인

```bash
/query-inspector:tuning-report --version    # 예: query-inspector v1.0.1 (plugin)
/query-inspector:tuning-report --help
```

설치 후 플러그인이 로드되려면 **claude 새 세션**이 필요합니다.

> 사용 / 옵션 / 설정 / Tier 3 / 문제 해결: **[MANUAL.ko.md](./MANUAL.ko.md)**.

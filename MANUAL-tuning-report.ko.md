# query-inspector - tuning-report 매뉴얼

[English](./MANUAL-tuning-report.md) | **한국어**

query-inspector의 두 스킬 중 하나인 **`tuning-report`** 의 상세 매뉴얼입니다.<br> 
이 스킬을 실행하면 **git 기반 변경분의 SQL/ORM 쿼리를 추출해 튜닝(인덱스 누락 / N+1 / 안티패턴 등)** 리포트를 작성합니다.<br> 
튜닝 대신 프로젝트 내 쿼리의 목록을 뽑아 보려면 **[`inventory-report`](./MANUAL-inventory-report.ko.md)** 스킬을 사용하세요.

> 두 스킬 개요: [MANUAL.ko.md](./MANUAL.ko.md)<br>
> 소개: [README.ko.md](./README.ko.md)<br>
> 전체 설치 안내: [INSTALL.ko.md](./INSTALL.ko.md)<br>
> 설계: [DESIGN.md](./DESIGN.md)<br>
> 실행 중 빠른 참조: `--help`(= `assets/help.md`)

---

## 1. 개요

`tuning-report`는 수동으로 호출합니다.<br> 
기본 흐름은 **"마지막 튜닝 이후" 변경분만** 보는 증분 방식입니다(전체도 가능). **변경분을 커밋하기 직전에 실행하면 가장 유용**합니다 - 성능 문제를 저장소에 들어가기 전에 잡을 수 있습니다.<br> 
코드를 직접 수정하지 않고 제안이 담긴 리포트를 산출합니다.<br> 
실행 스크립트가 모두 파이썬이라 **mac / Linux / Windows 공통**으로 동작합니다.

### 주요 기능
- **주요 표적**: 
  - 인덱스 누락(바로 쓸 수 있는 `CREATE INDEX` 제안)
  - N+1 조회
  - 흔한 안티패턴(인덱스 무력화 조건 / 선행 와일드카드 `LIKE '%..'` / 방언 불일치 문법 / 불필요한 `SELECT *` 등)
- **증분 + 이전 제안 검증**: 지난 제안이 실제 수정 및 반영이 되었는지를 파악합니다. 이전 제안에 대한 검증은 이번에 수정되지 않은 파일도 대상이 됩니다.
- **단계 자동 조절(3-Tier)**: 정적 휴리스틱 -> 스키마 인덱스 대조 -> (선택) 실 DB EXPLAIN
- **폭넓은 스택**: 
  - `Kotlin / Java` + MyBatis / 네이티브 SQL / JPA/Hibernate(파생 메서드 / `@Query` / QueryDSL / Kotlin JDSL)
  - **Python(Django / SQLAlchemy)**: 지원하지만 주력 스택만큼 검증되지는 않음
  - 방언(MySQL / MariaDB 등) 자동 감지
- **바로 사용 가능한 상세 리포트**: 위험도순 요약 + 실행 계획(파일 / 라인 / 복붙용 코드 / DDL)
- **안전장치**: DB 실제 접근은 opt-in, 프로덕션 DB 접근 차단, 읽기 전용 쿼리만 수행

---

## 2. 설치

갱신이 편한 **플러그인(기본)** 을 권장합니다. `--skill`은 파일을 직접 설치합니다.

```bash
bash query-inspector-setup.sh              # 플러그인, 개인 글로벌(기본) -> /query-inspector:tuning-report
bash query-inspector-setup.sh --project    # 플러그인, 프로젝트 로컬(이 프로젝트에서만)
bash query-inspector-setup.sh --skill      # 스킬로 직접 설치
```
**Windows**에서는 같은 옵션으로 `query-inspector-setup.bat`을 실행합니다.<br> 
`--project`로 설치하실 때는 대상 프로젝트 루트에서 실행하세요(다른 위치면 `--project <경로>`).

**요구사항:** 
- `git`
- `python3`(mac/linux) 또는 `python`/`py`(Windows) - 표준 라이브러리만 
- Tier 3(실 DB EXPLAIN, 선택)는 
  - MySQL이면 `mysql` CLI 또는 `pymysql`
  - PostgreSQL이면 `psql` 또는 `psycopg`
  - `PyYAML`
- 비공개 저장소는 git 인증이 필요하고, 공개 저장소는 필요 없습니다.

> 스킬은 이 도구들을 **자동으로 설치하지 않습니다**. `git`/`python`이 없으면 스킬이 동작하지 않으므로 직접 설치해야 하며, Tier 3 드라이버(`pymysql`/`psycopg`)가 없으면 `mysql`/`psql` CLI로 대체하고, CLI도 없으면 **Tier 2로 자동 강등**합니다(리포트에 명시). `PyYAML`은 Tier 3 프로파일 파싱에만 필요하며, 없으면 설치를 안내합니다.

**갱신:** `claude plugin update query-inspector@query-inspector-marketplace` -> claude 재시작 (참고로 claude CLI 내 `/plugin`은 관리 UI만 열고 갱신하지 않음)<br> 
**제거:** `claude plugin uninstall query-inspector@query-inspector-marketplace`<br> 
자동 갱신: [8절](#8-자동-업데이트)

> **전체 설치 안내 -> [INSTALL.ko.md](./INSTALL.ko.md)**

---

## 3. 빠른 시작

새 Claude Code 세션에서 (설치 방식과 무관하게) 네임스페이스로 호출합니다.
```
/query-inspector:tuning-report            # 마지막 튜닝 이후 변경분(첫 실행이면 범위 확인)
```
`tuning-report`는 첫 실행이면 규모를 알려주고 (전체 점진 / 최근 커밋 / 특정 경로) 중 선택하게 합니다.<br> 
결과:
- 터미널 요약(위험도순 상위 목록)
- 상세 리포트: `docs/query-inspector/tuning-reports/<timestamp>.md`

```bash
# 전형적인 커밋 전 흐름
cp .query-inspector.example.yml .query-inspector.yml   # 선택 - 없어도 기본값으로 동작
git add .
claude
> /query-inspector:tuning-report
```

---

## 4. 명령/옵션 레퍼런스

|                          옵션                           | 설명 |
|:-----------------------------------------------------:|------|
|                         (없음)                          | 마지막 튜닝 이후 변경분(증분). 첫 실행이면 범위 확인 |
|                        `--all`                        | 이전 수행/baseline 무시, **전체** 쿼리 소스 스캔 |
|                      `--staged`                       | staged 변경분만 |
|                    `--range <rev>`                    | 지정 범위(예: `main..HEAD`, `HEAD~3`) |
|                   `--files <경로...>`                   | 특정 파일만 |
|                     `--continue`                      | 진행 중인 점진적 전체 스캔의 다음 도메인부터 |
|           `--depth static\|schema\|explain`           | 깊이 강제(Tier1/2/3) |
|                   `--db <profile>`                    | 실 DB EXPLAIN 심화(opt-in) |
| `--dialect mysql\|mariadb\|postgresql\|oracle\|ansi`  | 방언 강제(기본 자동 감지) |
|                `--lang ko\|en\|ja\|zh`                | 출력 언어(기본 `report.language=auto`) |
|                     `--no-state`                      | 상태 읽기/쓰기 없이 1회성 |
|                    `--reset-state`                    | 상태 초기화(다음 실행이 전체) |
|                  `--no-update-check`                  | 이번 실행에서 새 버전 확인 건너뜀 |
|                      `--version`                      | 설치된 스킬 버전 출력(예: `query-inspector v1.0.0 (plugin)`) |
|                    `--help`, `-h`                     | 도움말 |

**옵션 그룹**

- **대상 범위** (`--all` / `--staged` / `--range` / `--files` / `--continue`):
  - 무엇을 스캔할지 결정합니다. 아무 것도 주지 않으면 **증분**(마지막 튜닝 이후 변경분)입니다.
  - 명시 범위(`--all` / `--range` / `--files` / `--staged`)를 주면 증분 baseline을 무시하고 그 범위만 봅니다.
  - `--continue`는 진행 중인 점진적 전체 스캔을 다음 도메인부터 이어서 수행합니다.
- **튜닝 깊이 / DB** (`--depth` / `--db` / `--dialect`):
  - `--depth`는 Tier를 강제로 지정합니다(`static`=Tier 1, `schema`=Tier 2, `explain`=Tier 3). 미지정이면 가능한 최고 Tier를 자동 선택하고, 조건이 안 되면 강등합니다.
  - `--db <profile>`은 실 DB EXPLAIN(Tier 3)을 켭니다. `<profile>`은 `.query-inspector.yml`의 `db.profiles`에 정의한 이름입니다(설정과 동작은 [7절](#7-tier-3---실-db-explain-선택)).
  - `--dialect`는 방언 자동 감지 대신 방언을 직접 지정합니다.
- **상태(증분)** (`--no-state` / `--reset-state`):
  - `--no-state`는 상태 파일을 읽지도 쓰지도 않는 1회성 실행입니다.
  - `--reset-state`는 상태를 초기화합니다(다음 실행할 때 전체 스캔).
- **출력 / 기타** (`--lang` / `--no-update-check` / `--version` / `--help`):
  - `--lang`은 출력 언어를 고정합니다(기본은 `report.language=auto`).
  - `--no-update-check`는 이번 실행에서 새 버전 확인을 건너뜁니다.
  - `--version` / `--help`는 버전 / 도움말을 출력하고 종료합니다.

**자주 쓰는 조합**
- 이전 수행과 무관하게 **매번 전체**: `--all`(상태도 안 남기려면 `--all --no-state`).
- 브랜치 리뷰: `--range main..HEAD`.
- 특정 실행을 실 실행계획으로 심화: `--db <profile>`([7절](#7-tier-3---실-db-explain-선택)).

---

## 5. 동작 방식

`tuning-report`는 프로젝트의 변경분에서 쿼리를 수집하고 추출한 뒤 SQL을 재구성하고, 3단계(Tier)로 분석해 리포트로 만듭니다.

- **증분(기본)**: 상태파일(`docs/query-inspector/tuning-reports/state.json`)의 마지막 튜닝 커밋 이후 변경분 + 미커밋 + 새 파일. **첫 실행**은 자동 전체 대신 범위를 확인합니다.
- **점진적 전체 스캔**: 전체가 부담이면 도메인(최상위 패키지/디렉토리) 단위로 한 배치씩 수행하게 하고, `--continue`로 이어서 수행하게 할 수 있습니다.
- **3-Tier 자동 강등**: 
  - (1) Tier1 정적 휴리스틱(항상) -> (2) Tier2 스키마 인덱스 대조(엔티티 / 마이그레이션 / DDL 자동 감지 또는 `--db`) -> (3) Tier3 실 DB EXPLAIN(`--db`). 
  - 제공된 정보에 맞춰 올리고, 조건이 안 되면 낮춰 진행하며 리포트에 명시합니다.
- **방언 자동 감지**: 
  - 빌드 의존성 -> datasource URL -> Hibernate 설정 -> 마이그레이션 특성 순 
  - 판별 실패 시 MySQL 폴백합니다.
  - `--dialect`로 방언을 직접 지정 가능합니다.
- **이전 제안 검증(follow-up)**: 
  - 지난 `open_suggestions`를 현재 코드/스키마와 대조하여 상태를 표시합니다(✅ 해결 / ⚠️ 미반영 / ❓ 확인필요). 
  - 첫 실행 시 또는 `--all` 옵션을 주면 이 내용이 생략됩니다.

---

## 6. 리포트 해석

결과는 리포트로 제공되며 코드를 직접 수정하지 않습니다.

- **터미널 요약**: 위험도순 상위 N개(`terminal_top_n`, 기본 10)를 터미널에 출력합니다. 각 행에 심각도 / 이슈 / 위치 / 최종 수정자 / 신뢰도를 표시합니다.
- **상세 리포트 파일**: 
  - `docs/query-inspector/tuning-reports/<timestamp>.md` 파일로 리포트를 생성합니다. 
  - 전체 예시: [examples/sample-report.md](./examples/sample-report.md)
- **실행 계획(Action Items)**: 
  - 개발자나 개발자의 AI에게 그대로 넘겨 착수할 수 있게 정리합니다. 
  - 라벨: `[자동적용]`(기계적 반영 안전) / `[검토후]`(설계 판단) / `[확인후]`(전제 확인) 
  - 인덱스 추가 등의 작업을 위해 복붙용 DDL을 제공합니다.
- **최종 수정자**: 각 쿼리 원천 `파일:라인`을 마지막으로 작성/수정한 사람을 git blame 정보로 표시합니다. 커밋이 없는 경우 "미커밋(작업 중)"을 표시합니다.
- **신뢰도 라벨**: 
  - `EXACT`(원문) / `INFERRED`(ORM 번역 추론) / `AMBIGUOUS`(동적 분기 대표 시나리오) 
  - ORM 추론 / 동적 쿼리는 `show_sql` 등으로 실제 SQL 확인을 권장합니다.

### 리포트 예시 (증분 2회차)

```markdown
# Query Tuning Report - 증분(변경 파일 2)
- 심각도(미해결): 🔴 3 / 🟡 2 / ⚪ 1   /   이전 제안: ✅ 2건 해결 / ⚠️ 2건 여전히 미반영(2회째)

## 🔴 [critical] 인덱스 누락 - FK `orders.user_id` - OrderMapper.xml (SCHEMA-CONFIRMED / 2회째)
- 왜 치명적: N+1 자식 쿼리라 user N명마다 `orders` 풀스캔.
- 제안:  CREATE INDEX idx_orders_user_id ON orders (user_id);
- 검증(Tier 3, --db): EXPLAIN에서 `type: ALL -> ref` 확인.

## ✅ 실행 계획 (Action Items)
- [ ] [자동적용] 인덱스 마이그레이션 추가 - 새 파일 V3__orders_indexes.sql (2회째 리마인드)
      CREATE INDEX idx_orders_user_id        ON orders (user_id);
      CREATE INDEX idx_orders_status_created ON orders (status, created_at);
```

ORM 동적 쿼리는 100% 재구성이 불가능하므로, 모든 추론 쿼리에 신뢰도 라벨을 붙이고 `AMBIGUOUS` 항목은 실제 SQL 검증 방법을 함께 안내합니다.

---

## 7. Tier 3 - 실 DB EXPLAIN (선택)

인덱스 제안을 실 실행계획으로 확증하고 싶을 때 사용합니다.<br> 
**프로덕션 DB 접속 금지 / 읽기전용 / opt-in**이 강제됩니다.

```bash
/query-inspector:tuning-report --db dev
```

### 프로파일 설정(`.query-inspector.yml`)

`--db <이름>`이 가리키는 프로파일을 `db.profiles` 아래에 정의합니다.

```yaml
db:
  env_file: .env            # 자격증명을 담은 파일(gitignore). 셸 환경변수가 우선
  prod_guard: true          # 프로덕션 호스트/이름 패턴 원천 차단(기본 켬)
  profiles:
    dev:                                 # -> `--db dev`로 사용
      url_env: QT_DEV_DB_URL             # 접속 URL을 읽을 환경변수(또는 .env). URL 자체는 설정에 넣지 않음
      readonly: true                     # 읽기 전용 계정 사용 권장
      allow_explain_analyze: false       # EXPLAIN ANALYZE(실제 실행) 허용 여부
      host_allowlist: [localhost, 127.0.0.1, dev-db.internal]  # 이 목록 밖 호스트는 차단(사설 IP 등 개발 DB를 추가)
      host_denylist_patterns: ["*prod*", "*live*", "*production*"]  # 이름 패턴 차단
      statement_timeout_ms: 3000         # 문장 타임아웃
      max_rows: 100000                   # 예상 스캔 rows 상한(초과 시 경고)
```

- `url_env` / `env_file`: 접속 URL은 환경변수나 `.env`에서만 읽습니다(URL을 설정 파일에 넣지 않음). 자세한 조달 순서는 아래에서 설명합니다.
- `host_allowlist`: 비어 있지 않으면 목록 밖 호스트를 모두 차단합니다. **개발 DB(사설 IP 등)를 반드시 추가**하세요.
- `allow_explain_analyze`: `true`일 때만 `--analyze`(EXPLAIN ANALYZE)를 허용하며, 허용되어 있더라도 트랜잭션을 열고 무조건 롤백합니다.
- `statement_timeout_ms` / `max_rows`: 문장 타임아웃과 예상 스캔 rows 상한(가드레일).

### 접속 정보 조달(우선순위)
1. 프로파일 `url_env` 환경변수(스킬이 `.env` 자동 로드)
2. **프로젝트 datasource 설정 자동 추출**:
   - `application.yml`/`.properties`(및 `application-{local,dev}.*`)의 `spring.datasource.*`(또는 `r2dbc.*`)에서 자동으로 읽어 씁니다(운영 설정 `application-prod*`는 제외). 
   - **접속 전에 "host:port/db로 진행할까요?"를 확인**합니다.
3. 그래도 없으면 스킬이 **준비 후 다시 실행하도록 안내**합니다(보안상 **비밀번호를 대화창에서 직접 받지 않음**). 사용자는 아래 중 하나로 미리 준비합니다:
   - **`.env`에 저장(권장)**: **터미널에서** `python3 scripts/set_db_credential.py --var QT_DEV_DB_URL`(Windows는 `python`/`py`). 접속 URL을 **숨김 입력**으로 받아 `.env`에 저장합니다(숨김 입력이라 실제 터미널이 필요하며, claude의 비대화형 실행에서는 거부됩니다).
   - **셸 `export`**: `export QT_DEV_DB_URL="postgresql://..."`(셸 환경변수가 `.env`보다 우선).

- **비밀번호 특수문자** - `#`/`@`/`!` 등 URL 예약문자가 있으면 percent-encoding이 필요합니다(`#`->`%23`). 
- `set_db_credential.py`로 저장하면 **자동 인코딩**되므로 비밀번호를 그대로 입력하면 됩니다.

### 안전장치
- 프로덕션 호스트(이름 패턴/공인 IP)와 `SELECT`/`EXPLAIN` 외 문장은 차단됩니다(읽기 전용). 
- `host_allowlist`가 설정된 프로파일은 그 목록 밖 호스트를 차단하므로, **개발 DB(사설 IP 등)는 프로파일 `host_allowlist`에 추가**하면 됩니다.
- `EXPLAIN ANALYZE`(실제 실행)는 프로파일 `allow_explain_analyze: true` + 확인 시에만 수행되며, 트랜잭션을 열고 무조건 롤백합니다.
- 접속 URL/비밀번호는 리포트/로그에 남기지 않습니다.
- 드라이버/CLI가 모두 없으면 Tier2로 자동 강등됩니다(리포트에 사유 명시).

실습용 실 검증 환경: [`examples/docker-mysql/`](./examples/docker-mysql/), [`examples/docker-postgres/`](./examples/docker-postgres/).

---

## 8. 자동 업데이트

스킬은 실행 시 **하루 1회** 새 버전이 있는지 조용히 확인합니다(네트워크 / 인증 / git 실패 시 그냥 넘어감).
- **스킬 방식(`--skill`)**: 새 버전이 있으면 사용자 동의를 받아 즉시 갱신합니다. 갱신 내용은 다음 스킬 호출부터 적용됩니다(보통 claude 재시작 불필요, 반영되지 않으면 claude를 새로 시작).
- **플러그인 방식**: 
  - `claude plugin update query-inspector@query-inspector-marketplace`를 실행하도록 안내합니다(적용하려면 claude 재시작). 
  - 또는 `/plugin` -> Marketplaces에서 auto-update를 켜두면 세션 시작 시 자동으로 최신화됩니다.
- 끄기: `--no-update-check` 또는 설정 `report.update_check: false`

---

## 9. 설정 (`.query-inspector.yml`)

없어도 기본값으로 동작합니다. 조정하려면 템플릿을 복사하세요.
```bash
cp .query-inspector.example.yml .query-inspector.yml
```
주요 키: `stacks`(어댑터), `dialect`(기본 `auto`), `schema`(Tier2 소스), `depth`, `report`(`dir`/`language`/`min_severity`/`terminal_top_n`/`update_check`), `severity_rules`(휴리스틱별 심각도), `state`(증분), `db`(Tier3 프로파일).

`report.dir`은 리포트 루트(기본 `docs/query-inspector`)이고, 튜닝 리포트와 `state.json`은 그 하위 `tuning-reports/`에 저장됩니다.

> 🔒 이 파일들은 **튜닝 대상 프로젝트의 저장소**에 생성됩니다.<br> 
> `--db` 옵션 사용 시 접속 URL은 환경변수/`.env`로만 들어가고(설정 파일에는 변수 이름만), 스킬이 `.env`를 그 프로젝트 `.gitignore`에 자동 추가합니다.<br>
> 버전 관리에서 빼두시기를 권장하며, `.query-inspector.yml`에도 실제 URL을 넣지 않는 것이 좋습니다.

---

## 10. FAQ / 문제 해결

| 증상 | 해결 |
|------|------|
| 설치된 버전을 알고 싶음 | `/query-inspector:tuning-report --version`(또는 `claude plugin list`, 캐시 경로 `~/.claude/plugins/cache/query-inspector-marketplace/query-inspector/<버전>/`). 리포트 헤더에도 표시됩니다 |
| 명령이 안 보임 | 새 세션인지, 플러그인은 `/plugin list`에 `query-inspector`, 스킬은 `~/.claude/skills/query-inspector/`(Windows `%USERPROFILE%\.claude\skills\query-inspector\`) 확인 |
| `python3`를 못 찾음(주로 Windows) | `python` 또는 `py` 사용(`py --version`). git/python만 있으면 bash 없이 동작 |
| "git 저장소가 아닙니다" | git 저장소에서 실행(`git init`) |
| Tier3에서 `pymysql`/`PyYAML` 없음 | `mysql` CLI로 폴백 또는 Tier2 강등. 필요 시 `pip install pymysql pyyaml` |
| Tier3 접속 URL 파싱 실패 | 비밀번호의 예약문자(`#`,`@`,`!` 등)를 percent-encoding(또는 `set_db_credential.py`로 저장 -> 자동 인코딩) |
| 프로덕션 차단됨/allowlist 밖 | 대상이 dev면 프로파일 `host_allowlist`에 그 호스트 추가 |
| 전체가 아니라 일부만 검토됨 | 증분 모드(정상). 전체는 `--all` |
| 리포트가 안 보임 | `docs/query-inspector/tuning-reports/<timestamp>.md` 확인(경로는 `report.dir`) |

---

설계 배경은 [DESIGN.md](./DESIGN.md), 변경 이력은 [CHANGELOG.md](./CHANGELOG.md)를 참고하세요.

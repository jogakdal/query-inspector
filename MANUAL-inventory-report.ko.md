# query-inspector - inventory-report 매뉴얼

[English](./MANUAL-inventory-report.md) | **한국어**

query-inspector의 두 스킬 중 하나인 **`inventory-report`** 매뉴얼입니다.<br> 
**프로젝트의 쿼리(ORM이 생성할 쿼리 포함)를 추출해 목록(카탈로그)으로** 만듭니다. **튜닝이 아니라 목록화**를 수행합니다.<br> 
안티패턴 분석과 수정 제안이 필요하면 **[`tuning-report`](./MANUAL-tuning-report.ko.md)** 스킬을 사용하세요.

> 두 스킬 개요: [MANUAL.ko.md](./MANUAL.ko.md)<br>
> 소개: [README.ko.md](./README.ko.md)<br>
> 전체 설치 안내: [INSTALL.ko.md](./INSTALL.ko.md)<br>
> 설계: [DESIGN.md](./DESIGN.md)<br>
> 실행 중 빠른 참조: `--help`(= `assets/help.md`).

---

## 1. 개요

`inventory-report`는 **프로젝트에 포함되어 실행되는 쿼리의 카탈로그**를 만듭니다.<br> 
명시적 SQL과 ORM / 동적 쿼리가 생성하는 SQL 모두 대상이 됩니다.<br>
Kotlin/Java + MyBatis / 네이티브 SQL / JPA/Hibernate(파생 메서드 / `@Query` / QueryDSL / Kotlin JDSL) 등 폭넓은 스택을 지원합니다. **Python(Django / SQLAlchemy)도 지원하지만 주력 스택만큼 검증되지는 않았습니다.** 방언은 자동 감지합니다.<br> 
주된 산출물은 **모든 쿼리의 본문(전문)** 이며, 각 쿼리의 출처와 인덱스 커버 여부를 함께 리포팅합니다.<br> 
목록화 스킬이므로 심각도를 매기지 않고 수정도 제안하지 않습니다.<br> 
실행 스크립트가 모두 파이썬으로 작성되어 **mac / Linux / Windows 공통**으로 동작합니다.

### 주요 리포트 내용
- **쿼리 본문 전문(주 산출물)**: 모든 쿼리의 추론 SQL 본문을 전문으로 추출, 동적 쿼리는 대표 시나리오 2~3개를 각각 전문으로 추출
- **쿼리별 상세 정보**: 목적/용도, 대상 테이블(+스키마), 유형(`SELECT`/`INSERT`/`UPDATE`/`DELETE`/`DDL`), 원천 소스(`파일:라인` + 어댑터 + 신뢰도 라벨), **최종 수정자**(git blame), 접근 컬럼, 인덱스 커버
- **인덱스 커버**: 접근 경로(`WHERE` / `JOIN` / `ORDER BY` 컬럼)가 인덱스로 커버되는지 여부 (`✅ <인덱스>` / `❌ 미커버` / `❓ 스키마 미확인`)

---

## 2. 설치

query-inspector는 플러그인으로 설치합니다(스킬 복사 설치는 없음 - 두 스킬이 자산을 한 네임스페이스 아래에서 공유). 공개 마켓 대신 내 체크아웃에서 설치하려면 `--local`을 쓰세요.

```bash
bash query-inspector-setup.sh              # 개인 글로벌(기본) -> /query-inspector:inventory-report
bash query-inspector-setup.sh --project    # 프로젝트 로컬(이 프로젝트에서만)
bash query-inspector-setup.sh --local      # 이 체크아웃에서 설치(clone/포크/오프라인)
```
**Windows**에서는 같은 옵션으로 `query-inspector-setup.bat`을 실행합니다.<br> 
`--project`로 설치하실 때는 대상 프로젝트 루트에서 실행하세요(다른 위치면 `--project <경로>`).

**요구사항:** 
- `git`
- `python3`(mac/linux) 또는 `python`/`py`(Windows) - 표준 라이브러리만 
- 인덱스 커버를 실 DB로 확정하려면 
  - MySQL이면 `mysql` CLI 또는 `pymysql`
  - PostgreSQL이면 `psql` 또는 `psycopg`
  - `PyYAML`
- 비공개 저장소는 git 인증이 필요하고, 공개 저장소는 필요 없습니다.

> 스킬은 이 도구들을 **자동으로 설치하지 않습니다**. `git`/`python`이 없으면 스킬이 동작하지 않으므로 직접 설치해야 하며, 실 DB 조회용 드라이버(`pymysql`/`psycopg`)가 없으면 `mysql`/`psql` CLI로 대체하고, CLI도 없으면 코드의 스키마 정보만 사용하거나 인덱스 커버를 `❓ 스키마 미확인`으로 남깁니다. `PyYAML`은 `--db` 프로파일 파싱에만 필요하며, 없으면 설치를 안내합니다.

**갱신:** `claude plugin update query-inspector@query-inspector-marketplace` -> claude 재시작 (참고로 claude CLI 내 `/plugin`은 관리 UI만 열고 갱신하지 않음)<br> 
**제거:** `claude plugin uninstall query-inspector@query-inspector-marketplace`<br> 
자동 갱신: [8절](#8-자동-업데이트)

> **전체 설치 안내 -> [INSTALL.ko.md](./INSTALL.ko.md)**

---

## 3. 빠른 시작

새 Claude Code 세션에서 (설치 방식과 무관하게) 네임스페이스로 호출합니다.
```
/query-inspector:inventory-report                     # 프로젝트 전체(기본)
/query-inspector:inventory-report --range main..HEAD  # 이 브랜치가 바꾼 쿼리만
/query-inspector:inventory-report --staged            # staged 변경분만
```
기본은 프로젝트 전체를 대상으로 합니다.<br> 
**변경분만**(PR/브랜치) 뽑으려면 `--range` / `--staged` / `--files`로 범위를 좁히면 되고, 출력 형식은 같고 범위만 줄어듭니다.<br> 
결과:
- 터미널 요약(유형/테이블별 쿼리 수 + 상위 목록)
- **모든 쿼리의 본문 전문**을 담은 상세 리포트: `docs/query-inspector/inventory-reports/inventory-<timestamp>.md`

---

## 4. 명령/옵션 레퍼런스

|                          옵션                           | 설명 |
|:-----------------------------------------------------:|------|
|                         (없음)                          | 프로젝트 **전체** 쿼리 목록화(전문) |
|                        `--all`                        | 기본과 동일(전체 명시) |
|                    `--range <rev>`                    | 지정 범위의 쿼리만(예: `main..HEAD`) |
|                   `--files <경로...>`                   | 특정 파일만 |
|                      `--staged`                       | staged 변경분만 |
|                     `--continue`                      | 진행 중인 점진적 전체 스캔의 다음 도메인부터 |
|                   `--db <profile>`                    | 인덱스 커버를 실 DB 스키마로 확정(opt-in) |
| `--dialect mysql\|mariadb\|postgresql\|oracle\|ansi`  | 방언 강제(기본 자동 감지) |
|                `--lang ko\|en\|ja\|zh`                | 출력 언어(기본 `report.language=auto`) |
|                  `--no-update-check`                  | 이번 실행에서 새 버전 확인 건너뜀 |
|                      `--version`                      | 설치된 스킬 버전 출력(예: `query-inspector v1.0.0 (plugin)`) |
|                    `--help`, `-h`                     | 도움말 |

**옵션 그룹**

- **대상 범위** (`--all` / `--staged` / `--range` / `--files` / `--continue`):
  - 목록화할 범위를 결정합니다. 아무 것도 지정하지 않으면 **프로젝트 전체** 범위로 수행합니다.
  - `--range` / `--files` / `--staged`를 주면 그 범위에서 **변경된 쿼리만** 목록화합니다.
  - `--continue`는 진행 중인 점진적 전체 스캔을 다음 도메인부터 이어서 수행합니다.
- **DB / 방언** (`--db` / `--dialect`):
  - `--db <profile>`은 인덱스 커버리지를 실 DB 스키마로 확정합니다(opt-in). `<profile>`은 `.query-inspector.yml`의 `db.profiles`에 정의한 이름입니다(설정은 [7절](#7-인덱스-커버용-실-db-스키마-선택)).
  - `--dialect`는 방언 자동 감지 대신 방언을 직접 지정합니다.
- **출력 / 기타** (`--lang` / `--no-update-check` / `--version` / `--help`):
  - `--lang`은 출력 언어를 강제합니다(기본은 `report.language=auto`).
  - `--no-update-check`는 이번 실행에서 새 버전 확인을 건너뜁니다.
  - `--version` / `--help`는 버전 / 도움말을 출력하고 종료합니다.

---

## 5. 동작 방식

`inventory-report`는 프로젝트 내 소스 코드의 변경 내역을 수집하고 쿼리를 추출한 뒤 SQL을 재구성하고, 각 쿼리에 접근 경로와 인덱스 커버를 부가해 목록으로 만듭니다.

- **기본 대상(범위)은 프로젝트 전체:** 
  - 대상이 "프로젝트 내 모든 쿼리"입니다. 
  - 대형 저장소는 **도메인(최상위 패키지 또는 디렉토리, 예: `order` / `user` / `payment`) 단위로 나눠 한 번에 한 도메인씩** 목록화하고, `--continue` 옵션으로 다음 도메인을 이어갑니다. 
  - `--range`/`--files`/`--staged` 옵션을 사용하면 해당 범위만 목록화합니다.
- **인덱스 커버:** 
  - 각 쿼리가 사용하는 컬럼(`WHERE` / `JOIN` / `ORDER BY`)을 커버하는 인덱스가 있는지 확인합니다.
  - 인덱스 정보는 코드의 스키마 / 엔티티 / 마이그레이션에서 자동으로 찾거나, `--db`로 실 DB 스키마에서 가져옵니다. 
  - 스키마가 없으면 인덱스 항목만 `❓ 스키마 미확인`으로 남기고 목적 / 테이블 / 본문은 그대로 채웁니다.
- **판정 없음:** 목록으로 정리할 뿐, 심각도를 매기거나 수정을 제안하지 않습니다.
- **방언 자동 감지:**
  - 빌드 의존성 -> datasource URL -> Hibernate 설정 -> 마이그레이션 특성 순으로 파악합니다. 
  - 판별 실패 시 MySQL 폴백합니다. 
  - `--dialect` 옵션으로 강제 지정 가능합니다.

---

## 6. 인벤토리 해석

- **터미널 요약**: 유형 / 테이블별 쿼리 수 + 상위 목록. 헤더에 사용 스킬 버전 표시
- **상세 파일**: `docs/query-inspector/inventory-reports/inventory-<timestamp>.md` 파일에 모든 쿼리의 본문 전문 수록

각 쿼리 정보 항목:
- **목적/용도**: 메서드명 / 매퍼 id / 주변 코드에서 추론한 한 줄 설명(불확실하면 불확실하다고 표기)
- **대상**: 테이블(+ 알 수 있으면 스키마 / DB)
- **유형**: `SELECT` / `INSERT` / `UPDATE` / `DELETE` / `DDL`
- **원천**: `파일:라인`(+ 메서드/매퍼 id), 어댑터, 신뢰도 라벨(`EXACT` / `INFERRED` / `AMBIGUOUS`)
- **최종 수정자**: 원천 `파일:라인`을 마지막으로 작성/수정한 사람, 미커밋은 "미커밋(작업 중)"
- **접근 컬럼**: `WHERE` / `JOIN` / `ORDER BY` 컬럼
- **인덱스 커버**: `✅ <인덱스>` / `❌ 미커버` / `❓ 스키마 미확인`
- **쿼리 본문 전문**: 추론 SQL 본문을 전문으로 작성(동적 쿼리는 대표 시나리오 2~3개를 각각 전문으로 작성)

> ⚠️ **전체 쿼리 본문은 주된 산출물**이므로 쿼리가 많다는 이유로 본문을 생략 / 요약 / `...`로 축약하거나 대표 몇 개만 리포팅하지 않습니다.<br> 
> 쿼리가 많을 것으로 예상되면 **도메인 배치 / 대상 범위 지정 + `--continue` 옵션**을 사용해 주세요.

---

## 7. 인덱스 커버용 실 DB 스키마 (선택)

인덱스 커버는 기본적으로 스키마 파일이나 엔티티 / 마이그레이션에서 확인합니다.<br>
**실 데이터베이스 스키마**로 확정하려면 `--db` 옵션을 사용합니다.

```bash
/query-inspector:inventory-report --db dev
```

### 프로파일 설정(`.query-inspector.yml`)

`--db <프로파일명>`이 가리키는 프로파일을 `db.profiles` 아래에 정의합니다.

```yaml
db:
  env_file: .env            # 자격증명을 담은 파일(gitignore). 셸 환경변수가 우선
  prod_guard: true          # 프로덕션 호스트/이름 패턴 원천 차단(기본 켬)
  profiles:
    dev:                                 # -> `--db dev`로 사용
      url_env: QT_DEV_DB_URL             # 접속 URL을 읽을 환경변수 이름(예시 - 원하는 이름으로). URL 값은 설정에 넣지 않음
      readonly: true                     # 읽기 전용 계정 사용 권장
      host_allowlist: [localhost, 127.0.0.1, dev-db.internal]  # 이 목록 밖 호스트는 차단(사설 IP 등 개발 DB를 추가)
      host_denylist_patterns: ["*prod*", "*live*", "*production*"]  # 이름 패턴 차단
      statement_timeout_ms: 3000         # 문장 타임아웃
```

- `--db`는 인덱스 커버리지 확정을 위해 **스키마만 조회**합니다(EXPLAIN을 실행하지 않음).
- `host_allowlist`: 비어 있지 않으면 목록 밖 호스트를 모두 차단합니다. **개발 DB(사설 IP 등)를 반드시 추가**하세요.

### 안전장치
**프로덕션 금지 / 읽기전용 / opt-in**
- 프로덕션 호스트(이름 패턴 / 공인 IP)와 `SELECT`/`EXPLAIN` 외 문장은 차단됩니다. 
- 개발 DB 호스트는 프로파일 `host_allowlist`에 추가해 주세요.
- 접속 URL은 실행 시 프로파일 `url_env` 변수(셸 환경변수 또는 `.env`)에서 읽습니다. 없으면 프로젝트 datasource 설정에서 자동 추출하고(운영 제외, 접속 전 확인), 그래도 없으면 스킬이 **준비 후 다시 실행하도록 안내**합니다(보안상 **비밀번호를 대화창에서 직접 받지 않습니다**).
- 사용자는 아래 중 한 방법으로 접속 URL을 **미리** 준비합니다:
  - **`.env`에 저장(권장)**: 
    - **터미널에서** `python3 scripts/set_db_credential.py --var QT_DEV_DB_URL`(Windows는 `python`/`py`) 
    - 접속 URL을 **숨김 입력**(화면·기록에 미표시)으로 받아 `.env`에 저장하며, `--var`에는 프로파일의 `url_env`와 **같은 이름**을 적습니다(위 예시라면 `QT_DEV_DB_URL`). 
    - 예약문자(`#`/`@`/`!` 등)는 자동으로 percent-encoding합니다. 
    - 숨김 입력이라 실제 터미널이 필요하며, claude의 비대화형 실행에서는 거부됩니다.
  - **셸 `export`**: `export QT_DEV_DB_URL="postgresql://..."`(값은 실행 시 읽히며, 셸 환경변수가 `.env`보다 우선).
- 접속 URL / 비밀번호는 리포트 / 로그에 남기지 않습니다 **(AI가 읽지 않고 내부 DB 접속 스크립트가 직접 읽습니다)**.

---

## 8. 자동 업데이트

스킬은 실행 시 **하루 1회** 새 버전이 있는지 조용히 확인합니다(네트워크/인증/git 실패 시 그냥 넘어감).
- `claude plugin update query-inspector@query-inspector-marketplace`를 실행하도록 안내합니다(적용하려면 claude 재시작).
- 또는 `/plugin` -> Marketplaces에서 auto-update를 켜두면 세션 시작 시 자동으로 최신화됩니다.
- `--local` 설치라면 체크아웃에서 `git pull` 후 `claude plugin marketplace update ...` 와 `claude plugin update ...` 를 실행합니다.
- 끄기: `--no-update-check` 또는 설정 `report.update_check: false`

---

## 9. 설정 (`.query-inspector.yml`)

없어도 기본값으로 동작합니다. 조정하려면 템플릿을 복사하세요.
```bash
cp .query-inspector.example.yml .query-inspector.yml
```
인벤토리에 관련된 키: `stacks`(어댑터), `dialect`(기본 `auto`), `schema`(인덱스 커버 소스), `report`(`dir`/`language`/`terminal_top_n`/`update_check`), `db`(실 스키마 프로파일)

`report.dir`은 리포트 루트(기본 `docs/query-inspector`)이고, 인벤토리 리포트는 그 하위 `inventory-reports/`에 저장됩니다.

> 🔒 이 파일들은 **목록화 대상 프로젝트의 저장소**에 생성됩니다.<br> 
> `--db` 옵션 사용 시 접속 URL은 환경변수/`.env`로만 들어가고(설정 파일에는 변수 이름만), 스킬이 `.env`를 그 프로젝트 `.gitignore`에 자동 추가합니다.<br>
> 버전 관리에서 빼두시기를 권장하며, `.query-inspector.yml`에도 실제 URL을 넣지 않는 것이 좋습니다.

---

## 10. FAQ / 문제 해결

| 증상 | 해결 |
|------|------|
| 설치된 버전을 알고 싶음 | `/query-inspector:inventory-report --version`(또는 `claude plugin list`). 인벤토리 헤더에도 표시됩니다 |
| 명령이 안 보임 | 새 세션인지, 플러그인은 `/plugin list`에 `query-inspector`, 스킬은 `~/.claude/skills/query-inspector/`(Windows `%USERPROFILE%\.claude\skills\query-inspector\`) 확인 |
| `python3`를 못 찾음(주로 Windows) | `python` 또는 `py` 사용(`py --version`). git/python만 있으면 bash 없이 동작 |
| "git 저장소가 아닙니다" | git 저장소에서 실행(`git init`) |
| 본문이 잘린 듯/일부 쿼리만 보임 | 설계상 상세 파일에는 모든 쿼리의 본문 전문이 담깁니다. 일부만 나온 느낌이면 배치 경계이니 `--continue`로 이어서(대형 저장소는 도메인 단위로 목록화) |
| 인덱스 커버가 `❓ 스키마 미확인` | 스키마를 못 찾음. 스키마 파일/엔티티/마이그레이션을 추가하거나 `--db <profile>`로 실 스키마 확정 |
| 인벤토리가 안 보임 | `docs/query-inspector/inventory-reports/inventory-<timestamp>.md` 확인(경로는 `report.dir`) |

---

설계 배경은 [DESIGN.md](./DESIGN.md), 변경 이력은 [CHANGELOG.md](./CHANGELOG.md)를 참고하세요.

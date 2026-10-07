---
name: tuning-report
description: >-
  변경분(staged diff 또는 지정 범위)에서 SQL과 ORM이 생성할 쿼리를 추출해
  N+1/인덱스 미스/비-SARGable 조건 등 안티패턴을 커밋 전에 튜닝한다.
  스키마(DDL/엔티티) 제공 시 인덱스 대조까지, 개발 DB 접속 제공 시 EXPLAIN 심화까지
  깊이를 자동 조절한다. Kotlin/Java + MyBatis / 네이티브 SQL / JPA/Hibernate(파생 메서드/@Query/QueryDSL/Kotlin JDSL)를 기본 지원하고,
  마이그레이션(DDL)으로 확장된다. 커밋 직전 수동 호출. 리포트 출력 언어는 다국어(i18n).
  트리거 - KO: "쿼리 튜닝", "N+1", "인덱스 점검", "슬로우 쿼리", "SQL 리뷰", "이 변경 쿼리 괜찮아?";
  EN: "query tuning", "tune this query", "check N+1", "index review", "slow query", "review my SQL changes",
  "will this ORM query be slow".
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/db_guard.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/db_guard.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/db_guard.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/run_explain.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/run_explain.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/run_explain.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/set_db_credential.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/set_db_credential.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/set_db_credential.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/version_check.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/version_check.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/version_check.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/blame_author.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/blame_author.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/blame_author.py *)
---

# query-inspector : tuning-report

변경분에서 쿼리 생성 코드를 골라 **안티패턴 튜닝 리포트**를 내는 스킬. `code-review`의 "쿼리 특화 + 변경분 한정" 형제. 배경/아키텍처는 [`DESIGN.md`](../../DESIGN.md).

> **먼저 공통 절차를 따른다:** 기본 원칙/설정/인자 처리(`--help`/`--version`)/업데이트 체크/Stage 0(수집)/0.5(방언)/1(추출)/2(재구성)는 **[`references/pipeline-common.md`](../../references/pipeline-common.md)**에 있다. 이 문서를 먼저 수행한 뒤, 아래 **Stage 3 -> 3.5 -> 4**로 튜닝 리포트를 완성한다. 같은 플러그인의 `inventory-report` 스킬은 튜닝 대신 쿼리 목록화를 한다.

## 호출

```
/query-inspector:tuning-report                      # 마지막 튜닝 이후 변경분(첫 실행이면 범위 확인)
/query-inspector:tuning-report --all                # 전체 쿼리 관련 소스 강제(이전 제안 검증 생략)
/query-inspector:tuning-report --staged             # staged 변경분만
/query-inspector:tuning-report --range main..HEAD   # 지정 범위
/query-inspector:tuning-report --files <경로...>    # 특정 파일만
/query-inspector:tuning-report --depth static|schema|explain   # 깊이 강제
/query-inspector:tuning-report --db <profile>       # DB 프로파일로 EXPLAIN 심화(opt-in)
/query-inspector:tuning-report --dialect mysql|mariadb|postgresql|oracle|ansi
/query-inspector:tuning-report --continue           # 진행 중인 점진 전체 스캔의 다음 도메인
/query-inspector:tuning-report --lang ko|en|ja|zh   # 출력 언어 강제(기본 report.language=auto)
/query-inspector:tuning-report --no-state           # 상태 읽기/쓰기 없이 1회성
/query-inspector:tuning-report --reset-state        # 상태 초기화(다음 실행이 전체)
/query-inspector:tuning-report --no-update-check    # 새 버전 확인 건너뜀
/query-inspector:tuning-report --version | --help
```

공통 인자/설정/업데이트 체크/`--help`/`--version` 처리는 `references/pipeline-common.md` 참조.

---

## Stage 3 - 튜닝 분석 (3-Tier, 자동 강등)

깊이는 `depth` 설정/`--depth` 인자로 정하되, 조건 미충족 시 자동 강등한다.

- **Tier 1 - 정적 휴리스틱 (항상 동작, DB 불필요).** `references/heuristics.md` 카탈로그로 안티패턴을 탐지한다. 기본이자 중심.
- **Tier 2 - 스키마 컨텍스트.** 엔티티(`@Entity`/`@Table`)/마이그레이션은 소스에서 **자동 감지**하고, `schema.*` 설정이나 `--db` 실 DB 조회로 보강해 WHERE/JOIN/ORDER BY 컬럼의 **인덱스 존재 여부**를 대조한다. **`missing_index`(인덱스 누락)는 이 스킬의 대표 표적이므로 최우선 점검** - 이 도구의 주된 동기가 "인덱스 없이 배포"였다 - 커버되지 않는 컬럼(조합)에 **구체적 `CREATE INDEX` DDL(컬럼 순서/트레이드오프 포함)**을 제안한다. 같은 변경분의 마이그레이션과 교차해 "이번 변경이 필요로 하는 인덱스가 빠졌는지"를 본다. 규칙: `references/tier2-index-matching.md`. **`--db`를 제공하면 실 DB에서 스키마(`SHOW INDEX`/`information_schema`)를 직접 조회**하므로 DDL/엔티티 없이도 대조된다(라이브 스키마 + 이번 마이그레이션 델타). 이때 Tier2/Tier3가 함께 충족.
- **Tier 3 - 실 DB EXPLAIN (`--db`, opt-in).** 아래 가드레일을 거쳐 `EXPLAIN`으로 실행계획을 수집하고 같은 접속으로 스키마도 조회해 Tier2를 채운다. `run_explain.py`(pymysql 우선 + `mysql` CLI 폴백).

각 이슈에 `heuristics.md`의 ID/심각도(`severity_rules`로 오버라이드)/근거/수정 제안을 채운다.

### Tier 3 - 실 DB EXPLAIN (옵션, 가드레일)

`--db <profile>`가 있을 때만. **의존성:** 설정(`.query-inspector.yml`) 파싱에 **PyYAML** 필요(없으면 `db_guard.py`가 종료코드 2), 실행은 `pymysql` 드라이버 또는 `mysql` CLI 중 하나. 어느 쪽도 없으면 **조용히 넘기지 말고** 설치(`pip install pyyaml pymysql` 또는 `mysql` CLI)를 안내한 뒤 **Tier2로 강등**한다. **반드시 아래 순서:**

0. **자격증명 확보(우선순위).** 접속 URL을 다음 순서로: **(1)** 프로파일 `url_env` 환경변수(스크립트가 프로젝트 루트 `.env`도 자동 로드, 셸 env 우선) -> **(2)** 프로젝트 datasource 설정 자동 추출 -> **(3)** 사용자에게 요청. **어느 경로든** 아래 1단계(db_guard)가 프로덕션 차단/읽기전용을 동일 검증한다.
   - **(2) datasource 자동 감지:** `application.yml`/`application.properties`(및 `application-{local,dev}.yml`)의 `spring.datasource.url`/`username`/`password`(또는 `spring.r2dbc.*`)를 활용. **`run_explain.py`에 `--source-config <설정파일>`을 넘기면** 스크립트가 그 파일에서 접속 정보를 직접 읽어 접속한다(URL/비밀번호를 대화/프로세스 인자에 노출 안 함). `${ENV[:기본]}` placeholder는 환경변수로 치환. **`application-prod*.yml` 등 운영 설정은 자동 사용 금지.**
   - **접속 전 확인:** 소스에서 찾았으면 접속 전 "`host:port/db`(계정 `user`)로 EXPLAIN을 진행할까요?"를 확인(프로덕션 오접속 방지 - db_guard 차단과 별개의 이중 확인).
   - **(3) 사용자 요청 시:** `.env` 저장/셸 `export` 우선 권장(비번이 대화에 안 남게). 가려 넣으려면 **`! python3 "${CLAUDE_PLUGIN_ROOT}/scripts/set_db_credential.py" --var QT_DEV_DB_URL`**(Windows는 `python`/`py`; 숨김 입력 -> `.env` 0600; 비대화형 거부).
   - **입력/추출한 자격증명은 리포트/상태/로그에 남기지 않는다**(호스트/DB명만, 비번 마스킹).
1. `scripts/db_guard.py`로 프로파일 검증. **미통과 시 즉시 중단**하고 Tier2 강등.
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/db_guard.py" --profile <profile> --config .query-inspector.yml --sql-file <추출된_select.sql>
   ```
   - 프로덕션 호스트/이름 패턴/`SELECT`/`EXPLAIN` 외 문장/denylist 매칭이면 차단.
2. 통과한 SELECT만 `run_explain.py`로 `EXPLAIN`(비실행). **Stage 0.5 감지 방언을 반드시 `--dialect`로 전달**(미전달 시 기본 `mysql`이라 MariaDB에서 실패 가능).
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run_explain.py" --profile <profile> --config .query-inspector.yml --sql-file <추출된_select.sql> --dialect <mysql|mariadb|postgresql> [--source-config <application-local.yml 등>] [--analyze]
   ```
   - MySQL/MariaDB/PostgreSQL을 지원한다(감지 방언을 `--dialect`로 전달). 그 외(Oracle 등)는 Tier3 미구현(종료코드 3 -> Tier2 유지).
   - `EXPLAIN ANALYZE`(실제 실행)는 프로파일 `allow_explain_analyze: true` + 사용자 확인 + `--analyze`일 때만. 트랜잭션 열고 무조건 롤백.
3. 어떤 쿼리를 어느 DB에 던졌는지 **감사 로그로 리포트에 기록**.
4. DML/DDL은 **실행하지 않는다**(정적/스키마 분석만).

> 접속 실패/권한 부족/타임아웃이면 조용히 넘기지 말고 Tier2 강등, 리포트에 사유.

## Stage 3.5 - 이전 제안 검증 (follow-up)

상태파일의 `open_suggestions`(지난 튜닝 미해결 제안)를 현재 코드/스키마와 대조해 반영 여부를 판정한다. 규칙: `references/state-and-followup.md`.

- 제안 지문(`<id>|<scope>|<target>`, 라인 제외)으로 추적.
- 해결 판정 예: `missing_index` -> 인덱스가 DDL/마이그레이션/`@Index`에 생겼는가 / `n_plus_one` -> `@EntityGraph`/`join fetch`/배치 도입 / `dialect_pipe_concat` -> `CONCAT` 전환.
- **해결**은 "이전 제안 검증"에 ✅, **미해결**은 `open` 유지 + **상단 ⚠️ 리마인드**("N회째 미반영"), **애매**는 ❓확인필요.
- 상태파일이 없으면(첫 실행) **또는 `--all`(전체 재검토)이면** 이 단계를 건너뛴다 - "처음부터 전체를 보는" 실행이므로 이전 제안 검증 없이 새로 진단(리포트에 "이전 제안 검증" 섹션 미포함).

## Stage 4 - 리포트 생성 + 상태 저장

`${CLAUDE_PLUGIN_ROOT}/assets/report_template.md`를 채워 두 곳에 출력한다.

1. **터미널 요약** - 위험도순 상위 `terminal_top_n`개(기본 10). `min_severity` 하한 적용.
2. **상세 리포트 파일** - `report.dir`의 `tuning-reports/`(기본 `docs/query-inspector/tuning-reports/`) 아래 `<timestamp>.md`. 이력/캐시 겸용.

리포트에는 반드시 포함: **사용한 스킬 버전**(헤더 - `version_check.py ... --local`로 확인), 대상 범위(증분/전체 + baseline)/파일/쿼리 수/라벨 분포, 사용된 깊이(및 강등 사유), 감지된 방언(및 근거), **이전 제안 검증**(상태가 있고 `--all`이 아닐 때만), **실행 계획(Action Items)**, 이슈별 원천/**최종 수정자**/근거/수정안/신뢰도. 심각(critical) 이슈가 있으면 종료 신호를 남겨 훅/CI가 감지할 수 있게 한다(선택).

**최종 수정자** - 각 이슈 원천 `파일:라인`에 대해 `blame_author.py`(git blame)로 마지막 작성/수정자를 조회해 포함. 한 파일 여러 라인은 한 번에:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/blame_author.py" --file <경로> --lines <n1,n2,...> --json   # Windows는 python 또는 py
```
`author`(+`date`)를 "최종 수정자: 이름 (YYYY-MM-DD)"로, `committed:false`면 "미커밋(작업 중)". git 정보 없으면 생략(이메일 기본 생략).

**실행 계획(Action Items)** - 요약 다음. 개발자나 **그 개발자의 AI 에이전트에게 그대로 전달해 착수**할 목록을 심각도 그룹(🔴 이번 배포 필수 / 🟡 곧 / ⚪ 여유)으로. 각 항목: `- [ ]` + 적용 라벨(`[자동적용]`/`[검토후]`/`[확인후]`) + `파일:라인` + 근거 이슈번호 + (가능하면) 복붙용 코드/DDL. 인덱스 추가처럼 안전한 건 `[자동적용]`으로 완성 DDL 제시. 이 목록은 "제안"이며 스킬이 자동 반영하지 않는다.

**상태 저장** - 리포트 직후 `<report.dir>/state.json` 갱신(`references/state-and-followup.md`): `last_tuned_commit`=현재 HEAD(+dirty), `last_report`, `updated_at`, `open_suggestions`=미해결 + 새 발견(해결분 제거). **단 `--all`은 처음 실행처럼** 이전 것과 대조/누적하지 않고 이번 발견분으로 새로 기록. 기본 로컬(gitignore), `state.shared: true`면 커밋 대상. `--no-state`면 저장 안 함. **점진 스캔 중이면** `scan_progress`도 갱신(처리 도메인을 `domains_done`으로, 남은 게 없으면 제거 후 baseline 확정). **리포트/상태 커밋 방지:** `state.shared`가 false면 `report.dir`에 `.gitignore`(`*`)가 없으면 생성.

---

## 지금 되는 것 / 한계

- ✅ Stage0 수집, 방언 자동 감지(MySQL/MariaDB/PostgreSQL), `mybatis`/`native-sql`/`jpa`(추론) 추출, Tier1 휴리스틱 + Tier2 인덱스 대조, Tier3 실 DB EXPLAIN(`--db` opt-in), 증분/점진 + follow-up, 리포트 + 실행 계획.
- 🔎 `jpa`/동적 쿼리는 추론(`INFERRED`/`AMBIGUOUS`)이며 `show_sql` 검증을 함께 안내(과신 금지).
- 🟠 방언 심화는 MySQL/MariaDB/PostgreSQL 지원(Oracle은 스텁). Python(Django/SQLAlchemy) 어댑터는 확장으로 제공(주력 JVM 스택만큼 검증되지는 않음). Node 등 그 외 스택은 미구현 - `references/adapters/_template.md`로 확장.

범위를 벗어난 요청은 **할 수 있는 만큼만 하고 한계를 분명히 밝힌다.** 없는 정확도를 지어내지 않는다.

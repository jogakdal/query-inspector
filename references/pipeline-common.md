# 공통 파이프라인 (tuning-report / inventory-report 공용)

이 문서는 `query-inspector` 플러그인의 **두 스킬이 공유하는 절차**다. 각 스킬(`skills/tuning-report/SKILL.md`/`skills/inventory-report/SKILL.md`)은 **먼저 이 문서를 따른 뒤** 모드별 단계로 진행한다.

> **경로 규칙(멀티스킬):** 공유 자산(`scripts/`/`references/`/`assets/`)은 **플러그인 루트**에 있으므로 항상 **`${CLAUDE_PLUGIN_ROOT}/...`로 참조**한다. 각 스킬의 `${CLAUDE_SKILL_DIR}`는 자기 디렉토리(`skills/<skill>/`)라 공유 자산을 못 가리킨다.

## 기본 원칙 (항상 지킬 것)

1. **지정된 범위만 본다.** 기본은 변경분(마지막 튜닝 이후)이고, 전체 코드베이스 무분별 스캔이 아니다. **첫 실행/`--all`은 예외** - 사용자가 선택한 범위(전체 포함)를 따른다. 확정된 범위 밖으로 넘지 말 것.
2. **과신하지 않는다.** ORM 추론은 근사다. 모든 추출 쿼리에 신뢰도 라벨(`EXACT`/`INFERRED`/`AMBIGUOUS`)을 붙이고, 불확실하면 그렇게 말한다.
3. **DB는 opt-in, 프로덕션은 원천 차단.** 실 DB 접근은 사용자가 `--db`로 명시할 때만. 반드시 `scripts/db_guard.py`를 먼저 통과시킨다.
4. **깊이는 자동 강등하되, 이상은 사용자에게 묻는다.** 단순 조건 미충족(예: `--db` 미제공, 스키마 없음)은 조용히 하위 Tier로 강등하고 리포트에 명시한다. 그러나 **사용자가 요청한 심화(`--db`/`--depth explain`)가 이상으로 막히면** - 접속 실패/권한 부족/**대상 테이블이 실 DB에 없음**/**실 DB 스키마가 코드/마이그레이션과 현저히 불일치** - 조용히 fallback하지 말고 **상황과 원인 후보를 알려 대화식으로 확인**한다. 어느 경우든 조용히 실패하지 않는다.
5. **출력 언어를 맞춘다(i18n).** 리포트/터미널 요약**뿐 아니라 사용자에게 하는 모든 발화**(첫 실행 범위 확인, 배치 진행/완료 안내, 확인 요청, 경고, 강등 사유 등)를 `report.language`(기본 `auto` = 사용자 대화 언어)로 작성한다. 단 휴리스틱 ID/신뢰도 라벨/설정 키/어댑터명/심각도 토큰(`critical`/`warn`/`info`)은 **언어 중립 식별자**로 그대로 둔다. (Claude Code 하네스 시스템 메시지는 스킬 밖이라 제어 불가.) 상세: `references/i18n.md`.
6. **경로는 `${CLAUDE_PLUGIN_ROOT}` 기준 / 스크립트는 파이썬(크로스플랫폼).** 실행 스크립트(`collect_diff.py`/`db_guard.py`/`run_explain.py`/`set_db_credential.py`/`version_check.py`/`blame_author.py`)는 모두 **`${CLAUDE_PLUGIN_ROOT}/scripts/`** 아래에 있고 절대경로로 실행한다.
   - **파이썬 명령은 OS마다 다르다.** mac/linux는 `python3`, **Windows는 대개 `python` 또는 `py`**(py 런처)다. 실행 전 사용 가능한 명령을 확인해 **있는 것으로 호출**한다. 아래 예시는 `python3`로 적지만 Windows에서는 `python`/`py`로 바꾼다.
   - 각 스킬 `allowed-tools`에 세 명령(`python3`/`python`/`py`)을 모두 선언해 어느 OS에서도 매칭되게 한다.

## 설정

**프로젝트 루트의 `.query-inspector.yml`**을 먼저 찾고, 없으면 **`${CLAUDE_PLUGIN_ROOT}/.query-inspector.example.yml`의 기본값**을 사용한다(프로젝트에 설정을 두지 않아도 동작). `stacks`/`dialect`/`schema`/`depth`/`report`/`severity_rules`/`db`/`state`를 반영한다. 인자는 설정을 오버라이드한다.

## 공통 인자 처리 (모든 스킬)

- **`--help`/`-h`/`help`:** `${CLAUDE_PLUGIN_ROOT}/assets/help.md`를 바탕으로 도움말을 출력하고 **즉시 종료**(수집/분석 없음). `help.md`는 영어(정본)지만 **출력층**이라 `report.language`가 영어가 아니면 그 언어로 렌더한다(옵션/플래그/경로 등 식별자는 그대로).
- **`--version`:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/version_check.py" --skill-dir "${CLAUDE_PLUGIN_ROOT}" --local`로 **버전을 출력하고 즉시 종료**. 출력 예: `query-inspector v1.0.0 (plugin)`.
- **`--self-diagnose-internal`(내부 전용/undocumented):** 정상 실행에 더해 **자가 진단 리포트**를 추가 생성한다(스킬 자신의 실행 환경/지침 품질/버그/개선점을 관찰해 로컬에 기록, 온라인 전송 없음). 절차/관찰 항목/저장 규칙은 `references/self-diagnostic.md`. 이 플래그와 자가 진단은 help/README/MANUAL에 **노출하지 않는다**(사용자 대면 도움말에서 제외).

## Stage 0 이전 - 업데이트 체크 (하루 1회 / 조용히 / 선택)

스킬 시작 시(하루 1회) 새 버전이 있는지 **조용히** 확인한다. 설정 `report.update_check: false`이거나 `--no-update-check`면 건너뛴다. **네트워크/인증/git 부재로 실패하면 조용히 무시**하고 본래 작업을 진행한다.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/version_check.py" --skill-dir "${CLAUDE_PLUGIN_ROOT}" --json   # Windows는 python 또는 py
```

- `update_available: false`(또는 `checked: false`) -> **아무 말 없이** Stage 0으로.
- `method: "skill"` + `update_available: true` -> **"새 버전 {remote_version}이 있습니다. 지금 업데이트할까요?"** 를 묻고, 동의 시 `--apply --json`으로 self-update. 적용 후 본문/`references`/`scripts`는 다음 발동부터 반영(트리거/권한 변경 릴리스는 새 세션 필요).
- `method: "plugin"` + `update_available: true` -> 안내만: "`claude plugin update query-inspector@query-inspector-marketplace` 실행 후 재시작하거나, `/plugin` -> Marketplaces에서 auto-update를 켜세요."

업데이트 체크는 **정보 제공/제안**이며 사용자 동의 없이 갱신하지 않는다(즉시 재확인은 `--force`).

## Stage 0 - 대상 범위 결정 + 변경분 수집

`scripts/collect_diff.py`를 실행한다. **기본은 "마지막 튜닝 이후" 증분** - 상태파일(`<report.dir>/tuning-reports/state.json`)의 `last_tuned_commit` 이후 커밋분 + 미커밋 + 새 파일. **상태가 없으면(첫 사용) 자동 전체 대신 사용자에게 범위를 확인**한다 - 규모(파일/도메인 수)를 알리고 **(a) 전체 스캔(점진적: 도메인 단위 한 배치씩) (b) 최근 커밋 범위 (c) 특정 도메인/경로** 중 고르게 한다(명시 인자가 있으면 그대로). **진행 중인 점진 스캔(`scan_progress`)이 있으면 이어서 진행할지 묻고, `--continue`면 다음 도메인부터.** 규칙/배치/재개: `references/state-and-followup.md`.

```bash
# 파이썬 명령: mac/linux는 python3, Windows는 python 또는 py
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py"              # baseline 있으면 그 이후, 없으면 전체 소스 목록
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py" --all        # 전체 강제
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py" --staged     # staged만
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py" --range main..HEAD
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py" --files path/a.xml
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py" --count-only  # 규모만(첫 실행 범위 확인용)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py" --continue    # 점진 스캔 재개: 다음 도메인
```

- 출력은 파일 유형별 분류: `source` / `mybatis-xml` / `migration-sql` / `sql` / `config` / `other`. **쿼리 무관 변경(문서/정적 리소스 등)은 조기 제외.**
- 증분이 누락 없이 동작하려면 상태가 정확해야 한다(Stage 4에서 저장). `--all`이면 전체 재검토.
- diff만으로 ORM 시그니처/엔티티 매핑/MyBatis `resultMap`을 알 수 없으므로 **관련 파일은 전체를 Read**한다. 전체 모드는 diff가 없으니 목록의 각 파일을 Read해 쿼리 지점을 찾는다.

## Stage 0.5 - 방언 결정

`dialect`가 `auto`(기본)이면 `references/dialect-detection.md` 규칙으로 추론한다:
1. `--dialect` 인자 또는 설정 명시값이 있으면 그대로.
2. 없으면: 빌드 의존성(`build.gradle(.kts)`/`pom.xml`) -> datasource URL(`application.yml/properties`의 `jdbc:*`) -> Hibernate `dialect` 설정 -> 마이그레이션/SQL 특성 순.
3. 다중/충돌/미검출이면 **MySQL 폴백**, 방언 의존 규칙은 보수적(ANSI 안전 패턴)으로 적용하고 근거/불확실성을 리포트에 남긴다.

결정된 방언의 `references/dialects/<dialect>.md`를 이후 단계 참고로 로드한다.

## Stage 1 - 쿼리 원천 식별/추출 (어댑터 라우팅)

`stacks` 설정에 따라 각 변경 파일을 어댑터로 라우팅하고 규칙 파일을 읽어 적용한다.

| 파일 유형 | 어댑터 | 규칙 파일 | 상태 |
|-----------|--------|-----------|-----|
| MyBatis XML(`<select>`...), `@Select`/`@Insert`... | `mybatis` | `references/adapters/mybatis.md` | ✅ 완전 |
| SQL 문자열, `JdbcTemplate`, `@Query(nativeQuery=true)`, 마이그레이션 내 DML | `native-sql` | `references/adapters/native-sql.md` | ✅ 완전 |
| JPA `@Query`(JPQL)/파생 메서드/`@EntityGraph`/QueryDSL/**Kotlin JDSL** | `jpa` | `references/adapters/jpa.md` | ✅ **기본 활성**(추론/라벨 보수적) |
| Flyway/Liquibase DDL | `migration` | `references/adapters/migration.md` | ✅ Tier2 인덱스 소스(자동 감지) |
| Django ORM(QuerySet/모델/`migrations/*.py`) | `python-django` | `references/adapters/python-django.md` | 확장(`stacks`에 추가 시) |
| SQLAlchemy(`session.query`/`select`/모델/Alembic `versions/*.py`) | `python-sqlalchemy` | `references/adapters/python-sqlalchemy.md` | 확장(`stacks`에 추가 시) |

- **jpa 어댑터(기본 활성):** `jpa.md`대로 추론. 실 SQL은 Hibernate 생성이라 라벨을 보수적으로(`INFERRED`/`AMBIGUOUS`) 두고 `show_sql` 검증 안내(과신 금지). JPA 미사용 프로젝트엔 대상 파일이 없어 자연히 건너뜀. **migration**은 `stacks` 활성 시 튜닝 대상, 비활성이어도 Tier2 인덱스 소스로 자동 감지(`tier2-index-matching.md`).
- 각 추출 결과에 **원천(파일:라인)** 과 **신뢰도 라벨**을 붙인다.
- Spring Data JPA/Kotlin JDSL(`com.linecorp.kotlinjdsl`)/QueryDSL이 `build.gradle(.kts)`/`pom.xml`에서 감지되면 별도 설정 없이 추론(패턴은 `jpa.md`).
- **python-django(확장):** `manage.py`/`settings.py`(`INSTALLED_APPS`/`DATABASES`)/`pyproject.toml`/`requirements*.txt`에서 `django` 의존이 감지되면, `stacks`에 `python-django`를 추가해 분석한다(규칙은 `python-django.md`). Django 미사용 프로젝트엔 대상이 없어 자연히 건너뜀.
- **python-sqlalchemy(확장):** `pyproject.toml`/`requirements*.txt`에서 `sqlalchemy`(또는 `alembic`)가 감지되면, `stacks`에 `python-sqlalchemy`를 추가해 분석한다(규칙은 `python-sqlalchemy.md`).
- **트레이드오프(설계):** 방언 판정/스키마 인벤토리/쿼리 추출은 스크립트가 아니라 **LLM이 파일을 읽어 수행**한다(`collect_diff.py`만 스크립트). 대형 프로젝트에선 `--count-only`로 규모를 먼저 파악하고 **점진 배치**(도메인 단위)로 처리량을 통제한다.

## Stage 2 - 예상 쿼리 재구성 (필요 시)

명시적 SQL은 그대로(`EXACT`). ORM/동적 쿼리는 어댑터 규칙에 따라 **생성될 SQL 형태로 재구성**한다.

- MyBatis 동적 태그(`<if>`/`<foreach>`/`<choose>`)/QueryDSL/Kotlin JDSL의 동적 필터는 **대표 시나리오 2~3개**로 전개(전체 경우의 수 X). 라벨 `AMBIGUOUS`.
- **경계 시나리오 포함:** 동적 조건이 **모두 빠지는 경우**(전 조건 null -> WHERE 없는 전건 조회)도 대표 시나리오에 반드시 포함해 `unbounded_result`/풀스캔 위험을 표기한다.
- 바인드 값이 필요하면 대표/샘플 값을 가정하고 그 가정을 리포트에 적는다.

---

여기까지가 공통이다. 이후 단계는 각 스킬 문서로 돌아간다:
- **튜닝 리포트** -> `skills/tuning-report/SKILL.md`의 Stage 3(3-Tier 분석)/3.5(follow-up)/4(리포트).
- **쿼리 인벤토리** -> `skills/inventory-report/SKILL.md`의 인벤토리 파이프라인.

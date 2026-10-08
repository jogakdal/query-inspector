# Tier 2 - 인덱스 대조 엔진

스키마(DDL/엔티티/마이그레이션)에서 **인덱스 인벤토리**를 구성하고, 각 쿼리의 **접근 경로**(WHERE/JOIN/ORDER BY)와 매칭해 `missing_index`(*)/`order_by_filesort`를 판정하고 **구체적 인덱스**를 제안한다. `SKILL.md` Stage 3의 Tier2가 이 문서를 따른다.

## 1. 스키마 소스 -> 인덱스 인벤토리

인덱스 인벤토리는 아래 소스를 병합해 만든다. **`--db` 프로파일이 있으면 실 DB에서 스키마를 직접 조회하는 것이 최우선/최정확 소스**다 - 사용자가 DDL/엔티티를 따로 제공하지 않아도 인덱스 대조가 된다(실제 배포된 스키마가 진실의 원천).

| 소스 | 우선 | 인덱스 신호 / 수집 방법 |
|---|---|---|
| **실 DB (라이브, `--db`)** | * 최우선 | `SHOW INDEX FROM <t>` / `information_schema.statistics`(인덱스) / `information_schema.columns`(컬럼/타입). **db_guard를 통과한 읽기 전용 조회**로 수집 |
| 마이그레이션(이번 diff) | | `V*.sql`의 `CREATE/DROP INDEX`를 시간순 누적 = 이번 배포의 **델타**. 관례 경로 **자동 감지** |
| 엔티티(JPA) / **자동 감지** | | 설정 없이도 소스에서 `@Entity`/`@Table(indexes=@Index)`/`@Id`/`@Column(unique)`/`@JoinColumn`(FK) 스캔 -> 테이블/컬럼/명시 인덱스 |
| 모델(Django) / **자동 감지** | | 소스에서 필드 `db_index=True`/`unique=True`, `Meta.indexes`(`models.Index`)/`constraints`/`unique_together`, FK/OneToOne(**기본 인덱스 생성**) 스캔. `migrations/*.py`의 `AddIndex`/`RemoveIndex`는 델타 |
| 모델(SQLAlchemy) / **자동 감지** | | 소스에서 `Column(index=True)`/`unique=`, `__table_args__`(`Index`/`UniqueConstraint`), `primary_key` 스캔. **FK는 자동 인덱스 없음**(Django와 반대 - PostgreSQL은 FK 인덱스 미생성). Alembic `versions/*.py`의 `op.create_index`는 델타 |
| DDL 파일 | | `schema.ddl` 지정 또는 관례 경로. `PRIMARY KEY`, `UNIQUE`, `CREATE [UNIQUE] INDEX`, `CREATE TABLE` 내 `KEY`/`INDEX`, `FOREIGN KEY`(SQL 방언(dialect)에 따라 자동 인덱스 여부 다름) |

- **소스 자동 감지:** 엔티티(JPA `@Entity`/`@Table` 애노테이션)와 마이그레이션/DDL을 **설정 없이도 프로젝트 소스에서 자동 감지**한다(SQL 방언 감지와 같은 원리 - `dialect-detection.md`). 감지 경로는 Flyway/Liquibase 관례(`**/db/migration/V*.sql`/`**/db/changelog/**`)**뿐 아니라 일반 SQL 경로(`**/resources/**/*.sql`/`**/sql/**`, 예: `sql/create/NN_*.sql`/`sql/migration/*.sql`)**도 포함한다(비-Flyway 프로젝트 대응). 자동 감지로 못 찾으면 설정 `schema.ddl`로 지정하며, `schema.*`는 자동 감지를 오버라이드/보강할 때 쓴다.
- **배포 후 상태 = 실 DB 라이브 스키마(현재) + 이번 변경분의 마이그레이션(델타).** 이 최종 상태로 판정한다: 라이브에도 없고 이번 마이그레이션에도 없으면 `missing_index`; 이번 마이그레이션이 추가하면 OK.
- 소스 충돌 시 신뢰 순위: **실 DB > 마이그레이션 최신본 > DDL > 엔티티**. 충돌은 리포트에 남긴다.
- **스키마 커버리지 판정:** 실 DB 조회 -> `LIVE-SCHEMA`(최고 신뢰). DDL 전체/엔티티 명시 인덱스 확보 -> `SCHEMA-CONFIRMED`. 엔티티에 `@Index`가 없어 인덱스 정의를 알 수 없음 등 불완전 -> `SCHEMA-PARTIAL`(신뢰도 낮춤).
- **INVISIBLE 인덱스 제외(MySQL 8.0+):** 인벤토리를 구성할 때 **`INVISIBLE` 인덱스**(`SHOW INDEX`의 `IS_VISIBLE=NO`, DDL/`ALTER`의 `... INVISIBLE` 키워드)는 **커버 가능한 인덱스로 세지 않는다** - 옵티마이저가 사용하지 않으므로 해당 컬럼(조합)은 미인덱스로 취급한다. 이 경우 리포트에 "인덱스는 있으나 INVISIBLE"임을 명시하고 신규 생성 대신 `ALTER TABLE <t> ALTER INDEX <idx> VISIBLE;` 전환을 제안한다(`heuristics.md`의 INVISIBLE 변형).

> 따라서 **`--db`만 제공하면 Tier2(스키마 대조)와 Tier3(EXPLAIN)가 한 번에 충족**된다 - 스키마 파일을 따로 챙길 필요가 없다. 스키마 조회는 EXPLAIN과 동일하게 `scripts/db_guard.py`를 통과한 `SHOW`/`SELECT`만 실행한다.

## 1.5 실 DB 스키마 예외 - 조용히 강등하지 말고 물어볼 것

`--db`로 실 DB 스키마를 조회할 때, 아래는 **조용히 fallback하지 말고 사용자에게 상황을 알리고 대화식으로 확인**한다(잘못된 DB나 마이그레이션 전 상태로 튜닝하면 틀린 결론이 나오므로):

- **대상 테이블이 실 DB에 없음** -> 원인 후보 제시: (a) 아직 마이그레이션 전(이번 변경분이 새로 만드는 테이블) / (b) `--db` 프로파일이 잘못됨 / (c) 테이블/스키마명 불일치. 물음 예: "이번 마이그레이션 델타만으로 판정할까요, 프로파일을 확인/변경할까요?"
- **실 DB 스키마가 코드/마이그레이션과 현저히 불일치**(쿼리가 참조하는 컬럼이 실 DB에 없음, 구조 상이) -> "다른 환경이거나 오래된 DB일 수 있습니다"라고 경고하고 계속 여부/프로파일 변경을 확인.
- **접속 실패/권한 부족/타임아웃** -> 사유를 알리고 Tier2로 강등할지/재시도할지 확인.

> 정상 강등(사용자가 `--db`를 아예 주지 않은 경우)은 조용히 진행하되 리포트에 사용된 깊이를 명시한다. **차이는 "사용자가 심화를 요청했는데 이상으로 막혔는가"** - 그럴 때만 대화식으로 묻는다.

## 2. 쿼리 접근 경로 추출

각 추론 SQL에서:
- **등호 컬럼**: `col = ?`, `col IN (...)`
- **범위 컬럼**: `col > ? / >= / < / BETWEEN`, 접두 `LIKE 'x%'`
- **조인 키**: `ON a.x = b.y`, FK 컬럼
- **정렬 컬럼**: `ORDER BY ...`
- **그룹화**: `GROUP BY ...`

## 3. 매칭 규칙

인덱스가 접근 경로를 커버하는지 판정한다.

- **leftmost prefix:** 인덱스 `(a, b, c)`는 `a`, `(a,b)`, `(a,b,c)` 접근을 커버. `b` 단독/`(b,c)`는 커버 못 함.
- **등호 -> 범위/정렬:** 복합 인덱스는 **등호 컬럼들**을 앞에 두고 그 뒤에 **범위 컬럼 1개**를 둔다. **범위 컬럼 뒤의 컬럼은 정렬/탐색에 쓰이지 못하므로**, 범위 조건 컬럼과 `ORDER BY` 컬럼이 **다르면 한 인덱스로 범위 필터와 정렬을 동시에 커버할 수 없다** - 목적에 따라 `(등호..., 범위)` 또는 `(등호..., 정렬)`을 **택일**한다(`WHERE a=? AND b>? ORDER BY c` -> `(a, b)` 또는 `(a, c)`). 범위 조건과 `ORDER BY`가 **같은 컬럼**이면(`... b>? ORDER BY b`) 그 컬럼까지 한 인덱스로 커버된다.
- **정렬 커버:** `ORDER BY` 컬럼이 인덱스 후미와 방향까지 맞으면 filesort 회피.
- **커버링:** `SELECT` 컬럼까지 인덱스에 포함되면 covering(테이블 접근 없음). 좁은 조회에 유효.
- **다중 단일-컬럼 인덱스 + 복합 부재:** `WHERE a=? AND b=? ORDER BY c`인데 `(a)`/`(b)`/`(c)`가 **각각 단일 인덱스**로만 있고 복합 인덱스가 없으면, 옵티마이저는 대개 **한 인덱스만 골라 부분 사용**하고 나머지 조건/정렬은 필터/filesort로 처리한다(MySQL `index_merge`가 될 수도 있으나 조건/통계 의존이라 보장 못 함). 이 경우 **부분 커버**로 보고 단정하지 말고(`❓`/⚠️), 조건을 함께 커버하는 **복합 인덱스**를 제안한다. `index_merge` 가능성은 근거로만 덧붙인다.
- **UPSERT(`INSERT ... ON DUPLICATE KEY UPDATE`):** 충돌 감지에 쓰이는 **PK/UNIQUE 인덱스**가 있어야 동작한다 - 이 인덱스는 "쓰기 경로의 필수 제약"으로 보고, 없거나 의도한 유니크 키가 부재하면 지적한다(조회 성능용 `missing_index`와 구분해 표기).
- **연관(secondary) 테이블:** M2M `secondary` 연관 테이블(예: SQLAlchemy `relationship(secondary=...)`, Django 자동 중간 테이블)에 **PK/UNIQUE가 없으면** 중복 행이 허용되고 조인 시 풀스캔이 된다. 두 FK의 **복합 PK**(또는 각 방향 조회용 인덱스)를 제안한다 - 조회 성능과 중복 방지 모두.
- **FK `ON DELETE CASCADE`/`SET NULL` 참조측(PostgreSQL):** 부모 행 삭제 시 DB가 자식의 FK 컬럼을 탐색한다. **CASCADE/SET NULL FK 컬럼에 인덱스가 없으면 삭제마다 자식 테이블 풀스캔**이다 - 조회뿐 아니라 삭제 경로 때문에도 `missing_index`로 지적한다. (MySQL/InnoDB는 FK에 인덱스를 자동 생성하므로 해당 없음 - PostgreSQL 특화.)

판정 결과:
- 접근 경로를 **어떤 인덱스도 커버하지 못함** -> `missing_index` 🔴.
- WHERE는 커버되나 **정렬만 미커버** -> `order_by_filesort`(정렬 컬럼 포함 인덱스로 승격 제안).
- FK/조인 키에 인덱스 없음 -> `missing_index`(연관/조인에서 치명적).

## 4. 제안 생성

- `CREATE INDEX idx_<table>_<cols> ON <table>(<col>, ...)` - **컬럼 순서는 3절 규칙**(등호->범위->정렬). 방언 세부는 `dialects/<dialect>.md`.
- **기존 인덱스 확장 우선:** 접두가 겹치는 인덱스가 있으면 신규 대신 컬럼 추가(확장)를 제안(인덱스 수 억제).
- **커버링 옵션:** 자주 쓰는 좁은 조회면 `SELECT` 컬럼 포함 버전을 부가 제안.
- **트레이드오프 명시:** 쓰기 비용, 낮은 카디널리티 컬럼의 효과 한계, 중복 인덱스 경고.
- **마이그레이션 교차:** 같은 변경분에 쿼리가 추가됐는데 인덱스 마이그레이션이 없으면 "이번 배포에 인덱스 함께 포함" 액션으로 승격.

## 5. 과신 방지 (필수)

- `SCHEMA-PARTIAL`이면 단정 대신 **"확인 필요"**로 낮추고, 어느 스키마 소스가 부족한지 명시.
- 매우 작은 테이블/낮은 카디널리티는 인덱스 효과가 제한적임을 함께 안내(무분별한 인덱스 추가 방지).
- 최종 확증은 Tier3 `EXPLAIN`(`--db`)으로: before/after 실행계획을 근거로 첨부.

## 6. 리포트 반영

- 상세 이슈: `missing_index`에 대조 근거(`SCHEMA-CONFIRMED|PARTIAL`) + 제안 DDL + 순서 근거 + 트레이드오프(`report_template.md`의 `tier2_index_block`).
- 실행 계획: 인덱스 추가는 `[자동적용]`으로 완성 DDL 제시(AI가 바로 마이그레이션 생성 가능).

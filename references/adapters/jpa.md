# 어댑터: `jpa` (기본 활성)

JPA/Hibernate가 **생성할 SQL을 추론**한다. 이 스킬의 주요 차별점(ORM->SQL 번역)이며, N+1과 인덱스 누락(`missing_index`)을 커밋 전에 검출하는 주요 경로다. 추출 난이도 **중~상** - 실제 SQL은 Hibernate가 생성하므로 라벨은 대체로 `INFERRED`, 동적은 `AMBIGUOUS`. 항상 "실 SQL 검증(show_sql)"을 함께 안내한다.

## 대상 파일/지점

- **Spring Data 리포지토리 인터페이스**: 파생 쿼리 메서드(`findBy...`), `@Query`(JPQL/native), `@Modifying`, `Pageable`/`Sort` 파라미터, `@EntityGraph`.
- **엔티티 클래스**: `@Entity`/`@Table`(+`@Index`), 연관(`@OneToMany`/`@ManyToOne`/`@ManyToMany`/`@OneToOne`), `FetchType`, `@JoinColumn`(FK), `@BatchSize`.
- **QueryDSL**: `JPAQueryFactory`, `Q`타입, `BooleanBuilder`.
- **Criteria API**: `CriteriaBuilder`/`CriteriaQuery`.
- **EntityManager**: `createQuery`(JPQL) / `createNativeQuery`(-> `native-sql` 규칙) / **`find`/`getReference`(PK 기반 조회 - 1차 캐시 미스 시 `SELECT ... WHERE <pk>=?` 발생)**.

> **repository 계층에 한정하지 말 것:** 쿼리 원천은 리포지토리 밖에도 흩어진다 - **service/filter/config/listener 등 전 계층의 직접 `EntityManager`(`find`/`getReference`/`createQuery`)/`JdbcTemplate` 사용**도 스캔한다. "쿼리는 repository에 있다"는 통념으로 범위를 좁히면 전체 스캔이 불완전해진다.

> diff에 메서드 시그니처만 보여도, **엔티티 매핑(연관/FetchType/`@Table` 인덱스)을 반드시 Read**해야 N+1과 인덱스를 판정할 수 있다.

## 파생 쿼리 메서드 -> SQL 번역

> **대상 한정(중요):** 파생 쿼리 번역은 **Spring Data 마커를 상속한 인터페이스**(`JpaRepository`/`CrudRepository`/`PagingAndSortingRepository`/`Repository<T,ID>`/`KotlinJdslJpqlExecutor` 등)에만 적용한다. **DDD 등에서 흔한 "마커 미상속 순수 인터페이스"는 이름이 `findBy...`/`existsBy...`여도 Spring Data가 프록시를 만들지 않으므로 파생쿼리가 아니다** - 쿼리로 오추출하지 말고 그 인터페이스의 **구현체(다른 모듈일 수 있음)를 찾아 실제 본문(JDSL/JdbcTemplate 등)에서 추출**한다.
>
> **네이밍만으로 자동 번역 금지:** 구현이 있는 메서드는 이름(`existsBy...`/`selectBy...`)만 보고 번역하지 말고 **구현 본문을 확인**한다. 예: `existsBy...`가 실제로는 JDSL `...firstOrNull() != null`이라 **엔티티 전 컬럼 SELECT**일 수 있다(이름 기반 `SELECT 1 ... LIMIT 1` 오판 금지 - LIMIT은 Hibernate 재량).

메서드명을 파싱해 SQL 형태로 번역한다(라벨 `INFERRED`).

| 조각 | SQL |
|---|---|
| `findBy`/`readBy`/`getBy`/`queryBy` | `SELECT ...` |
| `countBy` | `SELECT COUNT(*)` |
| `existsBy` | `SELECT 1 ... LIMIT 1` |
| `deleteBy`/`removeBy` | `DELETE ...` (실행하지 않음, 정적 검토만) |
| `And`/`Or` | `AND` / `OR` (-> `or_predicate_index` 점검) |
| `Is`/`Equals` | `=` |
| `Between` | `BETWEEN ? AND ?` |
| `LessThan`/`Before` / `GreaterThan`/`After` | `< ?` / `> ?` (날짜 `After`/`Before` 포함) |
| `LessThanEqual`/`GreaterThanEqual` | `<= ?` / `>= ?` |
| `Like`/`Containing`/`StartingWith`/`EndingWith` | `LIKE` - `Containing`/`EndingWith`는 **선행 `%`** -> `leading_wildcard_like` |
| `In`/`NotIn` | `IN (...)` -> 크기 무제한이면 `large_in_clause` |
| `IgnoreCase` | `UPPER(col)=UPPER(?)` -> `non_sargable_predicate` |
| `OrderBy...Asc/Desc` | `ORDER BY ...` -> Tier2에서 `order_by_filesort`/`missing_index` 점검 |
| `Top`/`First`(N) | `LIMIT N` |

연관 FK: `findByUserId`처럼 연관 엔티티의 식별자를 참조하면 **FK 컬럼**으로 번역 -> `WHERE user_id = ?` (-> Tier2에서 FK 인덱스 확인).

예: `findByStatusAndCreatedAtAfterOrderByCreatedAtDesc`
-> `SELECT ... FROM <t> WHERE status = ? AND created_at > ? ORDER BY created_at DESC`
-> Tier2: `(status, created_at)` 인덱스 없으면 `missing_index`(*).

## Spring Data 기본 CRUD (`save`/`saveAll`/`findById`/`deleteById` ...)

`JpaRepository`/`CrudRepository`가 **상속으로 제공**하는 기본 메서드도 SQL을 생성한다. 파생 메서드 표에 없으므로 여기서 처리한다(라벨 `INFERRED` - 실 SQL은 Hibernate 생성). 이 스택에서 **INSERT/UPDATE의 사실상 전부가 `save*` 경유**다.

| 메서드 | SQL | 비고 |
|---|---|---|
| `save`/`saveAndFlush` | 신규면 `INSERT`, 아니면 `UPDATE ... WHERE <pk>=?` | INSERT/UPDATE는 **`isNew()` 판정**에 달림(아래) |
| `saveAll`/`saveAllAndFlush` | 위를 원소마다 | 배치 여부는 `hibernate.jdbc.batch_size` |
| `findById`/`getReferenceById` | `SELECT ... WHERE <pk>=?` | `getReferenceById`는 프록시(접근 시 조회) |
| `existsById` | `SELECT ... WHERE <pk>=?` | |
| `deleteById`/`delete` | 선행 `SELECT`(로딩) + `DELETE ... WHERE <pk>=?` | `delete`는 대상 로딩 후 삭제 |
| `count`/`findAll` | `SELECT COUNT(*)` / 전건 `SELECT` | `findAll()`은 `unbounded_result` 주의 |

- **INSERT vs UPDATE 판정(`isNew()`):** 식별자가 **assigned(직접 부여)** 이거나 `@Version`/`Persistable.isNew()`가 있으면 판정이 달라진다. **`@EmbeddedId`/`@MapsId` 등 assigned-key 엔티티의 `save()`는 `isNew()=false`로 보고 `merge`로 동작** -> **INSERT/UPDATE 앞에 식별자 확인 `SELECT`가 1회 선행**한다(이 선행 SELECT의 PK 인덱스 접근도 인벤토리/튜닝 대상). 순수 INSERT로 오근사하지 말 것.
- **`@DynamicInsert`/`@DynamicUpdate`:** 실제 `INSERT`/`UPDATE`의 컬럼 목록이 **런타임 가변**이다. 컬럼을 확정하지 말고 라벨을 `INFERRED`로 두고 "동적 컬럼(대표: 변경된 필드)"임을 명시한다. WHERE/식별자는 PK.
- **인벤토리 나열 방침:** 상속 제공 기본 메서드는 **코드에서 명시적으로 선언/호출된 지점만** 싣는다(전 메서드 기계적 나열은 노이즈). 호출부가 확인되면 그 지점을 원천으로 표기한다.

## `@Query`

- **JPQL**: 엔티티/필드를 테이블/컬럼으로 매핑해 SQL로 근사. 연관 경로(`o.user.name`) -> 조인.
- **`nativeQuery = true`**: `native-sql` 어댑터 규칙 적용(SQL 방언(dialect) 이질 문법 `dialect_pipe_concat` 포함).
- **`@Modifying`**: 쓰기 쿼리 - 실행하지 않고 정적/스키마 분석만.

## N+1 판정

- 기본 `FetchType`: **`@ManyToOne`/`@OneToOne` = EAGER, `@OneToMany`/`@ManyToMany` = LAZY**.
- **LAZY 연관을 컬렉션 순회에서 접근 + fetch 미지정** -> `n_plus_one` 🔴.
- **해소 확인**: `@EntityGraph(attributePaths=[...])`, JPQL `join fetch`, QueryDSL `fetchJoin()` -> 조인 1회로 해결.
- **EAGER 남발**: `@ManyToOne(fetch=EAGER)` 다수 -> 목록 조회 시 항상 조인/추가 쿼리(과다 로딩). 지적 대상.
- **완화**: `@BatchSize(size=n)` / `hibernate.default_batch_fetch_size` -> IN 배치로 N+1 완화(있으면 근거에 반영).
- 페이징 + `join fetch` 컬렉션 조합은 메모리 페이징(`HHH000104`) 경고.
- **수동 ON 조인은 N+1 프레임 밖:** `@Transient`/비-JPA 연관을 명시적 `ON` 조건으로 조인하는 경우(엔티티 매핑 연관이 아님)는 "LAZY 연관 순회" N+1 프레임을 적용하지 않는다 - 조인 1회로 해결된 형태다. 매핑 연관과 혼동하지 말 것.

## Tier2 인덱스 대조 연계

파생 메서드/`@Query`/QueryDSL에서 뽑은 **WHERE/JOIN/ORDER BY 컬럼**을 스키마와 대조한다. 엔티티의 `@Table(indexes=@Index(columnList="..."))`, `@Id`, `@JoinColumn`(FK)도 인덱스 인벤토리에 포함한다. 규칙/판정은 `references/tier2-index-matching.md`. **FK(`@JoinColumn`)에 인덱스가 없으면 `missing_index`** - 연관 조회/조인에서 특히 치명적(이 도구의 주된 동기).

- **엔티티에 인덱스 선언이 없을 수 있다:** 많은 프로젝트가 `@Table(indexes=...)`를 쓰지 않고 인덱스를 **DDL/마이그레이션에만** 둔다. 엔티티만으로는 `SCHEMA-PARTIAL`이 되므로, **엔티티에 인덱스 선언이 없으면 DDL/마이그레이션 또는 `--db` 실 DB 조회를 반드시 병행**한다.
- **소스 충돌 주의:** 엔티티의 `@Table(uniqueConstraints=...)`/`@Index` 선언과 실제 DB(DDL/실DB)가 **어긋날 수 있다**(마이그레이션 누락 등). 충돌 시 신뢰 순위는 **실DB > 마이그레이션 > DDL > 엔티티**(`tier2-index-matching.md` 1절). 엔티티 선언만 믿고 "커버됨"으로 단정하지 말고, 불일치 자체를 "확인 필요" 신호로 리포트에 남긴다.
- **INVISIBLE 인덱스:** 인덱스가 존재해도 `INVISIBLE`이면 옵티마이저가 쓰지 않으므로 **미인덱스로 취급**한다(판정/제안은 `tier2-index-matching.md`의 INVISIBLE 규칙). 코드 주석이 "이 인덱스를 쓴다"고 단언해도 실제 `IS_VISIBLE=NO`면 그 가정이 틀렸음을 지적한다.

## QueryDSL / Criteria (동적)

- 빌더 체인(`where(...)`, `BooleanBuilder`)의 조건을 수집. 동적이면 **대표 시나리오 2~3개**로 전개(`AMBIGUOUS`).
- `fetchJoin()`/`leftJoin(...).fetchJoin()`으로 N+1 해소 여부 확인.

## Kotlin JDSL (`com.linecorp.kotlinjdsl`)

타입 안전 DSL로 JPQL/쿼리를 조립한다(최신 Kotlin 스택에서 흔함). 빌더 표현을 SQL 접근 경로로 번역한다(대체로 `INFERRED`, 동적 분기는 `AMBIGUOUS`).

| JDSL 표현 | SQL 절 |
|---|---|
| `select(entity(Foo::class))` / `selectNew<Dto>(...)` | `SELECT`(프로젝션/DTO) |
| `from(entity(Foo::class))` | `FROM foo` |
| `where(path(Foo::status).eq(s))` | `WHERE status = ?` |
| `.eq/.ne/.lt/.le/.gt/.ge` | `= / <> / < / <= / > / >=` |
| `` .`in`(values) `` (Kotlin 예약어라 백틱) | `IN (...)` -> 크기 무제한이면 `large_in_clause` |
| `.like("%x%")` | `LIKE` -> 선행 `%`면 `leading_wildcard_like` |
| `.isNull()/.isNotNull()` | `IS [NOT] NULL` |
| `and()/or()` | `AND`/`OR` (-> `or_predicate_index`) |
| `leftJoin(Foo::bar).on(...)` / `associate(...)` | `LEFT JOIN ... ON ...` - fetch 여부로 N+1 판정 |
| `orderBy(path(...).asc()/desc())` | `ORDER BY ...` -> Tier2 `order_by_filesort`/`missing_index` |
| `offset(n).limit(m)` | 페이징 -> 큰 offset이면 `deep_pagination` |
| `deleteFrom(entity(Foo::class)).where(...)` | `DELETE FROM foo WHERE ...` - 실행하지 않고 정적 검토만 |
| `update(entity(Foo::class)).set(...).where(...)` | `UPDATE foo SET ... WHERE ...` - 정적 검토만 |

- **N+1:** JDSL 조인이 **fetch join인지**(연관 즉시 로딩) 단순 조인/미조인인지 구분. LAZY 연관을 결과 순회에서 접근하면 `n_plus_one`(QueryDSL과 동일 원리).
- **동적 쿼리:** 코틀린 `if`/`let`으로 조건을 조립하는 부분은 **대표 시나리오 2~3개**로 전개(`AMBIGUOUS`).
- WHERE/JOIN/ORDER BY 컬럼은 `path(Entity::field)`에서 추출해 Tier2 인덱스 대조에 전달한다.
- **연관 경로 -> FK 직접 vs JOIN:** `path(Child::parent).path(Parent::id)`처럼 **연관의 식별자(@Id)** 만 타면 자식 테이블의 **FK 컬럼 직접 접근**(예: `parent_id`)으로 최적화돼 조인이 없을 수 있다. 반면 **연관의 비-식별자 속성**(`path(Child::parent).path(Parent::name)`)을 타면 상위 테이블 **JOIN**이 생긴다. 접근 컬럼/인덱스 대조 시 이를 구분하고, 확정이 어려우면 `AMBIGUOUS`로 두고 조인 그래프를 함께 적는다.

## 신뢰도 라벨

- `@Query` 정적 JPQL/native: `INFERRED`(JPQL 번역) 또는 `EXACT`(native 그대로).
- 파생 메서드: `INFERRED` - 번역 규칙은 확실하나 실제 SQL은 Hibernate가 생성.
- QueryDSL/Criteria 동적: `AMBIGUOUS`.
- 모든 항목에 **"Hibernate `show_sql`/`org.hibernate.SQL` 로그로 실제 SQL 확인"** 안내.

## 산출물 형식

각 지점마다: **원천**(`파일:라인`, 메서드/엔티티) / **추론 SQL**(+라벨) / **fetch/조인 메타**(FetchType, EntityGraph, join fetch) / **N+1 판정** / Tier1/Tier2 결과 / 검증 안내.

## 예시

```kotlin
// 리포지토리
interface OrderRepository : JpaRepository<Order, Long> {
  fun findByStatusAndCreatedAtAfterOrderByCreatedAtDesc(status: String, from: Instant): List<Order>
}
// 엔티티
@Entity @Table(name = "orders")               // <- @Table(indexes=...) 없음 -> 인덱스 미정의
class Order(
  @Id @GeneratedValue val id: Long,
  @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "user_id") val user: User,  // FK 인덱스?
  val status: String, val createdAt: Instant,
)
```
-> 추론 SQL: `SELECT ... FROM orders WHERE status=? AND created_at>? ORDER BY created_at DESC` (INFERRED)
-> Tier2: `orders(status, created_at)` 인덱스 없음 -> `missing_index` 🔴 + `CREATE INDEX` 제안.
-> 연관 `user`가 LAZY인데 목록 순회에서 접근하면 `n_plus_one`, `user_id` FK 인덱스 없으면 자식도 풀스캔.

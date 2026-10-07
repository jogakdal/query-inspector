# 어댑터: `python-sqlalchemy` (확장)

SQLAlchemy(ORM + Core)가 **생성할 SQL을 추론**한다. `session.query`/`select` 체인과 relationship 로딩을 SQL로 번역해 N+1(lazy relationship)과 인덱스 누락(`missing_index`)을 검출한다. 라벨은 대체로 `INFERRED`, 동적 조건은 `AMBIGUOUS`. 항상 "실 SQL 검증(`echo=True` / `logging`의 `sqlalchemy.engine`)"을 함께 안내한다.

> **Django와의 결정적 차이(오탐/미탐 갈림):** **SQLAlchemy는 `ForeignKey`에 인덱스를 자동 생성하지 않는다**(DB가 FK 제약에 자동 인덱스를 만드는 경우는 별개 - MySQL/InnoDB는 만들고 PostgreSQL은 안 만든다). 따라서 Django 어댑터와 반대로, **FK 컬럼에 명시 인덱스(`index=True`/`Index(...)`)가 없으면 `missing_index` 후보**로 본다(특히 PostgreSQL). Django 규칙("FK는 기본 인덱스라 단정 금지")을 여기 그대로 적용하지 말 것.

## 대상 파일/지점

- **declarative 모델**: `Base` 상속 클래스, `Column(type, index=, unique=, primary_key=, nullable=)`, `relationship(lazy=, back_populates, uselist)`, `ForeignKey`, `__table_args__`(`Index(...)`, `UniqueConstraint(...)`). Mapped/`mapped_column`(2.0 타입 애노테이션 스타일) 포함.
- **쿼리 지점(ORM)**: `session.query(Model)` 체인(`filter`/`filter_by`/`order_by`/`limit`/`offset`/`join`/`outerjoin`/`group_by`/`having`/`distinct`/`count`/`first`/`one`/`scalar`), `options(joinedload/selectinload/subqueryload/contains_eager)`.
- **쿼리 지점(2.0 스타일)**: `select(Model).where(...).order_by(...)`, `session.scalars(...)`/`session.execute(...)`.
- **Core**: `select(table).where(table.c.x == ...)`, `table.c` 접근, `text("SQL")`.
- **마이그레이션(Alembic)**: `**/versions/*.py`의 `op.create_index`/`create_table`/`add_column`/`create_foreign_key` - 인덱스 델타 소스(Tier2).
- **전 계층 스캔**: repository/service/DAO/태스크에 흩어진다. repository 계층에 국한하지 말 것.

> **커스텀 쿼리 메서드(중요):** repository/매니저의 커스텀 메서드는 이름만으로 판단하지 말고 **정의 본문을 Read**해 실제 필터/`options(...)` 로딩 전략을 확인한다(페치 최적화가 있으면 N+1 해소로 봄, 오탐 금지).

## query/select -> SQL 번역

| 체인/식 | SQL |
|---|---|
| `.filter(Model.a == 1)` / `.filter_by(a=1)` | `WHERE a = ?` |
| `Model.a > / >= / < / <=` | `> ?` / `>= ?` / `< ?` / `<= ?` |
| `.in_([...])` | `IN (...)` -> 크기 무제한이면 `large_in_clause` |
| `.between(a, b)` | `BETWEEN ? AND ?` |
| `.is_(None)` | `IS NULL` |
| `.like("x%")` | `LIKE 'x%'` |
| `.like("%x%")`/`.like("%x")` | **선행 `%`** -> `leading_wildcard_like` |
| `.ilike(...)` | 대소문자 무시 `LIKE` -> `non_sargable_predicate`(함수/`LOWER` 취급) |
| `.join(Model.rel)` / `관계 경로` | `JOIN` |
| `.order_by(Model.f.desc())` | `ORDER BY f DESC` -> Tier2 `order_by_filesort`/`missing_index` |
| `.limit(n)` / `.offset(m)` | `LIMIT n` / `OFFSET m` -> 큰 offset이면 `deep_pagination` |
| `.group_by(...)`/`.having(...)` | `GROUP BY`/`HAVING` |
| `.distinct()` | `DISTINCT` -> 불필요하면 `distinct_abuse` |
| `.count()` | `SELECT COUNT(*)`(서브쿼리로 감싸질 수 있음) |
| `.first()`/`.one()`/`.one_or_none()` | 단건(`one`은 0/2+건 예외) |
| `text("SQL")` | 원본 SQL 그대로(라벨 `EXACT`) -> `native-sql` 규칙 |

- 예: `session.query(Order).filter(Order.status == "paid").order_by(Order.created_at.desc())`
  -> `SELECT ... FROM orders WHERE status = ? ORDER BY created_at DESC`
  -> Tier2: `(status, created_at)` 인덱스 없으면 `missing_index`(*).

## N+1 판정

- **relationship 기본 `lazy="select"`**: 관계 속성 접근 시 그때 지연 `SELECT`. **반복문에서 접근 + eager 로딩 미지정** -> `n_plus_one` 🔴.
- **해소 확인**: `.options(joinedload(Model.rel))`(JOIN 1회), `.options(selectinload(Model.rel))`(`IN` 배치 1회), `subqueryload`, `contains_eager`(이미 조인된 것 매핑), 또는 relationship 정의의 `lazy="joined"`/`lazy="selectin"`. 있으면 해소로 판정.
- **relationship `lazy` 종류(정의에서 확인):** `select`(기본, 지연 -> N+1 위험) / `joined`/`selectin`/`subquery`(즉시 로딩 -> 해소) / `dynamic`(관계가 `Query` 객체를 반환 - 컬렉션을 로딩하지 않고 명시 쿼리를 요구하므로 반복 접근 시 매번 쿼리이고 `selectinload`로 일괄 로딩되지 않는다) / `raise`(접근 시 예외로 N+1을 코드로 차단 - 문제 없음) / `noload`(로딩 안 함).
- **컬렉션 relationship**(`uselist=True`)을 반복에서 접근 + eager 미지정 -> `n_plus_one`.
- `.all()` 후 파이썬 필터 -> 과다 로딩(쿼리에서 `filter` 권장).

## Tier2 인덱스 대조 연계

WHERE/JOIN/ORDER BY 컬럼을 스키마와 대조한다. 규칙/판정은 `references/tier2-index-matching.md`.

- **인덱스 소스(모델)**: `Column(index=True)`, `Column(unique=True)`, `__table_args__`의 `Index("ix", "a", "b")`/`UniqueConstraint(...)`, `primary_key=True`.
- **FK 인덱스(중요):** 위 상단 노트대로 - SQLAlchemy는 FK에 인덱스를 자동 생성하지 않으므로, FK 컬럼에 `index=True`/`Index`가 없으면 **`missing_index` 후보**(PostgreSQL에서 특히 유효; MySQL/InnoDB는 DB가 자동 생성하니 방언을 함께 고려). 확정이 어려우면 `--db` 실 DB 조회 권장.
- **마이그레이션 델타(Alembic)**: 같은 변경분의 `versions/*.py`에 `op.create_index`가 있으면 "이번 배포로 생기는 인덱스", 없으면 "이번 변경이 요구하는 인덱스가 빠졌는지" 판정.
- **신뢰 순위**: 실DB(`--db`) > Alembic 마이그레이션 > 모델 선언.

## 동적 쿼리 전개

- `if`로 `filter`를 조건부로 이어 붙이는 체인, `and_()`/`or_()` 조합은 **대표 시나리오 2~3개**로 전개(`AMBIGUOUS`). 전수 X.

## 원시 SQL 안티패턴 (`text()` / Core)

`text("...")`와 Core의 원시 SQL은 `native-sql` 규칙을 그대로 적용한다(`references/adapters/native-sql.md`).

- **문자열 보간 인젝션(`string_substitution` 🔴 critical):** `text(f"... WHERE x = {val}")`, `text("... WHERE x = " + val)`, `session.execute(text(f"..."))`처럼 **바인드가 아닌 f-string/`%`-format/`+` 결합**으로 값이 들어가면 `string_substitution`(SQL 인젝션 + 플랜 캐시 오염). `text("... WHERE x = :x").bindparams(x=val)`(또는 `:name`) 바인드로 치환한다.
- **방언 이질(`dialect_pipe_concat`):** 원시 SQL에 `||`/`NVL`/`SYSDATE`/`ROWNUM`/`FROM DUAL` 등 **감지 방언과 다른 문법**이 있으면 표기. 단 `||`는 PostgreSQL/Oracle에선 표준 문자열 결합, MySQL에선 논리 OR이므로 **감지 방언 기준으로만** 판정한다(PostgreSQL 프로젝트의 `||`는 정상).
- **`SELECT *`(`select_star`):** `text("SELECT * FROM ...")`은 `select_star`. ORM이 생성하는 전체 컬럼 SELECT(명시 컬럼)는 해당 없음.

## 신뢰도 라벨

- `text("...")` 정적 문자열: `EXACT`.
- `query`/`select` 번역: `INFERRED`.
- 조건부 체인/`and_`/`or_` 동적 조합: `AMBIGUOUS`.
- 모든 항목에 **"`create_engine(..., echo=True)` 또는 `logging`의 `sqlalchemy.engine`으로 실제 SQL 확인"** 안내.

## 산출물 형식

각 지점마다: **원천**(`파일:라인`) / **추론 SQL**(+라벨) / **로딩 전략**(`joinedload`/`selectinload` 유무) / **N+1 판정** / Tier1/Tier2 결과 / 검증 안내.

## 예시

```python
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))    # index= 없음 -> FK 인덱스 미생성(SQLAlchemy)
    status = Column(String(20))
    created_at = Column(DateTime)
    user = relationship("User")                          # lazy="select"(기본)
    # __table_args__ 없음 -> (status, created_at) 인덱스 없음

# 쿼리
orders = session.query(Order).filter(Order.status == "paid").order_by(Order.created_at.desc())
for o in orders:
    print(o.user.name)                                   # N+1: joinedload 누락
```
-> 추론 SQL: `SELECT ... FROM orders WHERE status = ? ORDER BY created_at DESC` (INFERRED)
-> Tier2: `orders(status, created_at)` 인덱스 없음 -> `missing_index` 🔴; **`user_id`도 인덱스 없음 -> `missing_index`**(SQLAlchemy는 FK 자동 인덱스 없음; PostgreSQL 기준).
-> N+1: 루프에서 `o.user` 접근인데 eager 미지정 -> `n_plus_one` 🔴 (해소: `.options(joinedload(Order.user))`).

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
| `rel.any(cond)` / `rel.has(cond)` | 컬렉션/스칼라 관계의 `EXISTS (...)` - 바깥 FROM에 소유 엔티티가 없으면 **비상관**이 되어 필터 무력화(아래 "조인 없이 타 엔티티 참조") |
| `Model.query`(Flask-SQLAlchemy 레거시) | `session.query(Model)`과 동치 - `.filter`/`.order_by`/... 체인 동일 번역 |
| `db.paginate(select)` / `.paginate()` | `LIMIT ? OFFSET ?` + 총계용 별도 `COUNT(*)` 서브쿼리 -> 대형이면 `count_large`/`deep_pagination` |

- 예: `session.query(Order).filter(Order.status == "paid").order_by(Order.created_at.desc())`
  -> `SELECT ... FROM orders WHERE status = ? ORDER BY created_at DESC`
  -> Tier2: `(status, created_at)` 인덱스 없으면 `missing_index`(*).

## 조인 없이 타 엔티티 참조 (카티전 곱 / 비상관 EXISTS)

SQLAlchemy는 JOIN을 명시하지 않고 `where`/`filter`에 다른 엔티티를 참조하면 **그 엔티티를 FROM에 암묵 추가**한다. 정적 추론만으로는 아래 두 패턴을 혼동하기 쉬우므로(카티전 곱으로 보이던 것이 실제로는 비상관 EXISTS), **컴파일된 SQL로 FROM 절과 EXISTS 상관 여부를 반드시 확인**한다.

- **암묵 FROM 카티전 곱(`cartesian_join` 🔴):** `select(A).where(B.x == 1)`처럼 조인 조건 없이 `B` 컬럼을 `where`에 쓰면 `FROM a, b`가 되어 카티전 곱이 된다. SQLAlchemy 2.0은 이때 **컴파일 린터가 "cartesian product" 경고**를 낸다(검증 수단). 해소: `.join(B, A.b_id == B.id)` 또는 relationship 경로 조인을 명시한다.
- **relationship `.any()`/`.has()`의 비상관 EXISTS(`query_correctness`/보안이면 `scope_filter_bypass` 🔴):** `select(Topic).where(Forum.groups.any(Group.id.in_(ids)))`처럼 **바깥 FROM에 소유 엔티티(`Forum`)가 없으면**, `.any()`가 비상관(uncorrelated) `EXISTS`로 렌더되어 "그런 `Forum`이 하나라도 있으면 전건 통과"가 된다 - 필터가 **무력화**된다(권한 필터면 보안 결함). 상관시키려면 바깥에 대상 엔티티를 조인하고(`select(Topic).join(Forum).where(Forum.groups.any(...))`) 올바른 상관 경로를 준다. `.has()`(스칼라 관계)도 동일하다.

> 검증: `str(stmt.compile(dialect=postgresql.dialect()))`의 FROM 절에 조인 없는 두 번째 테이블이 있는지, `EXISTS`가 바깥 행을 참조(상관)하는지 본다. 2.0의 cartesian-product 경고를 함께 확인한다.

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
- **연관 테이블(`secondary`):** `relationship(secondary=assoc)`의 `sa.Table(...)` 정의를 본다. M2M 연관 테이블에 **PK/UNIQUE도 인덱스도 없으면** 조인 시 풀스캔 + 중복 행 위험(`missing_index`/`cartesian_join` 교차). 보통 두 FK의 복합 PK 또는 각 FK 인덱스가 필요하다. 세부: `tier2-index-matching.md`.
- **마이그레이션 델타(Alembic)**: 같은 변경분의 `versions/*.py`에 `op.create_index`가 있으면 "이번 배포로 생기는 인덱스", 없으면 "이번 변경이 요구하는 인덱스가 빠졌는지" 판정.
- **신뢰 순위**: 실DB(`--db`) > Alembic 마이그레이션 > 모델 선언.

## 동적 쿼리 전개

- `if`로 `filter`를 조건부로 이어 붙이는 체인, `and_()`/`or_()` 조합은 **대표 시나리오 2~3개**로 전개(`AMBIGUOUS`). 전수 X.

## Flask-SQLAlchemy 고유 구문

- **`Model.query`(레거시):** `db.session.query(Model)`과 동치. 2.0 스타일 `select()`를 권장하나 번역/판정은 동일하다.
- **`db.paginate(...)`/`Query.paginate(...)`:** 페이지 조회 = `LIMIT`/`OFFSET` + **총 개수 `COUNT(*)` 서브쿼리**. 매 요청 대형 테이블이면 `count_large`, 페이지 번호가 커지면 `deep_pagination`(키셋 페이징 권장). `error_out`/`max_per_page`도 확인.
- **`WriteOnlyMapped`/`DynamicMapped`(2.0, `lazy="write_only"`/`"dynamic"`):** 컬렉션을 로딩하지 않고 `Select`/`Query`를 반환한다. 대량 컬렉션엔 적절하나 **`selectinload`로 일괄 로딩되지 않으므로**, 루프에서 건건 평가하면 N+1이다.
- **커스텀 `Pagination`:** 프로젝트 정의 페이지네이션(예: `SelectAllPagination`)은 본문을 Read해 COUNT/전량 로딩 여부를 확인한다(전량 로딩이면 `unbounded_result`).

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
- **컴파일 확인(DB 없이, 권장):** `str(stmt.compile(dialect=postgresql.dialect()))`로 FROM 절/EXISTS 상관/카티전 곱을 확인하고, 그 경우 "검증 수준: 컴파일 확인"으로 라벨과 별개 표기한다. **시스템 `python3`가 프로젝트 파이썬 버전과 다르면**(예: 3.9에서 3.12의 PEP 695/`datetime.UTC` import 실패) 모델 import가 안 되므로, **프로젝트 venv(`.venv`/`uv`/`poetry env`)의 파이썬**으로 컴파일한다. venv를 못 찾으면 최소 모델 복제본 + 동일 메이저 SQLAlchemy로 컴파일하되 버전 차이를 리포트에 남긴다.

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

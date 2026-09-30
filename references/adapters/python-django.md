# 어댑터: `python-django` (확장)

Django ORM이 **생성할 SQL을 추론**한다. QuerySet 체인과 관계 접근을 SQL로 번역해, N+1(`select_related`/`prefetch_related` 누락)과 인덱스 누락(`missing_index`)을 커밋 전에 검출한다. 실제 SQL은 Django가 생성하므로 라벨은 대체로 `INFERRED`, 조건부 체인은 `AMBIGUOUS`. 항상 "실 SQL 검증(`qs.query` / `connection.queries` / django-debug-toolbar)"을 함께 안내한다.

## 대상 파일/지점

- **모델(`models.py` 등)**: `models.Model`, 필드(`db_index=`, `unique=`, `null=`), `class Meta`(`indexes`, `constraints`, `unique_together`, `ordering`), 관계(`ForeignKey`/`OneToOneField`/`ManyToManyField`, `related_name`, `on_delete`, `db_index`).
- **쿼리 지점**: `Model.objects` 또는 커스텀 `Manager`/`QuerySet`의 체인 - `filter`/`exclude`/`get`/`all`/`order_by`/`values`/`values_list`/`only`/`defer`/`annotate`/`aggregate`/`distinct`/`count`/`exists`/`first`/`last`/슬라이싱 `[:n]`, `select_related`/`prefetch_related`/`Prefetch`, `.raw(...)`, `.extra(...)`, `F()`/`Q()`/`Subquery`/`OuterRef`.
- **마이그레이션(`**/migrations/*.py`)**: `migrations.AddIndex`/`RemoveIndex`/`AddConstraint`/`AlterField`, `models.Index(fields=[...])` - 인덱스 델타 소스(Tier2).
- **전 계층 스캔**: 쿼리는 뷰(`views.py`)/서비스/시그널/DRF 시리얼라이저/관리 명령/태스크(Celery)에 흩어진다. **"쿼리는 한 곳에 있다"는 통념으로 범위를 좁히지 말 것.** 특히 **DRF 시리얼라이저/템플릿의 관계 접근**은 뷰 코드에 안 보여도 N+1 원천이다.

> diff에 QuerySet 한 줄만 보여도, **모델 매핑(관계/`db_index`/`Meta.indexes`)을 반드시 Read**해야 N+1과 인덱스를 판정할 수 있다.

> **커스텀 매니저/QuerySet 메서드(중요):** `objects.approved()`/`browsable()`처럼 프로젝트가 정의한 매니저/QuerySet 메서드는 이름만으로 판단하지 말고 **정의 본문(`managers.py` 등)을 Read**해 실제 필터/`select_related`/`prefetch_related`를 확인한다. 본문에 페치 최적화가 있으면 N+1 해소로 본다(오탐 금지).

## QuerySet -> SQL 번역

메서드 체인과 필드 룩업을 SQL로 번역한다(라벨 `INFERRED`).

| 체인/룩업 | SQL |
|---|---|
| `.filter(a=1, b=2)` | `WHERE a = ? AND b = ?` |
| `.exclude(...)` | `WHERE NOT (...)` |
| `.get(...)` | `WHERE ...`(단건; 0/2+건 예외) |
| `__gt`/`__gte`/`__lt`/`__lte` | `> ?` / `>= ?` / `< ?` / `<= ?` |
| `__in=[...]` | `IN (...)` -> 크기 무제한이면 `large_in_clause` |
| `__range=(a,b)` | `BETWEEN ? AND ?` |
| `__isnull=True` | `IS NULL` |
| `__startswith` | `LIKE 'x%'` |
| `__contains`/`__endswith` | `LIKE '%x'`/`'%x%'` -> **선행 `%`** -> `leading_wildcard_like` |
| `__icontains`/`__iexact` | `UPPER(col) LIKE UPPER(?)` -> `non_sargable_predicate` |
| `관계__field`(예: `user__name`) | 상위 테이블 **JOIN** 후 `WHERE user.name = ?` |
| `fk_id=` / `fk=obj` | **FK 컬럼 직접** `WHERE user_id = ?`(조인 없음) |
| `.order_by('f', '-f')` | `ORDER BY f ASC/DESC` -> Tier2 `order_by_filesort`/`missing_index` |
| `.values('a')`/`.values_list()`/`.only()`/`.defer()` | 프로젝션(SELECT 컬럼 한정) |
| `.annotate(...)`/`.aggregate(...)` | 집계/`GROUP BY` |
| `.distinct()` | `DISTINCT` -> 불필요하면 `redundant_distinct` |
| `.count()` | `SELECT COUNT(*)` |
| `.exists()` | `SELECT 1 ... LIMIT 1` |
| `.first()`/`.last()`/`[:n]` | `ORDER BY ... LIMIT n` |
| `.raw("SQL")` | 원본 SQL 그대로 -> `native-sql` 규칙 적용(라벨 `EXACT`) |
| `.extra(...)` | 부분 raw 삽입 - SQL 인젝션/방언 이질 주의 |

- **관계 룩업 vs FK 직접(중요):** `filter(user__name=...)`는 상위 테이블 **JOIN**을 만들고, `filter(user_id=...)`/`filter(user=obj)`는 자식의 **FK 컬럼 직접 접근**(조인 없음)이다. 접근 컬럼/인덱스 대조 시 이를 구분한다.
- 예: `Order.objects.filter(status='paid').order_by('-created_at')`
  -> `SELECT ... FROM orders WHERE status = ? ORDER BY created_at DESC`
  -> Tier2: `(status, created_at)` 인덱스 없으면 `missing_index`(*).

## 쓰기/일괄 연산

| 메서드 | SQL | 비고 |
|---|---|---|
| `.save()` | 신규면 `INSERT`, 아니면 `UPDATE ... WHERE pk=?` | PK 유무로 분기(강제는 `force_insert`/`force_update`) |
| `.create()` | `INSERT` | |
| `.bulk_create()`/`.bulk_update()` | 배치 `INSERT`/`UPDATE` | `batch_size` 확인 |
| `.update(...)`(QuerySet) | `UPDATE ... WHERE <필터>` | 실행하지 않고 정적/스키마 분석만 |
| `.delete()` | `DELETE`(+ 관계 `on_delete` 연쇄) | `CASCADE`는 연쇄 삭제/추가 쿼리 유발 |
| `get_or_create`/`update_or_create` | `SELECT` 후 조건부 `INSERT`/`UPDATE` | 선행 SELECT의 인덱스 접근도 대상 |

## N+1 판정 (Django 특유, 최우선)

- **FK/OneToOne 접근**: `obj.user`처럼 관계 속성에 접근하면 그때 지연 `SELECT`가 나간다. **반복문/시리얼라이저에서 접근 + `select_related` 누락** -> `n_plus_one` 🔴.
- **역참조/M2M**: `obj.orders.all()`, `obj.tags.all()`을 반복에서 접근 + `prefetch_related` 누락 -> `n_plus_one`.
- **해소 확인**: `.select_related('user')`(JOIN 1회), `.prefetch_related('orders')`(별도 `IN` 쿼리 1회), `Prefetch(...)`(커스텀). 있으면 해소로 판정.
- **`.all()` 후 파이썬 필터**: `[o for o in qs.all() if o.status=='x']`처럼 DB에서 거르지 않고 전건 로딩 후 파이썬에서 필터 -> 과다 로딩(`.filter()` 권장).
- **`len(qs)` vs `.count()`**: 개수만 필요한데 `len(queryset)`을 쓰면 전건 로딩. `.count()`로.
- **DRF/템플릿**: 시리얼라이저 필드나 템플릿의 `{{ obj.user.name }}`이 뷰에 안 보여도 N+1을 만든다. 뷰의 `get_queryset`에 `select_related`/`prefetch_related`가 있는지 함께 본다.

## Tier2 인덱스 대조 연계

WHERE/JOIN/ORDER BY 컬럼을 스키마와 대조한다. 규칙/판정은 `references/tier2-index-matching.md`.

- **인덱스 소스(모델)**: 필드 `db_index=True`, `unique=True`, `class Meta`의 `indexes=[models.Index(fields=[...])]`/`constraints`/`unique_together`.
- **`Meta.ordering`(암묵 정렬):** 모델 `class Meta`에 `ordering`이 있으면 명시적 `.order_by()`가 없어도 모든 조회에 암묵 `ORDER BY`가 붙는다 - 그 정렬 컬럼도 `order_by_filesort`/인덱스 대조 대상이다.
- **FK 자동 인덱스(중요, 오탐 방지):** Django는 `ForeignKey`/`OneToOneField`에 **기본으로 인덱스를 생성**한다(`db_index=True`가 기본). 따라서 JVM처럼 "FK에 인덱스 없음"을 단정하지 말 것 - **`db_index=False`로 명시했거나, 복합 인덱스의 선행 컬럼이 아닌 경우**에만 `missing_index`로 본다. (단 일부 DB/구성에서 자동 인덱스가 없을 수 있으니 확정이 어려우면 `--db` 실 DB 조회 권장.)
- **마이그레이션 델타**: 같은 변경분의 `migrations/*.py`에 `AddIndex`가 있으면 "이번 배포로 생기는 인덱스", 없으면 "이번 변경이 요구하는 인덱스가 빠졌는지" 판정.
- **신뢰 순위**: 실DB(`--db`) > 마이그레이션 > 모델 선언. 모델 `Meta.indexes`만 믿고 "커버됨"으로 단정하지 말고, 마이그레이션 누락 가능성을 "확인 필요"로 남긴다.

## 동적 쿼리 전개

- `if`로 `filter`를 조건부로 이어 붙이는 체인, `Q()` 조합, `**kwargs` 필터는 **대표 시나리오 2~3개**로 전개(`AMBIGUOUS`). 전수 X.

## 신뢰도 라벨

- `.raw("...")` 정적 문자열: `EXACT`.
- QuerySet 번역: `INFERRED`(번역 규칙은 확실하나 실제 SQL은 Django가 생성).
- 조건부 체인/`Q()` 동적 조합: `AMBIGUOUS`.
- 모든 항목에 **"`qs.query` 출력 / `DEBUG=True` + `connection.queries` / django-debug-toolbar로 실제 SQL 확인"** 안내.

## 산출물 형식

각 지점마다: **원천**(`파일:라인`, QuerySet/모델) / **추론 SQL**(+라벨) / **관계 로딩**(`select_related`/`prefetch_related` 유무) / **N+1 판정** / Tier1/Tier2 결과 / 검증 안내.

## 예시

```python
# models.py
class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)   # FK -> Django 기본 인덱스 생성
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField()
    class Meta:
        indexes = []                                           # (status, created_at) 복합 인덱스 없음

# views.py
orders = Order.objects.filter(status="paid").order_by("-created_at")   # 뷰 QuerySet
for o in orders:
    print(o.user.name)                                         # 관계 접근 - select_related 누락
```
-> 추론 SQL: `SELECT ... FROM orders WHERE status = ? ORDER BY created_at DESC` (INFERRED)
-> Tier2: `orders(status, created_at)` 인덱스 없음 -> `missing_index` 🔴 + `CREATE INDEX` 제안.
-> N+1: 루프에서 `o.user` 접근인데 `select_related("user")` 누락 -> `n_plus_one` 🔴 (해소: `.select_related("user")`).
-> `user_id`는 FK라 기본 인덱스가 있을 가능성이 높으므로 단정하지 말고 확인.

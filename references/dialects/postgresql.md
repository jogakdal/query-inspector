# SQL 방언(dialect) 노트: PostgreSQL

`dialect: auto`가 PostgreSQL로 판정하거나 `--dialect postgresql`일 때 참고한다. Tier3 EXPLAIN은 `run_explain.py`가 PostgreSQL 경로(psycopg/psycopg2 드라이버 또는 `psql` CLI)를 지원한다.

## 방언 특성
- 식별자 인용: 큰따옴표 `"col"`. 자동증가: `SERIAL`/`BIGSERIAL`/`GENERATED ... AS IDENTITY`.
- 페이징: `LIMIT n OFFSET m`. `RETURNING` 절 지원.
- 함수/연산: `ILIKE`(대소문자 무시 LIKE), `::type` 캐스트, `COALESCE`, `jsonb` 연산자.
- 문자열 결합은 `||`(표준). MySQL과 달리 `||`는 논리 OR가 아니다.

## 대소문자 무시 / LIKE 인덱스 (중요 - 처방이 룩업마다 다르다)

PostgreSQL B-Tree는 기본적으로 **`=`와 좌측 고정 `LIKE 'x%'`(C 로케일)만** 커버한다. Django 대소문자 무시 룩업의 실제 SQL과 처방:

- **`__iexact`(`UPPER(col::text) = UPPER(?)`, 등호):** `CREATE INDEX ON t (UPPER(col))` **표현식 B-Tree**. 등호라 LIKE 패턴 인덱스가 아니다.
- **`__istartswith`(`UPPER(col) LIKE UPPER('x%')`):** `CREATE INDEX ON t (UPPER(col) text_pattern_ops)` - 비-C 로케일에서 LIKE 접두 매칭은 `text_pattern_ops`(varchar면 `varchar_pattern_ops`)가 있어야 커버.
- **`__startswith`(`col LIKE 'x%'`):** 비-C 로케일이면 `CREATE INDEX ON t (col varchar_pattern_ops)` 보조 인덱스가 따로 필요하다(기본 인덱스로는 LIKE 접두가 안 걸릴 수 있음).
- **`__icontains`(`UPPER(col) LIKE UPPER('%x%')`, 선행 `%`):** B-Tree 불가. **pg_trgm GIN**: `CREATE INDEX ON t USING gin (col gin_trgm_ops)`, 대소문자 무시는 Django `GinIndex(OpClass(Upper('col'), name='gin_trgm_ops'))`.
- **표현식 인덱스의 식 일치(중요):** 표현식 인덱스는 쿼리의 식과 **정확히 일치**해야 사용된다(`UPPER(col)` 인덱스는 `UPPER(col)` 조건에만 걸리고 `LOWER(col)`엔 안 걸림). Django `functions.Upper`/`Lower`의 식을 조건과 맞춘다.

## 인덱스 제안 형식 (Django/PostgreSQL)

- **온라인 생성:** 운영 테이블은 `CREATE INDEX CONCURRENTLY`(쓰기 락 최소화). Django 마이그레이션은 `AddIndexConcurrently` + `Migration.atomic = False`.
- **부분 인덱스**(`CREATE INDEX ... WHERE active`), **표현식 인덱스**(`(lower(name))`), 커버링 `INCLUDE (cols)`.
- `managed = False`/머티리얼라이즈드 뷰는 Django가 인덱스를 관리하지 않으므로 `RunSQL`로 수동 DDL을 제안한다.
- 재사용 앱(포크/`is_model_registered`)에서는 인덱스가 어느 마이그레이션/앱에 적용되는지 경로가 달라질 수 있다.

## 정렬 / `order_by_filesort`

- B-Tree는 양방향 스캔이 가능해 **단일 컬럼 `DESC` 정렬은 오름차순 인덱스로 역방향 스캔**으로 커버된다(별도 DESC 인덱스 불필요). 단 다중 컬럼에서 방향이 섞이면(`a ASC, b DESC`) 그 방향 조합의 인덱스가 필요하다.
- 명칭 주의: 내부 지표 ID는 MySQL 중심의 `order_by_filesort`지만, PostgreSQL에선 EXPLAIN의 **`Sort` 노드**(`Sort Method: quicksort`/`external merge`)로 나타난다. 판정은 동일(정렬을 인덱스가 뒷받침하는가).

## COUNT 특성

- PostgreSQL `COUNT(*)`는 MVCC 가시성 때문에 **항상 행을 스캔**한다(인덱스만으로 즉답 불가). 큰 테이블의 매 요청 총계는 `count_large`로 보고, 근사치(`pg_class.reltuples`)/키셋/`LIMIT + 1`(다음 페이지 존재만 확인)을 권한다.

## EXPLAIN (Tier3)

`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` - ANALYZE는 실제 실행이므로 opt-in + 롤백 필수. `run_explain.py`가 `FORMAT JSON` 출력을 파싱한다. 주요 노드:

- **Seq Scan**(풀스캔) - 큰 테이블에서 경고.
- **Index Scan / Index Only Scan**(커버링, 좋음) / **Bitmap Heap + Index Scan**.
- 조인: **Nested Loop**(소량 유리) / **Hash Join** / **Merge Join**.
- 지표: `cost`, `rows`, `actual time`, `Buffers`(shared hit/read), `Rows Removed by Filter`.
- **`hypopg`** 확장: 가상 인덱스로 before/after 실행계획 비교(실제 생성 없이). 있으면 활용, 없으면 제안만.

## 버전 주의

- **PG18+ skip scan:** 다중 컬럼 B-Tree의 선두 컬럼을 건너뛰는 skip scan이 도입되어, 기존 "선두 컬럼 조건 없으면 인덱스 못 씀" 판정이 완화될 수 있다. 서버 버전을 확인하고 단정하지 않는다.

## 안티패턴 대응 요지

- `non_sargable_predicate`: 표현식 인덱스로 해결(MySQL보다 유연, 단 식 일치 필요).
- `leading_wildcard_like`: `pg_trgm` GIN으로 `%x%` 가속.
- `deep_pagination`: 키셋 페이징 동일.

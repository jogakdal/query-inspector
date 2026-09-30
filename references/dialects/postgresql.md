# SQL 방언(dialect) 노트: PostgreSQL (🔶 스텁 - M2+ 확장)

`dialect: auto`가 PostgreSQL로 판정하거나 `--dialect postgresql`일 때 참고한다. MVP에서는 아래 요지만 사용하고, 정밀 규칙은 M2 이후 `mysql.md` 수준으로 확장한다.

## 방언 특성
- 식별자 인용: 큰따옴표 `"col"`. 자동증가: `SERIAL`/`BIGSERIAL`/`GENERATED ... AS IDENTITY`.
- 페이징: `LIMIT n OFFSET m`. `RETURNING` 절 지원.
- 함수/연산: `ILIKE`(대소문자 무시 LIKE), `::type` 캐스트, `COALESCE`, `jsonb` 연산자.
- 대소문자 무시 검색은 `ILIKE` 또는 `citext`/표현식 인덱스.

## EXPLAIN (Tier3, M3)
`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` - ANALYZE는 실제 실행이므로 opt-in + 롤백 필수. 주요 노드:
- **Seq Scan**(풀스캔) - 큰 테이블에서 경고.
- **Index Scan / Index Only Scan**(커버링, 좋음) / **Bitmap Heap+Index Scan**.
- 조인: **Nested Loop**(소량에 유리) / **Hash Join** / **Merge Join**.
- 지표: `cost`, `rows`, `actual time`, `Buffers`(shared hit/read), `Rows Removed by Filter`.

## PostgreSQL 강점 (M2+에서 활용)
- **부분 인덱스**(`CREATE INDEX ... WHERE ...`), **표현식 인덱스**(`CREATE INDEX ON t (lower(name))`) -> `non_sargable_predicate` 대응이 유연.
- **`hypopg`** 확장: 가상 인덱스로 **before/after 실행계획 비교**(실제 생성 없이). 있으면 Tier3에서 활용, 없으면 제안만.
- 커버링: `INCLUDE` 컬럼.

## 안티패턴 대응 요지
- `non_sargable_predicate`: 표현식 인덱스로 해결 가능(MySQL보다 유연).
- `leading_wildcard_like`: `pg_trgm`(trigram) GIN 인덱스로 `%x%` 가속 가능.
- `deep_pagination`: 키셋 페이징 동일.

> M2에서 EXPLAIN 노드 해석/인덱스 제안/hypopg 연동을 완전 규칙으로 확장.

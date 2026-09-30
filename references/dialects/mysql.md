# SQL 방언(dialect) 노트: MySQL / MariaDB (MVP 우선)

MVP 기본 방언. `dialect: auto`가 MySQL로 판정하거나 폴백했을 때, 그리고 `--dialect mysql`일 때 참고한다. MariaDB도 이 규칙을 공유한다(차이 나는 부분은 표기).

## 방언 특성 (추출/판정 시)

- 식별자 인용: 백틱 `` `col` ``. `AUTO_INCREMENT`, `ENGINE=InnoDB`.
- 페이징: `LIMIT n [OFFSET m]` 또는 `LIMIT m, n`.
- 함수: `NOW()`/`CURDATE()`, `IFNULL()`, `GROUP_CONCAT()`, `DATE()`, `STR_TO_DATE()`.
- **문자열 결합은 `CONCAT()` - `||`는 논리 OR!** MySQL 기본 `sql_mode`에서 `||`는 문자열 결합이 아니라 논리 OR다. Oracle/PostgreSQL에서 이식한 `a || b`는 오작동하므로 `CONCAT(a, b)`로 바꾼다(`dialect_pipe_concat`).
- 문자열 비교/컬레이션: `utf8mb4_general_ci`/`_unicode_ci`(대소문자/악센트 무시). 컬레이션 불일치는 조인 인덱스를 무력화할 수 있음.
- **암시적 타입 변환 주의(MySQL 특유):** 문자열 컬럼 `= 숫자`면 **컬럼을 숫자로 캐스팅** -> 인덱스 무력화 + 예상 밖 매칭. `implicit_type_cast`로 강하게 표기.

## EXPLAIN 읽는 법 (Tier3, M3에서 실동작)

`EXPLAIN`/`EXPLAIN FORMAT=JSON`/`EXPLAIN ANALYZE`(MySQL 8.0.18+, 실제 실행 - opt-in만). 주요 컬럼:

| 컬럼 | 의미 | 경고 신호 |
|---|---|---|
| `type` | 접근 방식 | **`ALL`(풀스캔)**, `index`(인덱스 풀스캔)는 주의. 좋은 순서: `const` > `eq_ref` > `ref` > `range` > `index` > `ALL` |
| `key` | 실제 사용 인덱스 | `NULL`이면 인덱스 미사용 |
| `possible_keys` vs `key` | 후보 있는데 미채택 | 통계/조건 문제 의심 |
| `rows` | 예상 스캔 행 | 결과 대비 과도하게 크면 비효율 |
| `filtered` | 필터 후 비율(%) | 낮은데 rows 크면 조건이 인덱스를 못 씀 |
| `Extra` | 부가 정보 | 아래 참조 |

`Extra` 주요 값:
- `Using filesort` - 정렬용 별도 처리(정렬 인덱스 부재). `order_by_filesort`.
- `Using temporary` - 임시 테이블(대개 GROUP BY/DISTINCT/정렬). 비용 주의.
- `Using where` - 스토리지에서 가져와 서버가 필터(인덱스로 다 못 거름).
- `Using index` - **커버링 인덱스**(좋음, 테이블 접근 없음).
- `Using index condition` - ICP(인덱스 컨디션 푸시다운, 대체로 좋음).

## 인덱스 제안 규칙 (Tier2/3)

- **복합 인덱스 컬럼 순서:** 등호 조건 컬럼 -> 범위 조건 컬럼 -> 정렬 컬럼 순. (`WHERE a=? AND b>? ORDER BY c` -> `(a, b)` 또는 `(a, c)`는 목적에 따라)
- **leftmost prefix:** `(a, b, c)` 인덱스는 `a`, `a,b`, `a,b,c` 조건에 쓰이고 `b` 단독엔 안 쓰임.
- **커버링 인덱스:** SELECT 컬럼까지 인덱스에 포함하면 `Using index`. 좁은 조회에 유효.
- **범위 뒤 컬럼 무효:** 복합 인덱스에서 범위 조건 다음 컬럼은 정렬/탐색에 못 쓰임.
- **INVISIBLE 인덱스(8.0+):** `CREATE INDEX ... INVISIBLE` 또는 `ALTER TABLE ... ALTER INDEX ... INVISIBLE`은 인덱스가 존재해도 옵티마이저가 **무시**한다(`SET optimizer_switch='use_invisible_indexes=on'`이면 예외). 인덱스 대조 시 INVISIBLE은 **없는 것으로** 보고, 필요하면 `ALTER TABLE <t> ALTER INDEX <idx> VISIBLE;`을 제안한다. `SHOW INDEX`의 `IS_VISIBLE` 컬럼으로 확인.

## 안티패턴별 MySQL 대응

- `non_sargable_predicate`: `WHERE DATE(created_at)=?` -> 범위(`>= AND <`)로. 함수 인덱스는 **MySQL 8.0.13+ functional index** 또는 생성 컬럼(generated column)+인덱스. MariaDB는 가상 컬럼+인덱스.
- `leading_wildcard_like`: `LIKE '%x%'` -> 접두 검색 가능하면 `'x%'`, 아니면 **FULLTEXT 인덱스**(`MATCH ... AGAINST`) 검토.
- `large_in_clause`: MySQL은 하드 상한은 아니나 `max_allowed_packet`/플랜 비용 문제 -> 청크/조인.
- `deep_pagination`: `LIMIT 100000, 20` -> 키셋 `WHERE id < :last ORDER BY id DESC LIMIT 20`.
- 힌트: 필요 시 `USE INDEX`/`FORCE INDEX`/`IGNORE INDEX`, 옵티마이저 힌트 `/*+ ... */`(8.0). 남용 금지 - 근거와 함께 제안.

> MariaDB 차이: `EXPLAIN ANALYZE` 문법/JSON 포맷/옵티마이저 힌트 세부가 다를 수 있음. 실행계획 해석은 대동소이하나 버전 확인 후 제안.

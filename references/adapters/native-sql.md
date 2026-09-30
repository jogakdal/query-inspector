# 어댑터: `native-sql` (MVP / 완전 지원)

코드에 직접 쓰인 SQL 문자열과, 마이그레이션이 아닌 곳의 원시 SQL을 추출한다. 추출 난이도 **하** - 문자열이 정적이면 `EXACT`.

## 대상 파일/지점

- **SQL 문자열 리터럴**
  - Kotlin raw string `"""SELECT ... """`, 일반 문자열 `"SELECT ..."`.
  - Java text block `"""..."""`, 문자열 리터럴.
- **JDBC 계열 API 호출의 인자**
  - Spring `JdbcTemplate`/`NamedParameterJdbcTemplate`: `query`, `queryForObject`, `queryForList`, `update`, `batchUpdate`.
  - `EntityManager.createNativeQuery(...)`, JPA `@Query(value = "...", nativeQuery = true)`.
  - R2DBC `DatabaseClient.sql("...")`, jOOQ `dsl.fetch("...")`/plain SQL.
  - MyBatis 애노테이션(`@Select` 등)은 `mybatis` 어댑터가 처리하지만, 순수 문자열 SQL이면 이 규칙도 참고.

> diff에 SQL 문자열 일부만 보이면, **문자열 상수/함수 전체를 Read**해서 SQL을 온전히 확보한다. 상수로 분리된 SQL(`companion object`/`static final String`)도 추적한다.

## SQL 식별 기준

문자열이 SQL인지 판단: 선두 키워드(`SELECT`/`INSERT`/`UPDATE`/`DELETE`/`WITH`/`MERGE`) 또는 `FROM`/`WHERE`/`JOIN` 등 절 키워드 동반. 로그 메시지/경로 문자열 등 오탐을 배제한다.

## 정적 vs 동적(문자열 결합)

- **정적 문자열** -> `EXACT`. 그대로 Tier1 휴리스틱 적용.
- **문자열 결합/보간으로 조립되는 SQL** -> 동적. 라벨 `AMBIGUOUS`(분기 많음) 또는 `INFERRED`(단순).
  ```kotlin
  // 결합: 대표 시나리오로 전개 + 인젝션 위험 점검
  val sql = "SELECT * FROM orders WHERE 1=1" +
            (if (status != null) " AND status = ?" else "") +
            " ORDER BY $sortColumn"        // <- 문자열 보간: SQL 인젝션 위험 + non-whitelist
  ```
  - 대표 조건 조합 2~3개로 전개해 각각 분석.
  - **바인드가 아닌 문자열 보간**(Kotlin `$var`, Java `+ var`, `String.format`)으로 값이 들어가면 **`string_substitution`(🔴 critical)** 으로 표기한다(SQL 인젝션 + 플랜 캐시 오염 - `heuristics.md` ^ 항목). 바인드(`?`/`:name`)로 치환하고, ORDER BY 컬럼명처럼 불가피하면 화이트리스트로 강제한다.

## 파라미터 표기

- 위치 파라미터 `?`, 명명 파라미터 `:name`(NamedParameterJdbcTemplate) -> 안전한 바인드. 정상.
- 문자열 보간으로 삽입된 값 -> 위험 표기.
- **단, IN 절 크기는 별개:** `:ids`처럼 **바인딩이라도** 컬렉션 크기가 크면(수백~수천) `large_in_clause` 대상이다 - "바인딩=정상"이 IN 크기 문제를 가리지 않게 한다.

## 산출물 형식

각 SQL마다:
- **원천**: `파일:라인`, 감싼 메서드/상수명.
- **추론 SQL**: 정적부 `EXACT`, 결합 시나리오는 라벨과 함께.
- **바인딩/보간**: `?`/`:name`(안전) vs 문자열 보간(위험) 구분.
- Tier1 휴리스틱(`references/heuristics.md`) 적용 결과.

## 자주 걸리는 것

- **SQL 방언(dialect) 이질 문법(`dialect_pipe_concat`)**: 추출한 SQL 텍스트에 `||`/`NVL`/`SYSDATE`/`ROWNUM`/`FROM DUAL` 등 **감지 방언과 다른 문법**이 있는지 스캔. 특히 mysql에서 `||`는 문자열 결합이 아니라 논리 OR이므로 정확성 이슈(critical)로 표기. -> `heuristics.md` * 항목.
- `SELECT *`(`select_star`), 선행 와일드카드 LIKE(`leading_wildcard_like`), `WHERE DATE(col)=...`(`non_sargable_predicate`), 페이징 없는 대량 조회(`unbounded_result`), 큰 `IN`(`large_in_clause`), 문자열 보간 인젝션(`string_substitution`).
- **인덱스 커버 판정은 Tier2로 위임:** WHERE/JOIN/ORDER BY 컬럼의 인덱스 대조/`missing_index`/**INVISIBLE 인덱스**(존재해도 옵티마이저 미사용 -> 미인덱스 취급) 판정은 `references/tier2-index-matching.md`를 따른다.

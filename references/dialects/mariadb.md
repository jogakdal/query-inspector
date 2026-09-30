# SQL 방언(dialect) 노트: MariaDB

`--dialect mariadb` 또는 자동 감지가 MariaDB(드라이버 `mariadb-java-client`, URL `jdbc:mariadb:`, `MariaDBDialect`)로 판정했을 때 참고한다. **MariaDB는 MySQL 규칙을 대부분 공유**하므로 기본은 [`mysql.md`](./mysql.md)를 따르고, 아래 차이만 유의한다.

## MySQL과의 주요 차이

- **Oracle 호환 함수(부분/조건부 지원):** `NVL(a,b)`는 MariaDB가 `sql_mode`와 무관하게 기본 지원한다(`IFNULL` 별칭) -> 방언 위반이 **아니다**(`IFNULL`/`COALESCE` 권장은 이식성 info로만). 그러나 **`NVL2(a,b,c)`/`DECODE(...)` 등 나머지 Oracle 호환 함수는 `sql_mode=ORACLE`(10.3+ Oracle 호환 모드)에서만** 동작한다 - 서버가 이 모드가 아니면 오류/오작동한다. 특히 **`DECODE`는 기본 모드에서 Oracle식(다중 인자 조건 분기)이 아니라 복호화 함수** 의미여서 결과가 완전히 다르다. 따라서 `NVL2`/`DECODE`는 "위반 아님"으로 단정하지 말고, **서버 `sql_mode`(`SELECT @@sql_mode`)에 `ORACLE`이 포함되는지 확인**하도록 안내하고, 확인 불가/미포함이면 `IFNULL`+`CASE`(또는 `COALESCE`)로의 치환을 제안한다.
- **문자열 결합:** MySQL과 같이 기본 `||`는 논리 OR이고 결합은 `CONCAT()`. 단 MariaDB 배포는 `sql_mode=PIPES_AS_CONCAT`이 켜진 경우가 MySQL보다 흔하니 서버 설정을 확인한다.
- **함수 인덱스:** MySQL 8.0.13+ functional index 대신 **가상(생성) 컬럼 + 인덱스**를 사용한다.
- **EXPLAIN:** `ANALYZE`/`EXPLAIN FORMAT=JSON`의 문법/출력이 MySQL과 세부 차이가 있다. 해석은 대동소이하므로 `mysql.md`의 EXPLAIN 표를 참고하되, 서버 버전을 확인하고 제안한다.

그 밖의 특성(백틱 식별자/`LIMIT` 페이징/`implicit_type_cast`/인덱스 제안 규칙 등)은 [`mysql.md`](./mysql.md)와 동일하게 적용한다.

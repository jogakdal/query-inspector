# SQL 방언(dialect) 자동 감지 (`dialect: auto`)

`SKILL.md` Stage 0.5에서 사용한다. 설정 `dialect: auto`(기본)일 때, 프로젝트 단서로 SQL 방언을 추론한다. **모든 방언을 망라하기보다 단서로 추정하고, 실패하면 MySQL로 폴백**하는 것이 원칙이다.

지원 방언 토큰: `mysql` / `mariadb`(MySQL 규칙을 공유하되 `NVL`/`NVL2` 등 Oracle 호환 함수를 10.3+에서 지원) / `postgresql` / `oracle` / `ansi`(방언 무관 안전 규칙만).

---

## 결정 우선순위

위에서 아래로, **먼저 확정되면 멈춘다.**

### 0. 명시값 (최우선)
- `--dialect <값>` 인자 -> 그대로 사용, 감지 생략.
- 설정 `dialect:`가 `auto`가 아니면 -> 그대로 사용.

### 1. 빌드 의존성 (가장 신뢰도 높음)
`build.gradle` / `build.gradle.kts` / `pom.xml`을 읽어 JDBC 드라이버를 찾는다.

| 의존성 좌표(부분 일치) | 방언 |
|---|---|
| `mysql:mysql-connector-j`, `com.mysql:mysql-connector-j`, `mysql-connector-java` | `mysql` |
| `software.aws.rds:aws-mysql-jdbc`, `software.amazon.jdbc:aws-advanced-jdbc-wrapper` (driver `software.aws.rds.jdbc.mysql.Driver`) | `mysql` (AWS RDS/Aurora MySQL 래퍼 - URL은 `jdbc:mysql:`) |
| `org.mariadb.jdbc:mariadb-java-client` | `mariadb` (MySQL 규칙 공유 + Oracle 호환 함수 일부) |
| `org.postgresql:postgresql` | `postgresql` |
| `com.oracle.database.jdbc:ojdbc*`, `com.oracle.ojdbc` | `oracle` |
| `com.h2database:h2` | (테스트용일 가능성 높음 -> 단독이면 확정 근거로 약하게, 다른 단서 우선) |

여러 드라이버가 잡히면(예: 운영 MySQL + 테스트 H2) **테스트 스코프/H2는 가중치를 낮추고** 운영 드라이버를 택한다. 그래도 충돌이면 다음 단계로.

**Python 프로젝트**는 `requirements*.txt`/`pyproject.toml`의 드라이버로 판단한다: `psycopg2`/`psycopg`(`postgresql`), `mysqlclient`/`PyMySQL`(`mysql`), `oracledb`/`cx_Oracle`(`oracle`), 표준 라이브러리 `sqlite3`(개발용 - `ansi` 규칙 위주).

### 2. DataSource URL
`application.yml` / `application.yaml` / `application*.properties` / `*.conf`에서 접속 URL 스킴을 본다.

| URL 스킴 | 방언 |
|---|---|
| `jdbc:mysql:` | `mysql` |
| `jdbc:mariadb:` | `mariadb` |
| `jdbc:postgresql:` , `r2dbc:postgresql:` | `postgresql` |
| `jdbc:oracle:thin:` , `jdbc:oracle:` | `oracle` |
| `jdbc:h2:` | 약한 근거(테스트 추정) |

프로파일별로 다르면(`application-prod.yml` vs `-local.yml`) **운영/기본 프로파일**을 우선한다. 값이 환경변수 플레이스홀더(`${...}`)로 가려져 스킴만 보이면 스킴으로 판단한다.

**Python**: Django `settings.py`의 `DATABASES['default']['ENGINE']`(`django.db.backends.postgresql` -> `postgresql`, `.mysql` -> `mysql`, `.oracle` -> `oracle`, `.sqlite3` -> 개발용), SQLAlchemy 접속 URL 스킴(`postgresql://`/`postgresql+psycopg://` -> `postgresql`, `mysql://`/`mysql+pymysql://` -> `mysql`, `oracle://` -> `oracle`).

**Python 멀티 DB 프로젝트(중요):** 라이브러리/프레임워크 앱은 optional extras로 여러 드라이버를 **동시에** 선언하는 경우가 많다(`pyproject.toml`의 `[project.optional-dependencies]`에 `postgres`/`mysql` 공존, 기본 설정은 `sqlite`). 드라이버 존재만으로는 결정할 수 없으므로 **운영 구성을 우선**해 판정한다:
1. **운영 배포 구성** - `docker-compose*.yaml`의 서비스 이미지(`postgres:18-alpine`)와 `DATABASE_URL`/`DATABASE_URI` 환경변수, `config.cfg.template`/`.env.example`의 접속 URL 스킴.
2. **방언 전용 코드** - PostgreSQL FTS(`tsvector`/`search_vector`/GIN), 특정 방언에만 쓰이는 마이그레이션/함수.
3. 그래도 불명확하면 기본 설정값(흔히 `sqlite`)이 아니라 **production에 가장 가까운 구성**을 택하고, 멀티 DB임을 리포트에 명시한다. 방언 의존 판정(FK 자동 인덱스 등)은 그 방언 기준으로 하되 다른 배포 타깃의 차이를 부기한다(예: "MySQL/InnoDB 배포면 FK 단일 인덱스가 자동 생성되어 일부 `missing_index`가 완화됨").

### 3. Hibernate / JPA dialect 설정
`spring.jpa.database-platform` 또는 `hibernate.dialect` 값.

| 값(부분 일치) | 방언 |
|---|---|
| `MySQLDialect` | `mysql` |
| `MariaDBDialect` | `mariadb` |
| `PostgreSQLDialect` | `postgresql` |
| `OracleDialect`, `Oracle12cDialect` | `oracle` |

### 4. 마이그레이션 / SQL 방언 특성 (문법 지문)
Flyway/Liquibase 마이그레이션이나 변경된 SQL의 문법 특성으로 추정한다.

| 특성 신호 | 시사 방언 |
|---|---|
| 백틱 식별자 `` `col` ``, `AUTO_INCREMENT`, `ENGINE=InnoDB`, `LIMIT n`, `NOW()`, `IFNULL(`, `GROUP_CONCAT(` | `mysql` |
| `SERIAL`/`BIGSERIAL`, `RETURNING`, `::type` 캐스트, `ILIKE`, `LIMIT n OFFSET m`, `nextval(`, `jsonb` | `postgresql` |
| `ROWNUM`, `SYSDATE`, `DUAL`, `NVL(`, `CONNECT BY`, `SEQUENCE.NEXTVAL`, `FETCH FIRST n ROWS ONLY`, `VARCHAR2` | `oracle` |
| 큰따옴표 표준 식별자만, 위 특성 없음 | `ansi` |

여러 특성이 섞이면(멀티-DB 지원 코드) 다수결 + 상위 단계(1~3) 근거를 우선.

---

## 폴백과 표기

- **미검출/판단 불가 ->** `mysql`로 폴백(MVP 기본). 단, 방언 의존 규칙은 보수적으로 적용하고 `ansi` 안전 패턴 위주로 판단한다.
- **다중/충돌 ->** 상위 우선순위 단계의 결론을 채택하되, 리포트에 감지 근거와 대안을 남기고 `--dialect`로 강제할 것을 안내한다.
- 리포트 헤더에 항상 남긴다: `방언: mysql (근거: build.gradle의 mysql-connector-j)` 또는 `방언: mysql (폴백 - 단서 없음, --dialect로 지정 권장)`.

---

## 감지 절차 요약 (실행 지침)

1. 인자/설정 명시값 확인 -> 있으면 종료.
2. 빌드 파일 -> URL -> Hibernate dialect -> SQL 특성 순으로 단서 수집.
3. 가장 신뢰도 높은 단계에서 단일 방언이 나오면 채택.
4. 충돌/부재면 MySQL 폴백 + 리포트에 불확실성 명시.
5. 결정된 방언의 `dialects/<dialect>.md`를 로드해 이후 분석의 방언 규칙으로 사용.

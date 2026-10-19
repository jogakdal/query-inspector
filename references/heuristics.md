# 휴리스틱 카탈로그 (Tier1 중심 / 일부 Tier2)

주로 **코드/쿼리 텍스트만으로**(Tier1) 검출하는 안티패턴 카탈로그다. `SKILL.md` Stage 3에서 적용한다. 일부 항목(특히 * `missing_index`, `order_by_filesort`)은 스키마(Tier2)가 있어야 확정되며, 각 항목의 "요구 깊이"를 따른다.

> *** 이 스킬의 최우선 표적은 `missing_index`(인덱스 누락)와 `n_plus_one`이다.** 이 도구의 주된 동기가 *"쿼리를 만들고 인덱스를 걸지 않은 채 배포"* 하는 문제였다. 따라서 스키마가 제공된 리뷰라면 **인덱스 누락 점검과 구체적 인덱스 추가 제안을 최우선으로** 수행하고, 대표 리포트에는 인덱스 추가 제안이 포함되어야 한다.

## 사용 방법

- 각 항목의 **ID**는 설정 `severity_rules`의 키와 일치한다. 사용자 설정이 있으면 그 심각도로 오버라이드한다.
- 탐지되면 리포트에 `[심각도] 이름 - 위치 (신뢰도라벨)` / 원천 / 근거 / 추론 SQL / 수정 제안을 채운다.
- **거짓 양성을 경계한다.** "신호"가 보여도 맥락상 문제 아니면(예: 결과가 확실히 소량, 배치성 1회 실행) 심각도를 낮추거나 info로 기록한다. 확신이 없으면 단정 대신 "확인 권장"으로 적는다.
- **도달 가능성(활성/비활성/미사용) 판정 - 레거시에서 특히 중요.** 결함을 보고하기 전에 그 코드가 **실제 실행 경로에 있는지** 먼저 확인한다: (1) 주석 처리/비활성 step·분기, (2) 호출부가 없는(dead) 매퍼 문장/메서드, (3) 활성. **비활성/미사용 경로의 결함은 심각도를 `⚪ info`로 하향**하고 "비활성/미사용 - 실행 경로 없음"을 근거에 명시한다(활성 결함이 리포트 상단을 차지하도록). 호출부 추적: MyBatis는 `namespace -> 매퍼 인터페이스 -> 그 타입을 참조하는 호출부`(동명 메서드 혼동 주의 - 반드시 매퍼 "타입" 기준), JPA/DAO는 메서드 참조로. 상세: `references/adapters/mybatis.md`.
- 심각도 기본값은 각 항목의 *기본 심각도*. SQL 방언(dialect) 의존 판단은 `dialects/<dialect>.md`를 함께 본다.

**반복형(`n_plus_one`/`write_in_loop`/`duplicate_query`) 심각도 매트릭스** - 반복 비용은 "반복 횟수 N의 상한 x 실행 빈도"로 정한다. 같은 이슈를 매번 다르게(critical/warn) 판정하지 않도록, 운영자가 프로젝트 기준을 `severity_rules`로 고정하길 권한다.

**적용 우선순위:** 사용자 설정 `severity_rules`에 해당 ID가 있으면 **그 값이 최우선(운영자 고정값)**이며 이 매트릭스로 덮어쓰지 않는다. 설정이 없을 때만 매트릭스로 판정한다 - 매트릭스는 기본값 산출기다. example 설정의 값(`n_plus_one: critical` 등)은 **예시 기본값**이며, 프로젝트가 자체 `.query-inspector.yml`로 고정하지 않는 한 매트릭스가 우선한다.

**심각도 결정 순서(한 곳 정리 - 규칙이 겹칠 때 이 순서로).**
1. **도달 가능성**(위) - 비활성/미사용이면 `info`로 하향. **다른 모든 규칙에 우선한다.**
2. **운영자 고정값** - 프로젝트 `.query-inspector.yml`의 `severity_rules`에 ID가 있으면 그 값(example의 값은 "예시 기본값"이라 여기 해당하지 않음).
3. **SCHEMA-PARTIAL 고정** - `missing_index`가 스키마 미확인이면 `warn` 고정(`tier2-index-matching.md` 5절). severity_rules의 critical보다 이게 우선하고, 확정 소스(`LIVE-SCHEMA`/`SCHEMA-CONFIRMED`) 확보 시 critical로 승격.
4. **반복형 매트릭스** - `n_plus_one`/`write_in_loop`/`duplicate_query`는 위 매트릭스.
5. **기본 심각도** - 그 외는 각 항목의 기본값.

| N 상한 \ 실행 빈도 | 매 요청·스토어프런트(고빈도) | 스태프·admin(저빈도) | 외부 연동 API(빈도 미상) | 배치 1회 |
|---|---|---|---|---|
| 무제한(페이지 없음) | 🔴 critical | 🟡 warn | 🟡 warn (호출 빈도 확인 권장) | 🟡 warn |
| 페이지 크기(수십~수백) | 🟡 warn | 🟡 warn | 🟡 warn | ⚪ info |
| 소량(확실히 수개 이하) | ⚪ info | ⚪ info | ⚪ info | ⚪ info |

> **외부 연동 API 열:** 호출 빈도를 코드만으로 확정하기 어려운 외부 연동/배치 트리거 경로다. 미상이면 보수적으로 warn에 두되 "호출 빈도 확인 권장"을 함께 적고, 무제한 N이 확인되면 critical로 올린다.

심각도 기호: 🔴 critical / 🟡 warn / ⚪ info

---

## * `missing_index` - 인덱스 누락 / 기본 🔴 critical / 요구 깊이 **Tier2**

**이 스킬의 대표 표적.** "쿼리를 만들고 인덱스를 걸지 않은 채 배포"하는 문제를 잡기 위해 존재한다. 스키마(DDL/엔티티/마이그레이션 **또는 `--db` 실 DB 조회**)가 있어야 확정되며, 없으면 "후보"로만 표기하고 스키마(또는 `--db`) 제공을 권한다. **특히 MyBatis 전용 레거시(엔티티/마이그레이션/DDL이 리포에 없음)에서는 스키마 없이 판정이 반쪽이 되기 쉽다** - 흔한 상황이므로, 이 경우 리포트에 `schema.ddl` 지정이나 `--db` 연결로 확정할 수 있음을 **분명히/눈에 띄게** 안내해 대표 기능이 무력화되지 않게 한다.

**탐지 신호**
- 쿼리의 **WHERE(등호/범위) / JOIN 키 / ORDER BY** 컬럼을 수집.
- 스키마 인덱스와 대조 -> 어떤 인덱스로도 커버되지 않는 컬럼(조합)이 있으면 누락.
- 특히: **FK 컬럼**(예: `orders.user_id`)에 인덱스 없음, 정렬 컬럼이 인덱스 미포함, 등호+범위 복합 조건을 커버할 인덱스 부재.

**왜 문제인가** 인덱스가 없으면 풀스캔/filesort. 로컬 소량에선 멀쩡하다 데이터가 쌓이면 급격히 느려진다 - **이 도구의 주된 동기가 된 바로 그 사고 유형**이다.

**제안 (반드시 구체적 DDL로)**
- `CREATE INDEX idx_<table>_<cols> ON <table>(<col>, ...);` 형태로 **컬럼과 순서까지** 제시.
- **컬럼 순서 규칙:** 등호 조건 -> 범위 조건 -> 정렬 컬럼 (방언 세부는 `dialects/<dialect>.md`).
- 가능하면 **커버링**(SELECT 컬럼 포함)/**leftmost prefix** 활용. 기존 인덱스로 커버되면 신규 대신 확장을 제안.
- **트레이드오프 명시:** 쓰기(INSERT/UPDATE) 시 인덱스 갱신 비용, 낮은 카디널리티 컬럼은 효과 제한 - 무분별한 추가를 부추기지 않는다.

**마이그레이션 교차 (최강 신호)** 같은 변경분에 새 쿼리가 추가됐는데 **그 컬럼 인덱스가 함께 온 마이그레이션에 없다** -> "이번 배포로 필요한 인덱스가 빠졌다"고 강하게 지적한다(`migration` 어댑터가 수집한 DDL과 대조).

**근거 라벨 (과신 방지)**
- `LIVE-SCHEMA` - `--db`로 실 DB 스키마를 직접 조회(`SHOW INDEX`/`information_schema`). 실제 배포 상태 기준 - **최고 신뢰**.
- `SCHEMA-CONFIRMED` - 대상 테이블 DDL 전체를 확인했고 인덱스가 정말 없음(확정).
- `SCHEMA-PARTIAL` - 스키마 소스가 불완전(엔티티만/DDL 일부) -> "미확인, 확인 필요"로 심각도와 어조를 낮춘다.

**INVISIBLE 인덱스(MySQL 8.0+) 변형 (중요):** 인덱스가 **존재해도 `INVISIBLE`이면 옵티마이저가 사용하지 않는다**(DDL의 `... INVISIBLE`, `SHOW INDEX`의 `IS_VISIBLE=NO`). **"인덱스 있음 -> OK"로 판정하면 안 된다** - 해당 컬럼(조합)은 사실상 미인덱스로 간주해 `missing_index`로 다루되, 신규 생성 대신 **`ALTER TABLE <t> ALTER INDEX <idx> VISIBLE;`**(전환)을 제안한다. 단 INVISIBLE이 의도적(삭제 전 영향 검증 등)일 수 있으니 코드 주석/마이그레이션 맥락을 함께 확인하고, 실제 사용 여부는 `--db` EXPLAIN으로 확증을 권한다.

**예시**
```sql
-- 쿼리(diff): SELECT id, amount FROM orders
--             WHERE status = ? AND created_at >= ? ORDER BY created_at DESC
-- 스키마: orders(PK=id)만 인덱스 존재 -> status/created_at 미인덱스 (SCHEMA-CONFIRMED)
CREATE INDEX idx_orders_status_created ON orders (status, created_at);
-- 순서 근거: status(등호) 선두 -> created_at(범위+정렬) 후행 -> range와 ORDER BY 동시 커버(filesort 제거)
-- 트레이드오프: orders 쓰기 비용 소폭 증가. status 카디널리티가 매우 낮으면 (created_at) 단일도 검토.
```

---

## 1. `n_plus_one` - N+1 쿼리 / 기본 🔴 critical

반복 실행 중 연관 데이터를 건건이 다시 조회하는 패턴. 이 스킬의 최우선 표적.

**탐지 신호**
- 컬렉션 순회(`forEach`/`map`/`for`/스트림) 안에서 연관 엔티티 접근 또는 리포지토리 재호출.
- JPA: `LAZY` 연관을 루프에서 접근하는데 `join fetch`/`@EntityGraph` 없음. (jpa 어댑터에서 정밀)
- MyBatis: `<resultMap>`의 `<association>`/`<collection>`이 **중첩 select**(`select=` 속성)로 매핑됨 -> 부모 N건마다 자식 select 실행.
- 서비스 코드에서 "목록 조회 후 각 항목마다 상세 조회".

**왜 문제인가** 목록 크기 N에 비례해 쿼리가 N(+1)회 -> 지연/DB 부하 급증. 로컬 소량 데이터에선 안 보이다 운영에서 터진다.

**수정 제안** 조인으로 한 번에(`join fetch`/`@EntityGraph`/MyBatis 중첩 결과 매핑 `<collection>` + 조인), 또는 IN 절 배치 로딩(`where id in (...)`), 또는 2차 캐시.

```
// 나쁨: 부모 목록마다 자식 조회
orders.forEach { it.items }               // items가 LAZY -> SELECT ... WHERE order_id=? (x N)
// 좋음
@EntityGraph(attributePaths = ["items"])  // 또는 join fetch
```

---

## * `dialect_pipe_concat` - 방언 불일치 문법 / 기본 🔴 critical / **정확성**(방언 감지 연계)

감지된 방언에서 **다른 방언의 문법이 잘못 동작**하는 경우. 성능이 아니라 **정확성** 문제라 심각도가 높다. 방언 자동 감지(`dialect-detection.md`)가 있어야 판정하며, 방언이 불확실하면 "확인 필요"로 낮춘다. 타 DB(Oracle/PostgreSQL)에서 코드를 옮길 때 흔히 발생한다.

**대표 - `||` 문자열 결합 (ID `dialect_pipe_concat`)**
- **MySQL 기본 `sql_mode`에서 `||`는 논리 OR** -> `a || b`가 문자열 결합이 아니다. `WHERE x LIKE '%' || ? || '%'`가 완전히 잘못된 조건이 된다.
- 제안: MySQL은 `CONCAT(...)`. 서버에 `PIPES_AS_CONCAT`이 설정됐는지 확인(`SELECT @@sql_mode;`)하되, 이식성을 위해 `CONCAT` 권장.

**같은 부류의 방언 이식성 함정 (상황별 심각도)**
| 문법 | 방언별 차이 | 조치 |
|---|---|---|
| 문자열 결합 | MySQL `CONCAT` / PostgreSQL/Oracle/ANSI `\|\|` / SQL Server `+` | 감지 방언에 맞게 |
| NULL 대체 | Oracle `NVL`/`NVL2`/`DECODE` / MySQL `IFNULL` / 표준 `COALESCE` | `COALESCE` 권장. `mariadb`는 `NVL`만 기본 지원(위반 아님), `NVL2`/`DECODE`는 `sql_mode=ORACLE` 한정 -> 확인 안내(`dialects/mariadb.md`) |
| 현재시각 | Oracle `SYSDATE` / MySQL/PG `NOW()`/`CURRENT_TIMESTAMP` | 방언 함수 |
| 페이징 | MySQL/PG `LIMIT` / Oracle `ROWNUM`/`FETCH FIRST` / SQL Server `TOP` | 방언 문법 |
| 더미 테이블 | Oracle `FROM DUAL` / 기타는 불필요 | 제거/조정 |

**탐지** 어댑터가 추출한 SQL 텍스트에서 위 문법을 스캔하고 **감지 방언과 대조**한다. 감지 방언과 다른 문법이면 표기하며, `||`처럼 정확성을 깨는 것은 critical, 단순 이식성 차이는 warn 이하로.

> **MariaDB 주의(거짓양성/음성 모두 방지):** `mariadb` 방언에서 **`NVL`은 기본 지원**(위반 아님, `IFNULL`/`COALESCE` 권장은 이식성 info로만)이지만, **`NVL2`/`DECODE`는 `sql_mode=ORACLE`에서만** 동작한다(기본 모드에선 미동작 - `DECODE`는 의미가 다른 복호화 함수). 따라서 `mariadb`라도 `NVL2`/`DECODE`는 "안전"으로 단정하지 말고 서버 `sql_mode` 확인을 안내한다. 상세: `dialects/mariadb.md`.

**신뢰도** 방언이 빌드/스키마로 확정되면 강함(`EXACT`), 폴백/불확실이면 "확인 필요"로 낮춘다.

---

## ^ `string_substitution` - 문자열 치환 인젝션(MyBatis `${}`/문자열 결합 SQL) / 기본 🔴 critical / **보안/정확성**

바인딩(`#{}`/`?`) 대신 SQL 문자열에 값을 **직접 치환**하는 패턴. **SQL 인젝션**과 **플랜 캐시 오염**을 동시에 유발한다. MyBatis/native SQL 공통 표적이며, 보안 관점에서는 이 스킬이 검출하는 가장 심각한 결함이다.

**탐지 신호**
- MyBatis에서 `#{param}`(바인딩) 대신 **`${param}`**(문자열 치환) 사용. 세부 규칙: `references/adapters/mybatis.md`.
- native/문자열 SQL에서 파라미터를 **문자열 결합**으로 삽입: `"... WHERE name = '" + name + "'"`, `String.format(...)`으로 값 주입, Kotlin 템플릿 `"... = $value"`.
- 바인딩이 불가한 위치(컬럼명/`ORDER BY` 방향 등)에 `${}`를 쓰면서 **허용값 화이트리스트가 없는** 경우.

**왜 문제인가**
- **SQL 인젝션:** 외부 입력이 `${}`/문자열 결합으로 들어가면 쿼리 구조 자체가 조작될 수 있다 - 가장 심각한 보안 결함.
- **플랜 캐시 오염:** 값이 SQL 텍스트에 박혀 실행마다 다른 쿼리가 되어 프리페어드 스테이트먼트 캐시가 무력화된다.

**수정 제안**
- 값은 **`#{}`(MyBatis)/`?`/명명 파라미터(native)**로 바인딩한다.
- 컬럼명/정렬 방향처럼 바인딩이 불가한 동적 요소에 `${}`가 꼭 필요하면 **허용값 화이트리스트**로 강제하고 사용자 입력을 직접 넣지 않는다(`ORDER BY ${col}` -> 허용 컬럼 매핑을 거친 안전한 식별자만).

```
// 나쁨(MyBatis): WHERE name = '${name}'   // 인젝션 + 플랜 캐시 오염
// 좋음:          WHERE name = #{name}
// 나쁨(native):  "... WHERE id = " + id
// 좋음:          "... WHERE id = ?"        // 바인드
```

---

## 2. `select_star` - `SELECT *` / 과다 컬럼 / 기본 🟡 warn

**탐지 신호** `SELECT *`, 또는 필요 이상으로 많은 컬럼, 특히 대형/BLOB/TEXT 컬럼 포함 테이블에서.

**왜 문제인가** 불필요한 I/O/네트워크, 커버링 인덱스 무력화, 컬럼 추가 시 예기치 않은 파급. ORM에서 엔티티 전체 로딩이 습관적 `SELECT *`가 되는 경우도 포함.

**수정 제안** 실제 사용하는 컬럼만 명시. 조회 전용은 projection/DTO. 대형 컬럼은 지연 로딩 분리.

---

## 3. `non_sargable_predicate` - 인덱스 무력화 조건(비-SARGable) / 기본 🟡 warn

WHERE/JOIN/ORDER BY의 **인덱스 컬럼을 가공**해 인덱스를 못 쓰게 만드는 패턴.

**탐지 신호**
- 인덱스 후보 컬럼을 함수로 감쌈: `WHERE DATE(created_at) = ?`, `WHERE UPPER(name) = ?`, `WHERE SUBSTR(code,1,2)=?`.
- 컬럼에 산술 연산: `WHERE price * 1.1 > ?`, `WHERE col + 0 = ?`.

**왜 문제인가** 컬럼이 함수/연산의 인자가 되면 B-Tree 인덱스 레인지 탐색이 불가 -> 풀스캔.

**수정 제안** 조건을 컬럼 단독으로 재작성 - 값 쪽을 가공한다.
```
-- 나쁨               ->  좋음(범위로 치환)
WHERE DATE(created_at) = '2026-08-26'
  ->  WHERE created_at >= '2026-08-26 00:00:00' AND created_at < '2026-08-27 00:00:00'
WHERE UPPER(name) = 'KIM'
  ->  대소문자 무시 컬레이션 사용, 또는 정규화 컬럼/함수 기반 인덱스(방언별)
```
방언별 함수 기반 인덱스 지원 여부는 `dialects/<dialect>.md` 참고.

---

## ^ `derived_table_filter` - 파생 테이블 밖 필터(조건 푸시다운 실패) / 기본 🟡 warn

서브쿼리/파생 테이블(인라인 뷰)을 만들고 **바깥에서 `WHERE`로 필터**하는 패턴. 옵티마이저가 조건을 파생 테이블 안으로 밀어넣지(pushdown) 못하면, 파생 테이블이 **먼저 전량 구체화(materialize)된 뒤** 필터돼 안쪽 인덱스/조기 필터를 놓친다. 레거시 MyBatis 목록 쿼리에서 흔하다.

**탐지 신호**
- `SELECT ... FROM (SELECT ... FROM t ...) d WHERE d.col = ?`처럼 파생 테이블 결과를 바깥 `WHERE`로 거르는 형태.
- 파생 테이블에 `GROUP BY`/`DISTINCT`/`UNION`/`LIMIT`가 있어 옵티마이저가 pushdown을 포기하기 쉬운 경우.

**왜 문제인가** 파생 테이블이 전량 구체화된 뒤 바깥 필터가 적용되면, 안쪽 테이블의 인덱스로 조기에 행을 줄이지 못해 대량 스캔/임시 테이블이 생긴다. (MySQL은 버전/`derived_condition_pushdown` 설정에 따라 다르고, 구버전/복잡 쿼리에선 자주 실패한다.)

**수정 제안** 필터 조건을 **파생 테이블 안(`WHERE`)으로 이동**해 조기에 거른다. 가능하면 조인으로 평탄화(flatten)하고, 옵티마이저의 condition pushdown에 의존하지 말고 안쪽에서 명시적으로 필터한다.

---

## 4. `implicit_type_cast` - 암시적 타입 변환 / 기본 🟡 warn

**탐지 신호** 컬럼 타입과 다른 리터럴/바인드 비교로 보이는 지점: 문자열 컬럼에 숫자 비교(`WHERE phone = 1012345678`), 숫자 컬럼에 따옴표 값, 날짜 컬럼에 문자열. (정밀 판정은 Tier2 스키마 필요 - Tier1은 "의심" 수준으로 표기)

**왜 문제인가** DB가 한쪽을 캐스팅하면서 인덱스를 못 쓰거나(특히 컬럼 쪽 캐스팅), 예상치 못한 결과/성능 저하. MySQL의 문자열<->숫자 비교가 대표적.

**수정 제안** 바인드 파라미터 타입을 컬럼과 일치. 스키마 확인 후 정정.

---

## 5. `leading_wildcard_like` - 선행 와일드카드 LIKE / 기본 🟡 warn

**탐지 신호** `LIKE '%...'` 또는 `LIKE '%...%'`, `CONTAINING`, 바인드가 앞에 `%`가 붙는 형태.

**왜 문제인가** 선행 `%`는 B-Tree 인덱스 레인지를 못 써 풀스캔.

**수정 제안** 접두 검색(`LIKE 'abc%'`)로 바꿀 수 있는지 검토, 전문 검색이 필요하면 FULLTEXT/전용 검색엔진(방언별). 후행 와일드카드만이면 인덱스 사용 가능함을 안내.

---

## 6. `unbounded_result` - 페이징/제한 없는 대량 조회 / 기본 🟡 warn

**탐지 신호** `LIMIT`/`FETCH FIRST`/`ROWNUM`/`Pageable`/`TOP` 없이 큰 테이블을 조회, `findAll()`류, 스트리밍 없는 전량 로딩.

**왜 문제인가** 결과 폭증 시 메모리/네트워크/GC 압박, OOM 위험.

**수정 제안** 페이지네이션 도입, 커서/키셋 페이징, 스트리밍/청크 처리. 진짜 소량이 보장되면 info로.

> **MySQL 관용구 주의:** `LIMIT 18446744073709551615`(BIGINT UNSIGNED 최대)는 **파생 테이블/뷰의 `ORDER BY`를 유지**하려는 의도적 관용구다(실질 상한 없음). 파생 테이블 내부의 이 패턴은 `unbounded_result`로 단정하지 말고 info/제외로 보되, **최상위 쿼리**에서 쓰이면 사실상 무제한이므로 경고한다.

---

## 7. `large_in_clause` - 미제한 대량 `IN (...)` 바인딩 / 기본 ⚪ info

**탐지 신호** 크기 제한 없는 컬렉션을 `IN`에 바인딩(`WHERE id IN (:ids)`)해 파라미터 수가 수천 이상이 될 수 있는 경로.

**왜 문제인가** 파싱/플랜 캐시 오염, 일부 드라이버/방언의 파라미터 상한 초과(Oracle 1000 등), 실행계획 악화.

**수정 제안** 청크 분할, 임시 테이블/조인, 값 목록을 파생 테이블로.

---

## 8. `deep_pagination` - 깊은 OFFSET 페이징 / 기본 ⚪ info

**탐지 신호** 큰 `OFFSET`(`LIMIT ? OFFSET 100000`)이나 페이지 번호가 커질 수 있는 오프셋 기반 페이징.

**왜 문제인가** OFFSET은 앞의 행을 세어 버리므로 뒤 페이지로 갈수록 느려진다.

**수정 제안** 키셋(seek) 페이징: `WHERE id < :lastId ORDER BY id DESC LIMIT ?`.

---

## 9. `order_by_filesort` - 인덱스 없는 정렬 / 기본 ⚪ info (Tier2에서 승격 가능)

**탐지 신호** `ORDER BY`(+`LIMIT`) 컬럼이 인덱스로 뒷받침되지 않을 가능성. Tier1은 "정렬 존재 + 페이징"을 신호로만 표기, 인덱스 확인은 Tier2.

**왜 문제인가** filesort/정렬 임시버퍼 발생, 특히 대량+LIMIT 조합에서.

**수정 제안** 정렬 컬럼을 포함한 (복합)인덱스, WHERE와 ORDER BY를 함께 만족하는 인덱스 설계.

---

## 10. `distinct_abuse` - 불필요한 DISTINCT / 기본 ⚪ info

**탐지 신호** 조인 폭증을 감추려는 `DISTINCT`, GROUP BY로 대체 가능한 DISTINCT.

**왜 문제인가** 중복 제거를 위한 정렬/해시 비용. 대개 잘못된 조인의 증상.

**수정 제안** 조인 카디널리티를 바로잡거나 `EXISTS`로 치환. 정말 필요한 경우만 유지.

---

## 11. `correlated_subquery` - 상관 서브쿼리 / 기본 ⚪ info

**탐지 신호** SELECT/WHERE 안에서 외부 행마다 재평가되는 서브쿼리(`WHERE EXISTS (... o.id = outer.id)`가 행마다), 스칼라 서브쿼리를 SELECT 목록에서 반복.

**왜 문제인가** 외부 N행 x 내부 실행 = N+1과 유사한 비용(방언 옵티마이저가 못 펴면).

**수정 제안** 조인/파생 테이블/윈도우 함수로 치환. 방언 옵티마이저의 세미조인 최적화 여부 확인.

---

## 12. `cartesian_join` - 카티전 곱/조인 조건 누락 / 기본 🔴 critical

**탐지 신호** `FROM a, b`에 조인 조건 누락, `CROSS JOIN` 의도치 않음, 다중 `collection` 조인으로 행 곱셈.

**왜 문제인가** 결과 행이 곱으로 폭증 -> 심각한 성능/메모리 사고.

**수정 제안** 명시적 `JOIN ... ON`, 조인 키 확인. MyBatis 다중 `<collection>` 조인은 별도 조회로 분리.

---

## 13. `or_predicate_index` - OR 조건 인덱스 저해 / 기본 ⚪ info

**탐지 신호** 서로 다른 컬럼을 잇는 `OR`(`WHERE a = ? OR b = ?`), `OR`로 인해 단일 인덱스 레인지가 깨지는 형태.

**왜 문제인가** 옵티마이저가 인덱스 병합에 실패하면 풀스캔.

**수정 제안** `UNION ALL`로 분해, 각 조건에 인덱스, 또는 조건 재설계.

---

## 14. `count_large` - 대량 COUNT/전량 집계 / 기본 ⚪ info

**탐지 신호** 페이징 총계용 `COUNT(*)`를 매 요청마다 대형 테이블에 수행, 필터 없는 전량 집계.

**왜 문제인가** 대형 테이블 COUNT는 비싸다(특히 필터 없거나 비-커버링).

**수정 제안** 근사 카운트/캐시, "다음 페이지 존재 여부만" 확인(LIMIT+1), 커버링 인덱스.

---

## 15. `transaction_lock_scope` - 트랜잭션/락 범위 과다 / 기본 ⚪ info

**탐지 신호** 트랜잭션 안에서 외부 호출(HTTP/메시지)/장시간 루프, 넓은 범위의 `SELECT ... FOR UPDATE`, 갱신 대상보다 넓은 잠금.

**왜 문제인가** 락 보유 시간^ -> 경합/데드락/처리량 저하.

**수정 제안** 트랜잭션 축소, 외부 호출을 트랜잭션 밖으로, 잠금 범위/행 최소화. (가능한 범위에서만 정적 판단)

---

## 16. `write_in_loop` - 루프 내 행별 쓰기 / 기본 🟡 warn

**탐지 신호** 루프에서 행별 `save()`/`create()`/`.add()`(M2M)/`delete()` 반복. ORM/서비스 코드의 "목록을 돌며 한 건씩 저장".

**왜 문제인가** INSERT/UPDATE가 N회 왕복 -> 네트워크/락/트랜잭션 비용이 건수에 비례(쓰기 N+1). 반복형 심각도 매트릭스를 따른다.

**수정 제안** `bulk_create`/`bulk_update`/`.set()`(M2M)/배치 INSERT, 또는 단일 `UPDATE ... WHERE`로 집합 처리.

---

## 17. `lost_update` - 읽기-수정-쓰기 경쟁 / 기본 🟡 warn / **정확성**

**탐지 신호** 값을 읽어 파이썬에서 계산한 뒤 **전체 행을 `save()`**(카운터/잔액/집계 누적), stale 인스턴스를 전체 컬럼 저장.

**왜 문제인가** 동시 실행 시 다른 트랜잭션의 갱신을 덮어써 **갱신 유실(lost update)** - 성능이 아니라 데이터 정확성 문제.

**수정 제안** 읽어서 더하지 말고 DB 식으로 원자적 갱신한다. Django: `F()` 식 `update(count=F('count')+1)`, `save(update_fields=[...])`로 갱신 컬럼 한정. SQLAlchemy: `update(Model).values(count=Model.count + 1)`(Core/2.0) 또는 `with_for_update()`로 행 잠금. 공통: `select_for_update`/행 잠금으로 읽기-수정-쓰기 구간 보호.

---

## 18. `duplicate_query` - 동일 쿼리 반복 / 기본 ⚪ info

**탐지 신호** 한 요청/단위 작업에서 같은 쿼리를 여러 번 실행(메모이제이션/요청 캐시 부재, 같은 `get()` 반복, 매 호출 재조회).

**왜 문제인가** 동일 결과를 중복 왕복해 불필요한 부하. N+1과 달리 "같은" 쿼리의 반복이다.

**수정 제안** 결과를 한 번 조회해 재사용, 요청 범위 메모이제이션/캐시, `cached_property`.

---

## 19. `stale_queryset_cache` - 모듈/클래스 레벨 QuerySet 캐시 / 기본 🟡 warn

**탐지 신호** 모듈/클래스 속성에 **평가된** QuerySet/리스트를 보관(import/정의 시점 1회 평가), 전역 상수로 조회 결과 고정.

**왜 문제인가** 결과가 고정(stale)되어 이후 변경을 반영하지 못하고, 프로세스 수명 동안 메모리를 점유하며, 워커 간 값이 불일치한다.

**수정 제안** 호출 시점에 쿼리를 생성(lazy 유지), 상수에는 QuerySet 자체가 아니라 생성 함수/lazy를 두고, 캐시가 필요하면 명시적 TTL 캐시를 쓴다.

---

## 20. `query_correctness` - 쿼리 정확성(결과가 틀림) / 기본 🔴 critical / **정확성**

**탐지 신호** 성능이 아니라 **결과 자체가 틀리는** 쿼리: 잘못된 바인드(리스트를 단일 문자열로 바인딩, 타입 불일치로 0건 매칭), 집계와 조인 팬아웃이 겹쳐 `COUNT`/`SUM`이 부풀거나 줄어듦, `GROUP BY` 누락/오지정. (성능상 인덱스 미사용인 타입 불일치는 `implicit_type_cast`, 여기서는 **결과가 틀리는** 경우.)

**왜 문제인가** 성능 이전에 데이터가 틀린다 - 조용히 잘못된 값을 반환하므로 가장 늦게 발견된다.

**수정 제안** 바인드 타입/구조를 컬럼과 구조에 맞게 교정, 집계는 팬아웃을 분리(`Subquery`/별도 집계 후 조인), 필요한 `GROUP BY`를 명시. 실 SQL과 샘플 데이터로 결과를 검증하도록 안내.

---

## 21. `scope_filter_bypass` - 권한/범위 필터 누락·무력화 / 기본 🔴 critical / **보안**

**탐지 신호** 사용자/테넌트/그룹 스코프 필터가 쿼리에서 누락되거나 무력화되는 경우: SQLAlchemy `.any()`/`.has()`가 소유 엔티티 미조인으로 **비상관 EXISTS**가 되어 전건 통과(`python-sqlalchemy.md` "조인 없이 타 엔티티 참조"), 멀티테넌트 쿼리에 `tenant_id`/`owner_id` 조건 누락, 권한 체크를 애플리케이션 레벨로만 미룬 전건 조회.

**왜 문제인가** 성능이 아니라 **접근 통제 결함** - 다른 사용자/테넌트의 데이터가 노출되거나 권한 필터가 전건 통과된다. `query_correctness`의 보안 특화 형태로, 조용히 잘못된 범위를 반환한다.

**수정 제안** 스코프 조건을 조인과 함께 상관시킨다(`select(X).join(Owner).where(Owner.scope.any(...))`), 테넌트/소유자 필터를 쿼리 레벨에 강제(기본 필터/세션 스코프), 권한을 DB 조건으로 표현. 실 SQL로 필터가 실제 적용되는지 확인한다.

---

## 22. `tx_not_participating` - 쓰기 트랜잭션 미참여 / 기본 🔴 critical / **원자성**

쓰기 경로(DAO 래퍼/`JdbcTemplate`/수동 `EntityManager`/Spring Batch step)가 **주 트랜잭션과 다른 커넥션/트랜잭션 매니저**를 써서, 다단계 갱신이 하나의 트랜잭션으로 묶이지 않는 경우. (구 `out_of_catalog`에서 승격.)

**탐지 신호**
- 쓰기 래퍼가 `@Transactional`과 다른 `DataSource`로 생성됨(별도 `JdbcTemplate` 빈 등).
- **Spring Batch:** step 트랜잭션 매니저(`BatchConfigurer`/`StepBuilder`)와 업무 리포지토리/매퍼의 트랜잭션 매니저가 **다른 리소스**(DataSource/EMF)를 가리킴 - 청크 커밋과 업무 쓰기가 별도 트랜잭션.
- 수동 `EntityManager`/`getTransaction()`을 선언적 트랜잭션과 섞어 씀.

**왜 문제인가** 다단계 갱신이 부분 커밋되고 실패 시 롤백되지 않는다 - 성능이 아니라 원자성/정확성.

**수정 제안** 쓰기 경로를 주 트랜잭션 매니저/`DataSource`에 통일. Spring Batch는 step 트랜잭션 매니저와 업무 트랜잭션 매니저의 리소스를 일치시키거나 업무 쓰기를 chunk 트랜잭션에 참여시킨다. 롤백 회귀 테스트로 확인.

---

## 23. `replica_routing_defect` - read replica 라우팅 결함 / 기본 🔴 critical(정확성) 또는 🟡 warn / **정확성/성능**

읽기/쓰기 DataSource 라우팅(`AbstractRoutingDataSource`/replica 분리)이 의도대로 동작하지 않는 경우. (구 `out_of_catalog`에서 승격.)

**탐지 신호**
- replica/master 빈 이름 충돌(같은 이름)로 모든 조회가 한쪽으로 감.
- `@Transactional(readOnly=true)` 부재로 라우팅이 master로 고정.
- 쓰기 직후 같은 요청에서 replica를 읽어 **복제 지연으로 stale** 데이터.

**왜 문제인가** master 과부하(성능) 또는 복제 지연으로 방금 쓴 데이터를 못 읽음(정확성). 의도(복제 지연 회피용 master 읽기)일 수 있으니 확인 후 심각도 조정.

**수정 제안** 라우팅 빈 이름/키 교정, 읽기 전용 트랜잭션 표기, 쓰기 직후 읽기는 master 강제 또는 지연 허용 설계.

---

## 24. `connection_abandon` - 커넥션 강제 회수(풀 abandon) / 기본 🟡 warn / **안정성**

커넥션 풀(DBCP2 등)의 `removeAbandoned`/타임아웃 설정이 장시간 쿼리/배치를 **실행 중에 강제 회수**할 수 있는 경우. (구 `out_of_catalog`에서 승격.)

**탐지 신호** `removeAbandonedOnBorrow`/`removeAbandonedTimeout`이 배치/장시간 작업의 쿼리 소요보다 짧게 설정됨.

**왜 문제인가** 실행 중 커넥션이 회수되면 쿼리 실패/트랜잭션 중단. 배치에서 특히 위험.

**수정 제안** 장시간 작업 전용 풀/타임아웃 상향, 또는 abandon 설정 재검토. 실제 60초+ 쿼리 존재 여부 측정 권장.

---

## 25. `paging_on_mutating_set` - 처리로 줄어드는 대상의 OFFSET 페이징 / 기본 🔴 critical / **정확성**

리더가 **WHERE/HAVING 조건으로 대상을 뽑는데, 같은 처리(writer/프로세서)가 그 조건 컬럼을 갱신**해 대상 집합이 줄고, 동시에 **OFFSET 기반 페이징**으로 읽어 **행이 건너뛰어져 누락**되는 경우. Spring Batch 리더/프로세서 구조에서 흔하다.

**탐지 신호** 리더 쿼리의 WHERE/HAVING 조건 컬럼을 같은 step의 writer가 갱신(처리 후 대상에서 빠짐) + chunk 단위 커밋 + `LIMIT ? OFFSET ?` 페이지 증가. 한 step은 이를 피하고(첫 read에서 전체 확보) 다른 step은 못 피하는 혼재도 신호.

**왜 문제인가** 처리된 행이 대상에서 빠지면서 뒤 페이지 OFFSET이 밀려 **중간 행이 조용히 누락**된다 - 성능이 아니라 데이터 정확성(일부 대상 미처리).

**수정 제안** OFFSET 페이징 대신 **키셋/커서**, 또는 **첫 read에서 전체 대상 확보 후 처리**(대상 규모가 작을 때), 또는 처리 상태 플래그로 대상을 고정해 재조회하지 않는다.

---

## 26. `random_clustered_pk` - 랜덤/UUID 클러스터드 PK / 기본 🟡 warn / **쓰기 성능**(방언 의존)

클러스터드 인덱스(InnoDB 등)에서 **PK가 단조 증가하지 않는 랜덤 값**(UUIDv4, 랜덤 바이트, 해시)이라, 삽입이 인덱스 중간중간에 일어나 **페이지 분할/단편화/버퍼풀 비효율**을 유발하는 경우. **"인조키(surrogate key) 자체"가 아니라 "랜덤 값을 클러스터드 PK로" 쓰는 것이 문제**다 - `AUTO_INCREMENT`/시퀀스 같은 단조 증가 surrogate PK는 오히려 권장 사례이므로 **지적 대상이 아니다**(오탐 금지).

> **중요(오탐 방지):** 이 ID는 **PK가 랜덤/UUID인 경우에만** 쓴다. 단조 증가 정수 PK(`seq`/`auto_increment`/IDENTITY)나, "자연키 대신 surrogate를 썼다" 같은 설계 선택은 **보고하지 않는다**(자연키의 유일성/불변성은 코드로 알 수 없어 판정 불가). 또한 클러스터드 인덱스가 없는 방언(PostgreSQL은 힙 테이블이라 PK가 클러스터드 아님)에서는 **해당 없음 또는 info로 크게 낮춘다**.

**탐지 신호**
- PK 컬럼 타입이 `UUID`/`CHAR(36)`/`BINARY(16)`/`VARCHAR`로, 값 생성이 `UUID()`/`uuid4()`/`randomUUID()`/`GenerationType.UUID`/앱단 랜덤이고, 그 컬럼이 **PRIMARY KEY**(= InnoDB 클러스터드).
- JPA `@Id @GeneratedValue(strategy = UUID)` 또는 `@GeneratedValue` 없이 앱에서 `UUID.randomUUID()`를 PK에 대입.

**왜 문제인가** InnoDB는 PK가 클러스터드 인덱스라 **행이 PK 순서로 물리 저장**된다. 랜덤 PK는 삽입 위치가 매번 달라 페이지 분할·단편화가 커지고, 모든 보조 인덱스가 PK를 포함하므로 **넓은 PK(UUID 16~36B)가 보조 인덱스까지 비대화**시킨다. (PostgreSQL은 힙 저장이라 영향이 작다 - 방언 노트 참조.)

**수정 제안**
- **단조 증가 PK로 전환**: `BIGINT AUTO_INCREMENT`를 PK로 두고, UUID가 외부 노출/분산 생성 때문에 필요하면 **UNIQUE 보조 컬럼**으로 유지(클러스터드에서 분리).
- UUID를 꼭 PK로 써야 하면 **시간 정렬 UUID**(UUIDv7/ULID)로 단조성을 확보하거나, MySQL이면 `BINARY(16)` + 바이트 재배열(`UUID_TO_BIN(uuid, 1)`)로 시간 접두를 앞세운다.
- 방언별 세부는 `dialects/<dialect>.md`.

---

## ~ `out_of_catalog` - 카탈로그 외 항목(메타) / 심각도 규칙 기반 / **발견 성격에 따름**

이 카탈로그의 명명된 ID 어디에도 들어맞지 않는 결함을 담는 **메타 항목**이다. 실제 리뷰에서 가장 중대한 결함이 여기 해당하는 경우가 있으므로(쓰기 트랜잭션 미참여, 커넥션 라우팅 결함 등), **"카탈로그에 없음"을 "경미함"으로 취급하지 않는다.**

**심각도 규칙** (ID 고정 기본값이 없으므로 발견의 성격으로 정한다)
- **정확성/원자성/보안을 깨는 결함 -> 🔴 critical** (예: 다단계 갱신의 원자성 부재, 권한 우회, 데이터 유실).
- **성능 저하 -> 🟡 warn**.
- **그 외(관측성/일관성/코드 위생) -> ⚪ info**.

**리포트 표기** ID는 `out_of_catalog`로 적되, **이름(name)에 구체 패턴을 병기**한다(예: "카탈로그 외 항목(`out_of_catalog`) - 쓰기 트랜잭션 미참여"). 근거/수정 제안/신뢰도 라벨은 다른 항목과 동일하게 채운다.

**정식 ID로 승격된 패턴** (아래는 더 이상 `out_of_catalog`가 아니라 전용 ID로 보고한다):
- 쓰기 트랜잭션 미참여 -> **`tx_not_participating`**(22)
- read replica 라우팅 결함 -> **`replica_routing_defect`**(23)
- 커넥션 강제 회수(풀 abandon) -> **`connection_abandon`**(24)

**아직 `out_of_catalog`로 남는 패턴** (빈도가 높아지면 승격 검토):
| 패턴 | 전형적 심각도 | 신호 |
|---|---|---|
| 트랜잭션 없는 복합 쓰기 | 🔴 critical(원자성) | 연관된 INSERT/UPDATE가 트랜잭션 경계 밖에서 실행(위 `tx_not_participating`에 해당하면 그 ID로) |
| 커넥션/세션 과다 획득 | 🟡 warn | 행마다 외부 에이전트/키 초기화, 매 요청 세션 SELECT+UPDATE |
| 관측성/위생 | ⚪ info | 로그에 SQL/자격증명 노출, 결과에 안 쓰는 불필요 LEFT JOIN 등(성격별 심각도 규칙) |

---

## 리포트에 남길 공통 항목

각 탐지 이슈마다:
- **ID / 심각도 / 신뢰도 라벨**(EXACT/INFERRED/AMBIGUOUS)
- **원천** `파일:라인` (+ 어느 코드/태그에서 왔는지)
- **추론 SQL** (있으면; 신뢰도 라벨 포함)
- **근거** (왜 문제로 판단했는지, 어떤 신호를 봤는지)
- **수정 제안** (구체적 코드/인덱스; Tier2/3면 근거 데이터 첨부)
- **검증 방법** (예: Hibernate `show_sql`로 실제 SQL 확인, EXPLAIN 재확인)

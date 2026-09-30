# SQL 방언(dialect) 노트: Oracle (🔶 스텁 - M2+ 확장)

`dialect: auto`가 Oracle로 판정하거나 `--dialect oracle`일 때 참고한다. MVP에서는 요지만 사용하고, 정밀 규칙은 M2 이후 확장한다.

## 방언 특성
- 식별자 인용: 큰따옴표(기본 대문자 폴딩). 자동증가: `SEQUENCE` + `.NEXTVAL` 또는 `GENERATED ... AS IDENTITY`(12c+).
- 페이징: 구버전 `ROWNUM`(서브쿼리 래핑), 12c+ `OFFSET m ROWS FETCH FIRST n ROWS ONLY`.
- 함수: `SYSDATE`, `NVL()`/`NVL2()`/`COALESCE`, `DECODE`, `TO_DATE`/`TO_CHAR`, `DUAL` 더미 테이블.
- 계층 쿼리: `CONNECT BY ... START WITH`.
- 타입: `VARCHAR2`, `NUMBER`, `CLOB`.

## 실행계획 (Tier3, M3)
- `EXPLAIN PLAN FOR ...` + `DBMS_XPLAN.DISPLAY`, 또는 `DBMS_XPLAN.DISPLAY_CURSOR`.
- 접근: **FULL TABLE SCAN**(경고) / **INDEX RANGE/UNIQUE SCAN** / **INDEX FAST FULL SCAN**.
- 조인: NESTED LOOPS / HASH JOIN / MERGE JOIN.
- 지표: `Cost`, `Cardinality(Rows)`, `Bytes`, 실제치는 `GATHER_PLAN_STATISTICS` 힌트 + DISPLAY_CURSOR.

## Oracle 특유 주의 (M2+)
- **바인드 필킹(bind peeking)/적응형 커서** - 같은 SQL도 바인드 값에 따라 계획 달라짐. 추론 SQL 판정 시 감안.
- **`IN` 표현식 리스트 1000개 상한** - **리터럴/표현식 목록**(`IN (a, b, ...)`)에만 적용되는 하드 에러(ORA-01795). **서브쿼리 `IN (SELECT ...)`나 바인드 배열/컬렉션에는 상한이 없다.** 또 **23c부터는 상한이 65535로 확대**됐다. 따라서 리스트형 `large_in_clause`만 승격하고 서브쿼리형은 승격하지 않는다.
- 함수 기반 인덱스(FBI)로 `non_sargable_predicate` 대응 가능.
- 힌트: `/*+ INDEX(t idx) */`, `/*+ LEADING(...) */` 등 - 근거와 함께 제안.

## 안티패턴 대응 요지
- `large_in_clause`: **표현식 리스트 1000개 초과 시 ORA-01795**(23c는 65535) -> 분할/조인. 단 서브쿼리 `IN (SELECT ...)`는 상한 없음(승격 제외).
- `non_sargable_predicate`: FBI(function-based index)로 해결 가능.
- `deep_pagination`: 12c+ `FETCH FIRST` 또는 키셋.

> M2에서 DBMS_XPLAN 해석/FBI 제안/바인드 필킹 영향을 완전 규칙으로 확장.

<!--
인벤토리 리포트 템플릿 - query-inspector `inventory-report` 스킬 모드.
SKILL.md의 "인벤토리 모드" 절차가 이 템플릿의 {{...}} 자리를 채워 두 곳에 출력한다:
  1) 터미널 요약(유형/테이블별 쿼리 수 + 상위 목록)
  2) 상세 파일 <report.dir>/inventory-reports/inventory-<timestamp>.md (이 템플릿 전체)
이 리포트는 **목록화 전용**이다 - 안티패턴 심각도/실행 계획(Action Items)/follow-up은 넣지 않는다.
스키마(엔티티/마이그레이션/DDL 자동 감지 또는 --db)가 없으면 "인덱스 커버"는 ❓ 스키마 미확인으로 남기고
목적/대상 테이블/본문은 그대로 채운다. baseline/open_suggestions 등 state.json은 갱신하지 않는다.
* 쿼리 본문(전문)은 필수다 - 쿼리 개수가 많아도 생략/요약/"대표만" 금지. 많으면 요약하지 말고
  점진 배치(도메인 단위)로 쪼개 --continue로 이어서, 결국 모든 쿼리의 본문 전문이 리포트에 남게 한다.
출력 언어는 report.language(auto=사용자 언어)로 렌더한다. 산문(목적/용도)은 지역화하되,
식별자(어댑터명/신뢰도 라벨/SQL/컬럼/테이블명)는 언어 중립으로 유지한다. -> references/i18n.md
-->
# Query Inventory - {{timestamp}}

- **스킬 버전:** query-inspector {{skill_version}}   <!-- version_check.py --local 로 확인 -->
- **범위:** {{range}}   /   **언어:** {{report_language}}
- **방언(dialect):** {{dialect}} ({{dialect_evidence}})
- **스키마 소스:** {{schema_source}}   <!-- LIVE-SCHEMA | SCHEMA-CONFIRMED | SCHEMA-PARTIAL | 없음 -> 인덱스 커버 판정 가능 여부 -->
- **쿼리 수:** {{query_count}}  ( SELECT {{n_select}} / INSERT {{n_insert}} / UPDATE {{n_update}} / DELETE {{n_delete}} / DDL {{n_ddl}} )
- **신뢰도:** EXACT {{n_exact}} / INFERRED {{n_inferred}} / AMBIGUOUS {{n_ambiguous}}
{{scan_progress_line}}  <!-- 점진 배치 사용 시: "진행: 도메인 3/7 (--continue 로 이어서)". 아니면 생략. -->

> 이 리포트는 프로젝트 쿼리의 **목록(인벤토리)** 입니다 - 안티패턴 튜닝 분석은 포함하지 않습니다. 튜닝하려면 `inventory-report` 스킬 없이 실행하세요.

---

## 요약 (테이블별)

| 테이블(+스키마) | 쿼리 수 | 유형 분포 | 인덱스 미커버 |
|---|---|---|---|
{{summary_rows}}
<!-- 예: | member (member_db) | 8 | SELECT 6 / UPDATE 2 | 1 (❌) |
     "인덱스 미커버"는 스키마를 알 때만 채우고, 모르면 ❓로 둔다. 테이블을 특정 못한 동적 쿼리는 마지막에 (미확정) 행으로. -->

---

## 쿼리 목록

<!-- 도메인(최상위 패키지/디렉토리)별로 그룹핑하고, 각 쿼리마다 아래 블록을 반복한다. -->
### 도메인: {{domain_name}}

#### [{{qid}}] {{purpose}}
- **원천:** `{{source_ref}}` - {{source_snippet}}   <!-- 파일:라인 + 메서드/매퍼 id -->
- **최종 수정자:** {{last_author}}   <!-- git blame(blame_author.py). "이름 (YYYY-MM-DD)", 미커밋은 "미커밋(작업 중)". git 정보 없으면 생략 -->
- **어댑터:** {{adapter}} / **유형:** {{op_type}} / **신뢰도:** {{confidence_label}}
- **대상:** {{tables}}   <!-- 테이블(+ 알 수 있으면 schema/DB). 여러 개면 모두. -->
- **접근 컬럼:** {{access_columns}}   <!-- WHERE ... / JOIN ... / ORDER BY ... (없으면 생략) -->
- **인덱스 커버:** {{index_coverage}}   <!-- ✅ <인덱스> | ❌ 미커버 | ❓ 스키마 미확인 -->
- **쿼리 본문(전문/필수):**
  ```sql
  {{query_body}}
  ```
<!-- query_body는 필수 - 쿼리 SQL **전문**을 기재한다. 개수가 많아도 생략/요약/"..." 축약 금지.
     동적 쿼리(MyBatis <if>/QueryDSL/Kotlin JDSL 등)는 대표 시나리오 2~3개를 각각 코드블록으로(전문),
     라벨을 AMBIGUOUS로 둔다. 목적/용도가 불확실하면 "추정: ..."으로 명시한다. -->


---

## 커버리지 & 한계

- **분석된 어댑터:** {{adapters_used}}   <!-- 예: mybatis(완전), native-sql(완전), jpa(추론), migration -->
- **인덱스 커버 판정:** {{index_judgement_note}}   <!-- 스키마 소스가 없으면 "스키마 미제공 -> 인덱스 커버는 ❓, 목적/테이블/본문만 확정". --db/스키마 지정 시 확정됨을 안내. -->
- **추론 한계:** ORM(jpa)/동적 쿼리는 실 SQL을 Hibernate/런타임이 생성하므로 라벨이 `INFERRED`/`AMBIGUOUS`입니다. 실제 SQL은 `show_sql`/`org.hibernate.SQL`로 확인하세요.
- **범위:** 이 인벤토리는 **{{range}}** 를 대상으로 합니다. {{scope_note}}   <!-- 전체가 아니면 "나머지 도메인은 --continue 로 이어서 목록화" 등. -->

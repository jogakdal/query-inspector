<!--
리포트 템플릿 - query-inspector Stage 4.
SKILL.md 절차가 이 템플릿의 {{...}} 자리를 채워 두 곳에 출력한다:
  1) 터미널 요약(위험도순 상위 report.terminal_top_n)
  2) 상세 파일 docs/query-inspector/tuning-reports/<timestamp>.md (이 템플릿 전체)
없는 섹션(예: Tier3 미사용 시 EXPLAIN)은 생략하고, 강등 사유는 반드시 남긴다.
수정안은 "제안"이다 - 코드 자동 반영 금지(사용자 확인 후 별도 적용).
출력 언어는 report.language(auto=사용자 언어)로 렌더한다. 아래 산문(제목/근거/제안)은 지역화하되,
식별자(휴리스틱 ID/신뢰도 라벨/설정 키/SQL)는 언어 중립으로 유지한다. -> references/i18n.md
-->
# Query Tuning Report - {{timestamp}}

- **스킬 버전:** query-inspector {{skill_version}}   <!-- version_check.py --local 로 확인 -->
- **범위:** {{range}}   /   **깊이:** {{depth_used}}{{depth_downgrade_note}}   /   **언어:** {{report_language}}
- **방언(dialect):** {{dialect}} ({{dialect_evidence}})
- **대상:** 파일 {{file_count}} / 추출 쿼리 {{query_count}} (EXACT {{n_exact}} / INFERRED {{n_inferred}} / AMBIGUOUS {{n_ambiguous}})   <!-- 쿼리 수/라벨 분포는 어댑터가 추출한 지점 기준 집계(추출은 LLM이 수행 - 스크립트 자동 카운트가 아님). 대형 프로젝트는 근사치로 표기하고 "약 N"처럼 명시한다 -->
- **심각도:** 🔴 critical {{n_critical}} / 🟡 warn {{n_warn}} / ⚪ info {{n_info}}
{{db_audit_line}}  <!-- Tier3 사용 시: "DB: dev(localhost) / EXPLAIN 3건 / ANALYZE 0건" 등 감사 로그 -->

> 이 리포트는 **제안**입니다. 코드는 자동 수정되지 않습니다. 반영하려면 해당 이슈 번호로 후속 요청하세요.

---

## 🔁 이전 제안 검증 (follow-up)

> 지난 튜닝(`{{last_report}}`, baseline `{{baseline}}`)의 제안이 반영됐는지 확인한다. **첫 실행이거나 `--all`(전체 재검토)이면 이 섹션은 생략**(처음부터 전체를 보는 실행이므로 이전 제안 검증을 하지 않는다).

{{followup_items}}
<!-- 형식:
     - ✅ 해결: <제안> - 근거(무엇이 반영됐는지: 인덱스 생성/EntityGraph 도입/CONCAT 전환 등)
     - ⚠️ 미반영(N회째): <제안> - `파일`/지문. -> 아래 실행 계획에 다시 포함.
     - ❓ 확인필요: <제안> - 정적 확증 불가(Tier3/수동 권장)
     미반영 항목은 반드시 아래 실행 계획에 다시 올린다. -->

---

## 요약 (위험도순)

| # | 심각도(기본->조정) | 이슈(ID) | 위치 | 최종 수정자 | 신뢰도 |
|---|--------|----------|------|------|--------|
{{summary_rows}}
<!-- 예: | 1 | 🔴 critical | N+1 (n_plus_one) | OrderService.kt:42 | Yongho Hwang(황용호) (2026-08-27) | INFERRED |
     최종 수정자는 git blame(blame_author.py) 기준. 미커밋은 "미커밋(작업 중)", git 정보 없으면 "-". -->
<!-- (이하 옛 예시 주석):
     맥락상 심각도를 조정했으면 "기본->조정"으로 표기: 예 `🔴 critical -> 🟡 warn`.
     조정 사유는 아래 상세의 "심각도" 필드에 적는다. severity_rules 기본값과 어긋나 보이지 않도록 항상 함께 표기. -->

---

## ✅ 실행 계획 (Action Items)

> 이 섹션만으로 바로 착수할 수 있게 정리한다. 개발자 또는 **개발자의 AI 에이전트에게 그대로 전달**할 수 있도록 대상 위치/변경 유형/복붙 가능한 코드/DDL을 담는다.
> 적용 라벨: **[자동적용]** 기계적 반영 안전 / **[검토후]** 설계 판단 필요 / **[확인후]** 전제 확인 뒤 적용

{{action_items}}
<!-- 심각도 그룹(### 🔴 이번 배포에 반드시 / ### 🟡 곧 / ### ⚪ 여유 될 때)으로 나누고, 각 항목 형식:
     - [ ] **[자동적용|검토후|확인후] <한 줄 지시>** - `파일:라인` (근거 #이슈번호)
           (적용 가능하면 복붙용 코드/DDL 블록 첨부)
     원칙: 이 목록은 "제안된 작업"이며 자동 반영하지 않는다. 적용은 사용자/AI가 수행. -->

---

## 상세

<!-- 이슈마다 아래 블록을 반복. 심각도 내림차순. 대규모 리포트(수십 건+)에서는 ⚪ info 항목을 전체 블록 대신 한 줄(ID/위치/한 줄 근거)로 묶어 축약할 수 있다 - 🔴 critical / 🟡 warn은 전체 블록을 유지한다. -->
### {{severity_icon}} [{{severity}}] {{issue_name}} - {{location}}  ({{confidence_label}})

- **ID:** `{{heuristic_id}}`
- **심각도:** {{severity}}{{severity_adjust}}   <!-- 맥락상 조정했으면: "🟡 warn (기본 🔴 critical -> 조정 사유: 결과 소량 보장/배치 1회성 등)". 조정 없으면 기본값만. -->
- **원천:** `{{source_ref}}` - {{source_snippet}}
- **수정 지점:** {{fix_site}}   <!-- 발현 위치(원천)와 다를 때만 채운다. 예: 템플릿에서 N+1이 발현하고 수정은 뷰 get_queryset. 여러 조회가 공유하는 인덱스면 '관련 위치'를 함께 적는다 -->
- **최종 수정자:** {{last_author}}   <!-- git blame(blame_author.py) 기준. 예: "Yongho Hwang(황용호) (2026-08-27)". 미커밋/새 파일이면 "미커밋(작업 중)". git 정보 없으면 이 줄 생략. 이메일은 기본 생략 -->
- **추론 SQL** ({{confidence_label}}):
  ```sql
  {{inferred_sql}}
  ```
- **근거:** {{rationale}}
- **검증 수준:** {{verification_level}}   <!-- 신뢰도 라벨과 별개로, 실제 어디까지 확인했는지: '컴파일 확인(str(qs.query))' / '쿼리 수 실측(N쿼리)' / 'EXPLAIN 실측' / '정적 추론(미실행)'. 라벨(EXACT/INFERRED/AMBIGUOUS)은 SQL 생성 주체를, 이 필드는 검증 여부를 나타낸다 -->
- **제안:** {{suggestion}}
  ```{{suggestion_lang}}
  {{suggestion_code}}
  ```
{{tier2_index_block}}
<!-- Tier2 인덱스 대조(missing_index). 채울 때 형식:
     - 인덱스 대조 근거: <스키마 소스> 확인 -> <table>(<cols>) 인덱스 없음  [SCHEMA-CONFIRMED | SCHEMA-PARTIAL]
     - 제안 인덱스: CREATE INDEX idx_<t>_<cols> ON <t> (a, b);   / 순서 근거: 등호->범위->정렬
     - 트레이드오프: 쓰기 비용 / 카디널리티 / 기존 인덱스 확장 가능 여부 -->
{{tier3_explain_block}} <!-- Tier3: EXPLAIN before/after 요약(type/key/rows/Extra 또는 노드), 감사 로그 -->
- **검증 방법:** {{verification_hint}}   <!-- 예: Hibernate show_sql로 실제 SQL 확인 / dev DB에서 EXPLAIN 재확인 -->

---

## 커버리지 & 한계

- **분석된 어댑터:** {{adapters_used}}   <!-- 예: mybatis(완전), native-sql(완전), jpa(추론) -->
- **강등/생략:** {{degradations}}        <!-- 예: "스키마 미제공 -> Tier1만", "dev DB 접속 실패 -> Tier2로 강등" -->
- **AMBIGUOUS 항목:** 동적 분기가 많아 대표 시나리오로 근사했습니다. 실제 SQL은 위 검증 방법으로 확인하세요.
- 이 리포트는 **변경분({{range}})** 만 대상으로 합니다. 변경되지 않은 기존 쿼리는 검토 범위 밖입니다.

<!-- 심각(critical) 이슈가 있으면 SKILL.md가 터미널 요약 끝에 `[query-inspector] critical=<N>`를 출력한다(훅/CI가 grep으로 감지하는 선택 신호). -->

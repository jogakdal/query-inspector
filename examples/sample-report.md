# Query Tuning Report - 2026-08-26 17:30 KST  / 2회차(증분)

- **범위:** 증분 - 마지막 튜닝(2026-08-26 15:00, `534cc70`) 이후 / **변경 파일 2**
- **깊이:** Tier2 (schema)   /   **방언(dialect):** mysql (`build.gradle`의 mysql-connector-j)   /   **스키마:** SCHEMA-CONFIRMED   /   **언어:** ko
- **대상:** 변경 파일 2 / 신규 검출 0 / **이전 제안 검증 8건**
- **심각도(미해결):** 🔴 3 / 🟡 2 / ⚪ 1   /   지난 제안 중 **✅ 2건 해결**

> 📌 **한 줄 요약:** 지난 튜닝에서 제안한 8건 중 **2건은 반영 완료(✅)**, **인덱스 누락 2건은 여전히 미반영(⚠️ 2회째)** 입니다. 이번 배포 전 아래 실행 계획 #1을 처리하세요.
>
> 이 리포트는 **제안**입니다. 코드는 자동 수정되지 않습니다.

---

## 🔁 이전 제안 검증 (follow-up)

> 지난 튜닝(`2026-08-26_1500.md`, baseline `534cc70`)의 제안이 반영됐는지 확인했습니다.

| 상태 | 제안(ID) | 위치 | 근거 |
|------|----------|------|------|
| ✅ 해결 | 전체 컬럼 조회 (`select_star`) | UserMapper.xml | `SELECT *` -> `SELECT id, name` 로 수정 확인 |
| ✅ 해결 | 방언 불일치 `\|\|` (`dialect_pipe_concat`) | UserRepository.kt | `\|\|` -> `CONCAT(...)` 전환 확인 |
| ⚠️ 미반영 (2회째) | **인덱스 누락 FK `orders.user_id`** (`missing_index`) | OrderMapper.xml | V2 이후 인덱스 마이그레이션 없음 |
| ⚠️ 미반영 (2회째) | **인덱스 누락 `orders(status, created_at)`** (`missing_index`) | OrderMapper.xml | 동일 - 인덱스 미생성 |
| ⚠️ 미반영 (2회째) | N+1 조회 (`n_plus_one`) | UserMapper.xml | `<collection select=...>` 중첩 select 그대로 |
| ⚠️ 미반영 (2회째) | 선행 와일드카드 LIKE (`leading_wildcard_like`) | UserRepository.kt | `CONCAT`으로 바꿨으나 선행 `%` 잔존 |
| ⚠️ 미반영 (2회째) | 조건 소실 -> 전체 조회 (`unbounded_result`) | UserMapper.xml | `ids==null` 분기 방어 없음 |
| ⚪ 미반영 (2회째) | 무제한 IN 바인딩 (`large_in_clause`) | UserMapper.xml | 크기 상한 없음(정보성) |

**미반영 6건은 아래 실행 계획에 다시 포함**했습니다. `missing_index` 2건은 **2회 연속 미반영**이라 최우선입니다.

---

## 요약 (이번 회차 / 위험도순)

> 증분 대상(변경 2파일)에서 새로 검출된 이슈는 없습니다. 아래는 **미반영으로 이월된** 이슈입니다.

| # | 심각도 | 이슈(ID) | 위치 | 상태 |
|---|--------|----------|------|------|
| 1 | 🔴 | 인덱스 누락 FK `orders.user_id` (`missing_index`) | OrderMapper.xml | 이월(2회째) |
| 2 | 🔴 | 인덱스 누락 `orders(status, created_at)` (`missing_index`) | OrderMapper.xml | 이월(2회째) |
| 3 | 🔴 | N+1 조회 (`n_plus_one`) | UserMapper.xml | 이월(2회째) |
| 4 | 🟡 | 선행 와일드카드 LIKE (`leading_wildcard_like`) | UserRepository.kt | 부분 진전 |
| 5 | 🟡 | 조건 소실 -> 전체 조회 (`unbounded_result`) | UserMapper.xml | 이월(2회째) |
| 6 | ⚪ | 무제한 IN 바인딩 (`large_in_clause`) | UserMapper.xml | 이월(2회째) |

---

## ✅ 실행 계획 (Action Items)

> 개발자 또는 **개발자의 AI 에이전트에게 그대로 전달**하세요.
> 라벨: **[자동적용]** 기계적 반영 안전 / **[검토후]** 설계 판단 필요 / **[확인후]** 전제 확인 뒤 적용

### 🔴 이번 배포에 반드시 (critical / 2회 연속 미반영 포함)

- [ ] **[자동적용] 인덱스 마이그레이션 추가** - 새 파일 `src/main/resources/db/migration/V3__orders_indexes.sql` (근거 #1, #2 / **2회째 리마인드**)
  ```sql
  CREATE INDEX idx_orders_user_id        ON orders (user_id);
  CREATE INDEX idx_orders_status_created ON orders (status, created_at);
  ```
- [ ] **[검토후] N+1 해소** - `UserMapper.xml`의 `<collection select="OrderMapper.findByUserId">`를 조인 결과 매핑 또는 `WHERE user_id IN (:userIds)` 배치로 (근거 #3). 위 `idx_orders_user_id`와 함께.

### 🟡 곧 (warn)

- [ ] **[검토후] 선행 와일드카드 완화** - `UserRepository.kt`. `CONCAT('%', ?, '%')`는 여전히 풀스캔 -> 접두 검색이면 `CONCAT(?, '%')`로 `idx_users_name` 활용, 부분일치 필수면 FULLTEXT (근거 #4).
- [ ] **[검토후] 전체 조회 방지** - `UserMapper.xml`. `ids==null` 시 전체 조회 -> null 방어 또는 `LIMIT` (근거 #5).

### ⚪ 여유 될 때 (info)

- [ ] **[검토후] IN 절 크기 상한** - `UserMapper.xml`. `<foreach>` IN 규모 커지면 청크 분할 (근거 #6).

---

## 상세 (미반영 이월 이슈)

### 🔴 [critical] 인덱스 누락 - FK `orders.user_id` - OrderMapper.xml (SCHEMA-CONFIRMED / 2회째)

- **ID:** `missing_index` / **인덱스 대조 근거:** `V2__orders.sql` 확인 -> `orders`에 PK(id)만, `user_id` 인덱스 없음.
- **왜 치명적:** `UserMapper`의 N+1 자식 쿼리(#3)라 user N명마다 `orders` 풀스캔.
- **제안:** `CREATE INDEX idx_orders_user_id ON orders (user_id);`
- **검증(Tier3, --db):** `EXPLAIN`에서 `type: ALL -> ref` 확인.

### 🔴 [critical] 인덱스 누락 - `orders(status, created_at)` - OrderMapper.xml (SCHEMA-CONFIRMED / 2회째)

- **ID:** `missing_index` / **추론 SQL:** `... WHERE status=? AND created_at>=? ORDER BY created_at DESC` -> 풀스캔 + filesort.
- **제안:** `CREATE INDEX idx_orders_status_created ON orders (status, created_at);`
  - 순서 근거(mysql): `status`(등호) -> `created_at`(범위+정렬) -> range와 `ORDER BY` 동시 커버(filesort 제거).
- **검증(Tier3):** `Extra`의 `Using filesort` 소거 확인.

### 🔴 [critical] N+1 조회 - UserMapper.xml (INFERRED / 2회째)

- `<collection ... select="OrderMapper.findByUserId">` 중첩 select -> user N건마다 orders 조회. **#1 미해결로 자식도 풀스캔.**
- **제안:** 조인 결과 매핑 또는 IN 배치 로딩.

### 🟡 [warn] 선행 와일드카드 LIKE - UserRepository.kt (EXACT / 부분 진전)

- 지난 회차 `||` 문제는 `CONCAT`으로 해결됐으나, `CONCAT('%', ?, '%')`는 여전히 선행 `%` -> `idx_users_name` 미사용.
- **제안:** 접두 검색 가능하면 `CONCAT(?, '%')`, 아니면 FULLTEXT.

---

## 커버리지 & 한계

- **범위:** 증분(마지막 튜닝 `534cc70` 이후 변경 2파일). **미반영 제안 검증은 변경 파일 밖의 이전 제안까지 상태로 추적**하므로, 손대지 않은 `OrderMapper.xml`의 인덱스 누락도 리마인드됩니다.
- **분석 어댑터:** `mybatis`(완전), `native-sql`(완전), `migration`(Tier2 인덱스 소스).
- **깊이:** Tier2(V1/V2 DDL 확인). Tier3(실 DB EXPLAIN)는 DB 미제공으로 강등 - `--db dev` 시 #1/#2 before/after 확증.
- **다음 baseline:** 이번 실행 HEAD로 상태가 갱신됩니다(`docs/query-inspector/tuning-reports/state.json`). 미반영 6건은 `open`으로 이월됩니다.

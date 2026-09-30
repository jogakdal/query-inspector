---
name: "Missing Index -> CREATE INDEX (간판 기능)"
description: "스키마에 필요한 인덱스가 없을 때 missing_index를 잡고 구체적 CREATE INDEX를 제안하는지"
tags: ["tier2", "missing-index", "mybatis", "flagship"]
plugins: ["query-inspector"]
runs: 3
max_turns: 20
timeout_seconds: 120
allowed_tools: ["Bash", "Read", "Grep", "Write"]
---

# 인덱스 누락 탐지 테스트

아래 변경분(staged)이 있는 MySQL(build.gradle의 mysql-connector-j) 프로젝트에서 `/query-inspector:tuning-report`를 실행하는 상황이다.

**마이그레이션 `V2__orders.sql` (신규) - 인덱스 없이 테이블 생성:**
```sql
CREATE TABLE orders (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  status VARCHAR(20) NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  created_at DATETIME NOT NULL
);
-- user_id / status / created_at 인덱스 없음
```

**`OrderMapper.xml` (신규):**
```xml
<select id="findRecentByStatus" resultType="Order">
  SELECT id, amount, created_at FROM orders
  WHERE status = #{status} AND created_at &gt;= #{from}
  ORDER BY created_at DESC
</select>
<select id="findByUserId" resultType="Order">
  SELECT id, user_id, status, amount, created_at FROM orders WHERE user_id = #{userId}
</select>
```

스킬이 만족해야 할 기준:
1. `orders(status, created_at)`와 `orders(user_id)`의 **인덱스 누락(missing_index)** 을 critical로 보고.
2. **구체적 `CREATE INDEX` DDL**을 제안(컬럼 순서: 등호 -> 범위/정렬).
3. 같은 변경분의 마이그레이션에 인덱스가 빠졌음을 지적.
4. `id`(PK)에는 인덱스 누락을 오탐하지 않음.

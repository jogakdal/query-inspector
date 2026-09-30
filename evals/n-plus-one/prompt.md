---
name: "N+1 Detection + Solution"
description: "MyBatis 중첩 select(또는 JPA LAZY)에서 N+1을 잡고 구체적 해결안을 제시하는지"
tags: ["tier1", "n-plus-one", "mybatis"]
plugins: ["query-inspector"]
runs: 3
max_turns: 15
timeout_seconds: 90
allowed_tools: ["Bash", "Read", "Grep", "Write"]
---

# N+1 탐지 테스트

아래 변경분에서 `/query-inspector:tuning-report`를 실행하는 상황이다.

**`UserMapper.xml` (신규):**
```xml
<resultMap id="userRM" type="User">
  <collection property="orders" ofType="Order" select="OrderMapper.findByUserId"/>
</resultMap>
<select id="search" resultMap="userRM">
  SELECT id, name FROM users
</select>
```

스킬이 만족해야 할 기준:
1. `<collection select=...>` **중첩 select**로 인한 **N+1(n_plus_one)** 을 critical/warn으로 보고.
2. 근거로 "중첩 select"(부모 N건마다 자식 조회)를 지목.
3. 해결안으로 **조인 결과 매핑** 또는 **`WHERE user_id IN (:ids)` 배치 로딩** 중 하나 이상을 구체적으로 제안.

---
type: llm
criteria: |
  리포트가 N+1에 대해 다음 중 하나 이상의 구체적 해결안을 제시하는가?
  - 조인 + 중첩 결과 매핑(<collection>에서 select= 제거)
  - OrderMapper에서 WHERE user_id IN (:userIds) 배치 로딩
  - (JPA라면) @EntityGraph / join fetch
focus: last_message
---

N+1을 "발견"만으로는 부족하다. 실제로 적용 가능한 구체적 수정 방향을 제시해야 통과한다.

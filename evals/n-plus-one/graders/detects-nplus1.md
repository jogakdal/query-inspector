---
type: regex
pattern: '(?i)(n_plus_one|n\+1|n plus one|중첩\s*select|nested select)'
match: contains
target: last_message
---

리포트에 N+1(`n_plus_one`/"N+1"/"중첩 select") 관련 지적이 포함되는지 확인한다.

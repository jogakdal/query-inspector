---
type: regex
pattern: '(?i)(missing_index|인덱스 누락|CREATE\s+INDEX)'
match: contains
target: last_message
---

리포트에 인덱스 누락(`missing_index`/"인덱스 누락") 또는 `CREATE INDEX` 제안이 포함되는지 확인한다.

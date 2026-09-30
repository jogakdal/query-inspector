---
type: llm
criteria: |
  리포트가 다음을 모두 만족하는가?
  1. orders(status, created_at) 복합 인덱스와 orders(user_id) FK 인덱스를 각각 CREATE INDEX DDL로 제안.
  2. 복합 인덱스의 컬럼 순서가 등호(status) -> 범위/정렬(created_at) 순으로 근거와 함께 제시됨.
  3. id(PK)에 대해서는 인덱스 누락을 주장하지 않음(오탐 없음).
focus: last_message
---

단순히 "인덱스가 필요하다"가 아니라, **컬럼과 순서가 명시된 실행 가능한 CREATE INDEX**를 제안해야 통과한다.
이 스킬의 간판 가치이므로 구체성이 핵심이다.

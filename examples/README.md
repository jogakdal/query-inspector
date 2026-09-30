# examples - 데모 fixture와 대표 리포트

`query-inspector`가 실제로 무엇을 검출하는지 보여주는 **재현 가능한 예시**다. 저장소에 커밋되는 데모/문서용이며, 향후 `claude plugin eval` fixture로도 재활용한다(DESIGN.md 12.2절).

> 참고: **실제 프로젝트에서 스킬을 돌리면 리포트는 `<프로젝트 루트>/docs/query-inspector/tuning-reports/<timestamp>.md`** 에 생성되고 그 경로는 `.gitignore` 대상이다(이력/캐시). 여기 `sample-report.md`는 그렇게 생성된 리포트를 **데모용으로 저장소에 보존**한 사본이다.

## 구성

- **`sample-project/`** - 의도적으로 안티패턴을 심은 최소 Kotlin+MyBatis 프로젝트.
  - `build.gradle` - `mysql-connector-j` 의존성(-> SQL 방언(dialect) 자동 감지가 `mysql`로 판정하는 근거).
  - `src/main/resources/mapper/UserMapper.xml` - `SELECT *`, 중첩 select(N+1), 동적 `<foreach>` IN.
  - `src/main/resources/mapper/OrderMapper.xml` - `user_id` 등호 조회, `status`+`created_at` 복합 조건+정렬.
  - `src/main/kotlin/UserRepository.kt` - 선행 와일드카드 `LIKE`, MySQL에서 잘못된 `||` 연산자.
  - `src/main/resources/db/migration/V1__init.sql`, `V2__orders.sql` - 스키마. **`orders`에 필요한 인덱스를 일부러 누락**(실무에서 흔한 "인덱스 없이 배포" 재현).
- **`sample-report.md`** - **2회차(증분 + 이전 제안 검증) 데모 리포트**(전사 데모용). 1회차에서 8건을 제안했고, 개발자가 `SELECT *`/`||`를 고친 뒤 재실행한 상황: ✅ 2건 해결, ⚠️ 인덱스 누락 등 6건 미반영(리마인드, "2회째"), 실행 계획에 `[자동적용]` 인덱스 DDL. 증분 대상은 변경 2파일이지만, 수정하지 않은 파일의 이전 제안도 상태로 추적하여 검증한다.

## 재현 방법

```bash
# 1) sample-project를 임시 git 저장소로 만들어 스테이징
cp -r examples/sample-project /tmp/dqt-demo && cd /tmp/dqt-demo
git init -q && git add -A

# 2) Stage0 수집 확인(스크립트 단독 실행 / Windows는 python 또는 py)
python3 /path/to/query-inspector/scripts/collect_diff.py

# 3) Claude Code에서 스킬 호출 -> 리포트가 docs/query-inspector/tuning-reports/ 에 생성됨
#    claude
#    > /query-inspector:tuning-report
```

## 탐지 이슈 목록

| 심각도 | 이슈(ID) | 위치 |
|--------|----------|------|
| 🔴 | 인덱스 누락 FK `orders.user_id` (`missing_index`) | OrderMapper.xml |
| 🔴 | 인덱스 누락 `orders(status, created_at)` (`missing_index`) | OrderMapper.xml |
| 🔴 | N+1 조회 (`n_plus_one`) | UserMapper.xml |
| 🔴 | 방언 불일치 `\|\|` (`dialect_pipe_concat`) | UserRepository.kt |
| 🟡 | 선행 와일드카드 LIKE / 조건 소실 / `SELECT *` | UserRepository.kt / UserMapper.xml |
| ⚪ | 무제한 IN 바인딩 (`large_in_clause`) | UserMapper.xml |

요점: **인덱스 누락 2건에 대해 구체적 `CREATE INDEX` DDL을 제안**하고, 같은 변경분의 마이그레이션에 인덱스가 빠졌음을 교차 지적한다.

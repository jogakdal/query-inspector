# tests - 회귀 테스트

## 철학: 결정적 검증 vs LLM 판정 검증

이 스킬의 추출/휴리스틱 판정은 **LLM(Claude)이 `SKILL.md` 절차로 수행**하므로 전통적 단위 테스트로 전부 자동화할 수 없다. 그래서 두 층으로 나눈다.

| 층 | 대상 | 방법 |
|----|------|------|
| **결정적(기계)** | `db_guard` 가드레일, `collect_diff` 파일 분류, 골든 파일 형식/fixture 존재 | `run_tests.sh` - CI에서 실행 |
| **LLM 판정** | 어댑터 추출, 휴리스틱 검출(`missing_index` 등), 인덱스 제안, 실행 계획 | `expected/*.yml` 골든을 **`claude plugin eval`(M4)** 또는 **수동 대조**로 |

## 구성

```
tests/
├── run_tests.sh              # 결정적 검증 러너(bash 3.2 호환)
├── fixtures/
│   └── jpa-sample/           # JPA 어댑터(M2) 검증용: 엔티티 + 리포지토리
│       ├── Order.kt
│       └── OrderRepository.kt
└── expected/                 # 선언적 골든(기대 판정)
    ├── sample-project.yml    # examples/sample-project(mybatis+native+migration)
    └── jpa-sample.yml        # fixtures/jpa-sample(jpa)
```

> mybatis/native-sql/migration 입력은 저장소의 **`examples/sample-project`** 를 재사용한다(중복 방지).

## 실행 (결정적 검증)

```bash
bash tests/run_tests.sh
```

검증 항목: (1) 가드레일 self-test, (2) `collect_diff` 분류(임시 git repo 생성), (3) 골든 파일 존재/YAML 파싱, (4) jpa fixture 존재.

## 골든 파일 형식 (`expected/*.yml`)

- `must_detect` - 반드시 검출될 `{id, at(파일), note}`. 누락 시 회귀.
- `must_suggest_index` - 반드시 제안될 인덱스(컬럼 집합/순서).
- `must_not` - 오탐 금지(있으면 회귀). 예: PK 컬럼에 `missing_index` 금지.
- `must_action` - 실행 계획에 있어야 할 액션(라벨/심각도).
- `must_translate`(jpa) - 파생 메서드 -> SQL 번역 기대.
- 라인 번호는 리팩터링에 취약하므로 **파일 단위로만** 고정한다.

## LLM 판정 대조(수동/eval)

1. fixture를 임시 git 저장소로 만들어 스테이징.
2. `/query-inspector:tuning-report` 실행 -> 생성된 리포트를 `expected/*.yml`과 대조.
3. `must_detect`가 모두 리포트에 나타나고, `must_not`이 없으며, `must_suggest_index`가 제안됐는지 확인.

## M4 - eval 스위트

`expected/*.yml`을 assertion으로 하는 `claude plugin eval` 케이스를 구성해 회귀를 자동화한다(DESIGN.md 12.2절). 그때 이 골든이 그대로 기대값 소스가 된다.

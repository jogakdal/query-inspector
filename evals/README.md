# evals - `claude plugin eval` 스위트 (골격)

품질 게이트. 스킬이 핵심 이슈를 회귀 없이 잡는지 `claude plugin eval`로 검증한다. `tests/expected/*.yml`의 선언적 골든을 eval 케이스의 판정 기준으로 옮긴 것이다.

## 구조

```
evals/
├── missing-index/          # * 간판 기능: 인덱스 누락 -> CREATE INDEX 제안
│   ├── prompt.md
│   └── graders/
│       ├── detects-missing-index.md   (regex)
│       └── suggests-create-index.md    (llm)
└── n-plus-one/             # N+1 탐지 + 해결안
    ├── prompt.md
    └── graders/
        ├── detects-nplus1.md          (regex)
        └── suggests-solution.md        (llm)
```

## 실행

```bash
cd /path/to/query-inspector
claude plugin eval ./                       # 전체
claude plugin eval ./ --case missing-index  # 특정 케이스
claude plugin eval ./ --json eval-results.json --threshold 0.85
claude plugin eval ./ --ablation with-without   # 플러그인 유무 비교
```

> ⚠️ eval 케이스 파일 형식(`prompt.md` 프론트매터, `graders/*.md`의 `type: regex|llm`)은 Claude Code의 `claude plugin eval` 스펙을 따른다. **실행 전 `claude plugin eval --help`로 현재 버전의 정확한 스키마/옵션을 확인**하고 필요 시 조정하라. 이 디렉토리는 골격이며, 케이스는 `tests/expected/*.yml` 골든을 기준으로 확장한다.

## 골든 연계

| eval 케이스 | 대응 골든(`tests/expected/`) |
|-------------|------------------------------|
| `missing-index` | `sample-project.yml`/`jpa-sample.yml`의 `must_detect: missing_index` + `must_suggest_index` |
| `n-plus-one` | `must_detect: n_plus_one` |

새 휴리스틱을 추가하면 골든과 eval 케이스를 함께 갱신한다.

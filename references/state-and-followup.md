# 증분 튜닝 & 이전 제안 검증 (상태 관리)

수동 스킬이지만 **마지막 튜닝 이후 변경분**만 대상으로 하고(누락 방지), **이전 제안이 반영됐는지 검증**하기 위해 프로젝트별 상태를 유지한다. `SKILL.md`의 Stage 0(대상 결정)/Stage 3.5(제안 검증)/Stage 4(상태 저장)가 이 문서를 따른다.

## 상태 파일

- 경로: `<report.dir>/tuning-reports/state.json` (기본 `docs/query-inspector/tuning-reports/state.json`).
- 저장 정책: **기본 로컬**(gitignore). 설정 `state.shared: true`면 커밋 대상(팀 공유).
- 스키마:

```json
{
  "version": 1,
  "last_tuned_commit": "<sha>",
  "last_tuned_dirty": false,
  "last_report": "docs/query-inspector/tuning-reports/2026-08-26_1500.md",
  "updated_at": "2026-08-26T15:00:00+09:00",
  "open_suggestions": [
    {
      "key": "missing_index|orders|user_id",
      "id": "missing_index",
      "file": "src/main/resources/mapper/OrderMapper.xml",
      "target": "orders(user_id)",
      "severity": "critical",
      "first_seen": "2026-08-26_1500",
      "seen_count": 1,
      "status": "open"
    }
  ]
}
```

## 대상 범위 결정 (Stage 0)

우선순위(위에서 먼저 매칭):
1. **명시 인자** `--range` / `--files` / `--staged` / `--all` -> 그대로 사용.
2. **기본 `--since-last`(증분):**
   - `state.json`의 `last_tuned_commit`을 baseline으로 읽는다(`collect_diff.py`가 파싱, jq/bash 불필요).
   - baseline이 **유효한 커밋**이면 -> `git diff <baseline>` = baseline 이후 **커밋분 + 미커밋(working/staged) 전부**.
   - baseline이 **없으면(첫 실행)** 또는 **무효**(rebase/squash로 사라짐)면 -> **자동으로 전체를 돌리지 않고 사용자에게 범위를 확인**한다(아래 "첫 실행 - 범위 확인").

> 요점: 첫 사용은 **사용자가 범위 선택**, 이후는 "마지막 튜닝 이후 변경분"(커밋 여부 무관).

### 첫 실행 - 범위 확인 (baseline 없음)

자동 전체는 큰 프로젝트에서 비용(토큰/시간/리포트)이 크므로, **전체를 한 번에 강행하지 않고 사용자에게 범위를 확인**한다. 단 명시 인자(`--all`/`--range`/`--files`/`--staged`)가 있으면 묻지 않고 그대로 사용한다.

1. **규모를 경량 파악한다** - `scripts/collect_diff.py --count-only`로 유형별 파일 수를 얻는다(전체 목록/diff 없이 카운트만). **도메인(최상위 패키지/디렉토리) 수**는 경로에서 센다. 파일 내용을 전부 읽지는 않는다.
2. **규모를 알리며 선택지를 제시한다:**
   - **(a) 전체 스캔(점진적)** - 전체를 도메인 단위로 나눠 우선순위 순으로 **한 배치씩** 진행(권장). 아래 "점진적 전체 스캔".
   - **(b) 최근 커밋 범위** - 예: `--range HEAD~10..HEAD`.
   - **(c) 특정 도메인/경로** - `--files <경로>`.
3. (b)/(c)는 해당 범위로 `collect_diff.py`를 호출하고, Stage 4에서 baseline을 저장하면 이후 "마지막 튜닝 이후" 증분으로 동작한다.

> 목적은 "당황"이 아니라 **안내된 선택**이다 - 규모와 선택지를 명확히 제시해 곧바로 고르게 한다.

### 점진적 전체 스캔 (전체를 도메인 배치로)

전체 점검이 필요하지만 한 번에는 부담이 크므로, **도메인(최상위 패키지/디렉토리) 단위 배치로 쪼개 한 배치씩** 진행한다.

1. **배치 분할** - 쿼리 생성 소스를 도메인으로 묶는다(예: `.../order`, `.../user`, `.../payment`). 도메인 구분이 어려우면 파일 N개 단위로 대체한다.
2. **우선순위 정렬** - 위험이 큰 순서로: (1) 이번/최근 마이그레이션/DDL과 관련된 테이블을 쓰는 도메인, (2) 최근 커밋에서 자주 바뀐 도메인, (3) 나머지.
3. **한 배치 튜닝** - 최우선 도메인 하나만 튜닝하여 리포트를 생성한다. 진행 상태를 `state.json`의 `scan_progress`에 저장한다.
4. **다음 배치 확인** - "도메인 X 완료(1/M). 다음(Y) 진행할까요?"를 묻는다.
   - **계속** -> 다음 도메인을 이어서 튜닝한다.
   - **나중** -> 종료한다. `scan_progress`가 남아 다음 실행에서 이어간다.
5. **재개** - 다음 실행 시 진행 중 스캔이 있으면 "전체 스캔 진행 중(X/M). 이어서 다음 도메인? / 그동안의 변경분만? / 처음부터?"를 묻는다. **`--continue`** 인자를 주면 바로 다음 도메인부터 진행한다.
6. **완료** - 모든 도메인을 처리하면 `scan_progress`를 제거하고 baseline을 현재 HEAD로 확정한다. 이후는 "마지막 튜닝 이후" 증분.

`scan_progress` 스키마(진행 중에만 존재):

```json
"scan_progress": {
  "mode": "progressive-full",
  "domains_done": [
    { "name": "order", "globs": ["**/order/**", "**/mapper/Order*.xml"] }
  ],
  "domains_pending": [
    { "name": "payment", "globs": ["**/payment/**", "**/sql/**/payment*.sql"] },
    { "name": "report",  "globs": ["**/report/**"] }
  ],
  "baseline_head": "<스캔 시작 시점 HEAD sha>",
  "started_at": "2026-08-31T10:00:00+09:00"
}
```

> **도메인 식별자 계약(중요):** `domains_done`/`domains_pending`의 각 항목은 **`{ "name", "globs": [...] }`** 객체다. `name`은 표시용 논리명, **`globs`는 그 도메인의 대상 파일을 매칭하는 git pathspec 패턴 목록**이다. `--continue`는 `domains_pending[0].globs`를 **다중 pathspec으로 전개**해 대상을 수집한다(`collect_diff.py`가 처리). 한 도메인이 여러 트리(예: `model/`/`repository/`/`resources/`)에 걸치면 **globs에 여러 패턴을 넣어** 엔티티/마이그레이션 교차가 끊기지 않게 한다. **도메인을 논리명만으로 저장하거나 단일 디렉토리로 좁히지 말 것** - 전자는 재개가 0건이 되고, 후자는 교차가 약화된다. (하위호환: 항목이 문자열이면 그 경로를 name이자 단일 glob으로 취급.)

> **진행 중 baseline 규약:** 점진 스캔이 끝나기 전에는 `last_tuned_commit`을 확정하지 않는다(`null` 유지). 스캔 시작 시점의 HEAD는 `scan_progress.baseline_head`에 보관하고, **모든 도메인 완료 시 이를 `last_tuned_commit`으로 승격**한 뒤 `scan_progress`를 제거한다. 완료 전 중단/재개 사이에 baseline이 어긋나지 않게 하기 위함이다.

## 제안 지문 (안정 키)

라인 번호는 리팩터링에 변하므로 제외한다. 키 = `<id>|<scope>|<target>`.
- `missing_index|orders|user_id`, `missing_index|orders|status,created_at`
- `n_plus_one|UserMapper|orders`, `dialect_pipe_concat|UserRepository|name`

동일 지문은 같은 제안으로 간주 -> 파일 이동/리라인에도 추적이 끊기지 않는다.

## 이전 제안 검증 (Stage 3.5 / follow-up)

> **건너뛰는 경우:** 첫 실행(상태파일 없음)이거나 **`--all`(전체 재검토)** 이면 이 단계를 수행하지 않는다. `--all`은 "처음부터 전체를 보는" 실행이므로 이전 제안과 대조하지 않고 새로 진단한다.

`open_suggestions`를 현재 코드/스키마와 대조해 상태를 갱신한다(정적 best-effort, 신뢰도 표기).

| 제안 유형 | 해결(resolved) 판정 신호 |
|---|---|
| `missing_index` | 대상 인덱스가 DDL/마이그레이션/엔티티 `@Index`에 **존재** |
| `n_plus_one` | 대상 지점에 `@EntityGraph`/`join fetch`/배치 로딩/중첩 결과매핑 도입 |
| `dialect_pipe_concat` | `\|\|` -> `CONCAT`(또는 `PIPES_AS_CONCAT` 확정) |
| `leading_wildcard_like` | 선행 `%` 제거 또는 FULLTEXT 전환 |
| 기타 | 대상 위치에서 해당 안티패턴이 사라짐 |

- **해결** -> `status: resolved`, 리포트 "이전 제안 검증"에 ✅.
- **미해결** -> `open` 유지 + `seen_count += 1`. 리포트 **상단에 ⚠️ 리마인드**(반복 게시), "N회째 미반영" 표시.
- **애매** -> ❓확인필요(정적 확증 불가 - Tier3/수동 권장).
- **대상 코드 삭제** -> `resolved`(해당 없음) 또는 `obsolete`.

## 상태 저장 (Stage 4)

리포트 생성 직후:
- **baseline 전진 조건(중요):** `last_tuned_commit = 현재 HEAD`는 **전체를 대상으로 본 실행에서만** 갱신한다 - 증분(`--since-last`)/전체(`--all`)/점진 스캔 완료 시. **부분 범위(`--files`/`--range`/`--staged`)는 일부만 검토했으므로 `last_tuned_commit`을 전진시키지 않는다** - 미검토분이 "검토됨"으로 취급돼 이후 증분에서 영구 누락되는 것을 막는다. 부분 범위 실행은 `last_report`/`open_suggestions`만 갱신한다.
- `last_tuned_dirty = (working tree 변경 존재 여부)`, `last_report`, `updated_at` 갱신.
- `open_suggestions` = 이번에 미해결로 남은 것 + 새로 발견된 것. `resolved`는 open에서 제거(이력은 리포트가 보관). **단 `--all`은 처음 실행처럼** 이전 `open_suggestions`와 대조/누적하지 않고 **이번에 발견한 것으로 새로 기록**한다(`seen_count`도 초기화).
- **dirty 주의:** 미커밋 상태로 튜닝하고 baseline을 HEAD로 잡으면, 다음 실행이 이번 미커밋분을 놓칠 수 있다. -> `last_tuned_dirty`가 true면 다음 실행 때 baseline을 그대로 두고 **working tree까지 다시 포함**(안전측). 리포트에 "커밋 후 재실행 시 baseline이 전진함"을 안내.

## 견고성 / 옵션

- 상태 파일 손상/부재 -> 가장 최근 `last_report` 타임스탬프에서 baseline 추정, 그래도 없으면 전체.
- `--all` : 언제든 전체 강제. `--staged`/`--range` : 상태 무시하고 명시 범위.
- `--reset-state` : 상태 초기화(다음 실행이 전체). `--no-state` : 상태 읽기/쓰기 없이 1회성.
- 설정 `state.shared: true` : `state.json`을 커밋 대상으로(그 경우 `.gitignore`에서 제외).

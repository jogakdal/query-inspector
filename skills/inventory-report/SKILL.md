---
name: inventory-report
description: >-
  프로젝트의 쿼리(ORM이 생성할 쿼리 포함)를 추출해 목록(카탈로그)으로 만든다 - 튜닝이 아니라 목록화.
  각 쿼리의 목적/용도/대상 테이블(+스키마)/쿼리 본문(전문)/유형/원천/신뢰도 라벨/최종 수정자/
  접근 컬럼/인덱스 커버 여부를 담는다. 기본은 프로젝트 전체이며 대형 저장소는 도메인 배치로 진행.
  Kotlin/Java + MyBatis / 네이티브 SQL / JPA/Hibernate(파생 메서드/@Query/QueryDSL/Kotlin JDSL) 지원.
  출력 언어는 다국어(i18n).
  트리거 - KO: "쿼리 목록", "쿼리 인벤토리", "쿼리 뽑아줘", "쿼리 카탈로그", "무슨 쿼리 있는지";
  EN: "list queries", "query inventory", "query catalog", "what queries", "extract all queries".
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/collect_diff.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/db_guard.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/db_guard.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/db_guard.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/run_explain.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/run_explain.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/run_explain.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/set_db_credential.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/set_db_credential.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/set_db_credential.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/version_check.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/version_check.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/version_check.py *), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/blame_author.py *), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/blame_author.py *), Bash(py ${CLAUDE_PLUGIN_ROOT}/scripts/blame_author.py *)
---

# query-inspector : inventory-report

프로젝트의 쿼리(ORM 생성 포함)를 추출해 **목록(카탈로그)**으로 리포팅하는 스킬. 튜닝(안티패턴 분석)이 아니라 **목록화**다. 배경/아키텍처는 [`DESIGN.md`](../../DESIGN.md).

> **먼저 공통 절차를 따른다:** 기본 원칙/설정/인자 처리(`--help`/`--version`)/업데이트 체크/Stage 0(수집)/0.5(방언)/1(추출)/2(재구성)는 **[`references/pipeline-common.md`](../../references/pipeline-common.md)**에 있다. 이 문서를 먼저 수행한 뒤, 아래 **인벤토리 파이프라인**으로 목록을 완성한다. 안티패턴 튜닝이 필요하면 같은 플러그인의 `tuning-report` 스킬을 쓴다.

## 호출

```
/query-inspector:inventory-report                    # 프로젝트 전체 쿼리 목록(기본 전체)
/query-inspector:inventory-report --all              # 전체 명시(기본과 동일)
/query-inspector:inventory-report --range main..HEAD # 지정 범위의 쿼리만
/query-inspector:inventory-report --files <경로...>  # 특정 파일만
/query-inspector:inventory-report --staged           # staged 변경분만
/query-inspector:inventory-report --continue         # 진행 중인 점진 전체 스캔의 다음 도메인
/query-inspector:inventory-report --db <profile>     # 인덱스 커버를 실 DB 스키마로 확정(opt-in)
/query-inspector:inventory-report --dialect mysql|mariadb|postgresql|oracle|ansi
/query-inspector:inventory-report --lang ko|en|ja|zh
/query-inspector:inventory-report --no-update-check    # 새 버전 확인 건너뜀
/query-inspector:inventory-report --version | --help
```

공통 인자/설정/업데이트 체크/`--help`/`--version` 처리는 `references/pipeline-common.md` 참조.

---

## 인벤토리 파이프라인

공통(Stage 0~2)으로 쿼리를 추출/재구성한 뒤, **Stage 3(튜닝 분석)을 건너뛰고** 각 쿼리에 접근 경로와 인덱스 커버만 부가해 목록으로 출력한다. 심각도 판정/실행 계획(Action Items)/이전 제안 검증(follow-up)은 **하지 않는다.**

**인덱스 커버 부가:** 각 쿼리의 접근 경로(WHERE/JOIN/ORDER BY 컬럼)와 **Tier2 인덱스 커버 여부**를 대조한다(스키마/엔티티/마이그레이션 자동 감지 또는 `--db`가 있을 때. 규칙: `references/tier2-index-matching.md`). 스키마가 없으면 인덱스 항목은 `❓ 스키마 미확인`으로 남기고 **목적/테이블/본문은 그대로 채운다.** 안티패턴 심각도는 매기지 않는다.

**대상 범위:** 기본은 **프로젝트 전체 쿼리**("모든 쿼리" 목적). 규모가 크면 **공통 Stage 0의 점진 배치(도메인 단위)와 `--continue`를 그대로 재사용**해 한 배치씩 목록화한다(첫 실행 범위 확인과 동일 인프라). `--range`/`--files`/`--staged`와 조합하면 그 범위의 쿼리만.

**항목(쿼리별):**
- **목적/용도** - 메서드명/매퍼 id/주변 코드에서 추론한 한 줄 설명(불확실하면 그렇게 표기).
- **대상** - 테이블(+ 알 수 있으면 스키마/DB). 여러 테이블이면 모두.
- **유형** - `SELECT`/`INSERT`/`UPDATE`/`DELETE`/`DDL`.
- **원천** - `파일:라인`(+ 메서드/매퍼 id), **어댑터**, **신뢰도 라벨**(`EXACT`/`INFERRED`/`AMBIGUOUS`).
- **최종 수정자** - 원천 `파일:라인`을 마지막으로 작성/수정한 사람(`scripts/blame_author.py`, git blame). 이름 + 날짜, 미커밋은 "미커밋(작업 중)". git 정보 없으면 생략.
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/blame_author.py --file <경로> --lines <n1,n2,...> --json   # Windows는 python 또는 py
  ```
- **접근 컬럼** - `WHERE`/`JOIN`/`ORDER BY` 컬럼.
- **인덱스 커버** - `✅ <인덱스>` / `❌ 미커버` / `❓ 스키마 미확인`.
- **쿼리 본문(전문/필수)** - 추론 SQL **전문**을 반드시 기재. 동적 쿼리는 대표 시나리오 2~3개를 각각 **전문으로**(라벨 `AMBIGUOUS`).

> **⚠️ 쿼리 본문은 인벤토리의 주된 산출물 - 전문 필수.** 각 쿼리의 SQL 본문(전문)을 **빠짐없이** 적는다. **쿼리 개수가 많다는 이유로 본문을 생략/요약/`...`로 축약하거나 "대표 몇 개만" 싣지 말 것.** 대상이 많으면 본문을 줄이는 게 아니라 **점진 배치(도메인 단위)로 쪼개고 `--continue`로 이어서** 진행해, 결국 **모든 쿼리의 본문이 리포트에 남게** 한다. 터미널 요약에는 목록만 낼 수 있으나, **상세 리포트 파일에는 전체 쿼리의 본문 전문**을 담는다. 개수가 부담되면 "요약"이 아니라 "배치 분할"로 해결한다.

**상태:** 목록화는 튜닝이 아니므로 **`state.json`을 갱신하지 않는다**(baseline 전진/`open_suggestions` 변경 없음). 점진 배치를 쓰면 `scan_progress`는 진행률 표시/`--continue` 재개에만 쓰고, 완료해도 baseline을 전진시키지 않는다.

**출력:** `${CLAUDE_PLUGIN_ROOT}/assets/inventory_template.md`를 채워 `report.dir`의 `inventory-reports/inventory-<timestamp>.md`로 저장하고, 터미널에는 요약(유형/테이블별 쿼리 수 + 상위 목록)을 출력한다. 리포트 헤더에 사용 스킬 버전 표기. 출력 언어는 `report.language`/`--lang`.

---

## 지금 되는 것 / 한계

- ✅ 프로젝트 전체(또는 지정 범위) 쿼리 추출/목록화, 접근 컬럼/인덱스 커버 부가, 최종 수정자 표기, 도메인 배치 + `--continue`.
- 🔎 `jpa`/동적 쿼리는 추론(`INFERRED`/`AMBIGUOUS`)이며 실 SQL은 `show_sql` 등으로 확인 권장(과신 금지).
- 🟠 인덱스 커버는 스키마(자동 감지 또는 `--db`)가 있을 때만 확정 - 없으면 `❓ 스키마 미확인`.

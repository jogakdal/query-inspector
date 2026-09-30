# query-inspector

[English](./README.md) | **한국어**

> Query-inspector는 프로젝트의 SQL과 ORM 생성 쿼리를 다루는 **두 스킬**을 가진 Claude Code 플러그인입니다.<br> 
> **`tuning-report`** 는 변경분의 쿼리를 튜닝하고(N+1/인덱스 미스/안티패턴), **`inventory-report`** 는 프로젝트가 실행하는 모든 쿼리를 목록화합니다.

- 설계 문서: [DESIGN.md](./DESIGN.md)
- 사용자 매뉴얼: 개요 **[MANUAL.ko.md](./MANUAL.ko.md)** - 스킬별 **[tuning-report](./MANUAL-tuning-report.ko.md)** / **[inventory-report](./MANUAL-inventory-report.ko.md)**
- **리포트 출력 언어**: `report.language: auto`로 사용자 대화 언어를 따라 출력합니다.

---

## 스킬 구성

| 스킬 | 호출 | 하는 일                                                                                     |
|------|------|------------------------------------------------------------------------------------------|
| **`tuning-report`** | `/query-inspector:tuning-report` | `git` 변경분 또는 프로젝트 전체의 SQL/ORM 쿼리를 추출해 **튜닝** 수행 ([상세 매뉴얼](./MANUAL-tuning-report.ko.md)) |
| **`inventory-report`** | `/query-inspector:inventory-report` | 프로젝트 쿼리(ORM 생성 포함)를 추출해 **목록**화 ([상세 매뉴얼](./MANUAL-inventory-report.ko.md))              |

두 스킬은 전처리(변경 수집 -> 쿼리 추출 -> SQL 재구성)와 안전장치를 공통으로 사용하고 산출물만 다릅니다. 상황에 맞는 쪽을, 또는 둘 다 사용하실 수 있습니다.<br>
`tuning-report`는 증분 상태를 유지하고 이전 제안을 검증하며, `inventory-report`는 기본적으로 전체 프로젝트를 대상으로 합니다.

---

## ⚠️ 보안 고지 (필독)

두 스킬은 선택적으로 **개발 DB에 접속해 `EXPLAIN` 등 읽기 전용 쿼리를 수행**할 수 있습니다(`tuning-report`: 실행계획 기반 튜닝, `inventory-report`: 인덱스 커버 확정).<br>
아래 사항을 반드시 확인해 주세요.

- **프로덕션 금지**: 이 스킬은 프로덕션 DB에 접속하지 않기 위해 기본으로 `*prod*`/`*live*`/`*production*` 호스트 패턴을 차단하며, `host_allowlist`를 권장합니다.
- **읽기 전용 권장**: DB 접속 계정을 명시할 때 가급적 읽기 전용 계정을 사용해 주세요. 이 스킬은 `SELECT`/`EXPLAIN` 이외의 문장을 실행하지 않습니다(가드레일 코드로 강제).
- **프로젝트 저장소에 자격증명 커밋 금지**:
  - 설정 파일 `.query-inspector.yml`에는 접속 URL의 **변수 이름만** 두고, 실제 URL은 넣지 않기를 권장합니다.
  - `--db` 옵션의 접속 URL은 **환경변수 또는 `.env`에만** 둡니다. `.env`는 스킬이 실행되는 프로젝트 디렉토리에 생성되는, 접속 URL 같은 비밀값 파일입니다.
  - `.env`가 커밋되지 않도록 스킬이 프로젝트 `.gitignore`에 자동 등록하니, 그 항목을 지우지 말아 주세요.
- **선택적 DB 사용**: 기본 실행 시 DB 접속이 필요 없는 정적 분석만 수행합니다. `--db <profile>`로 명시할 때만 DB에 접근합니다.

가드레일 전문은 [DESIGN.md 7절](./DESIGN.md).

---

## 주요 기능

1. `git` 변경분(또는 프로젝트 전체)에서 **쿼리를 생성하는 코드**만 추출합니다(쿼리 무관 변경은 제외).
2. 명시적 SQL은 그대로, **ORM/동적 쿼리는 생성될 SQL을 추론**합니다(신뢰도 라벨 부착).
3. **3단계**로 동작합니다: 정적 휴리스틱 -> 스키마 컨텍스트 -> 실 DB EXPLAIN.
4. **`tuning-report`** 는 위험도/근거/**수정 제안**이 담긴 리포트를, **`inventory-report`** 는 각 쿼리의 **본문 전문**과 인덱스 커버가 담긴 카탈로그를 산출합니다. 
5. 둘 다 코드를 실제 수정하지 않습니다.

---

## 설치

**`claude` CLI로 마켓플레이스를 등록하고 설치합니다.** 기본은 플러그인 방식입니다.

```bash
claude plugin marketplace add jogakdal/query-inspector
claude plugin install query-inspector@query-inspector-marketplace
```

설치 후 새 세션에서 `/query-inspector:tuning-report` 또는 `/query-inspector:inventory-report`로 호출합니다.

> - 저장소를 clone했다면 설치 스크립트로도 됩니다: `bash query-inspector-setup.sh`(옵션 `--project` / `--skill`). **Windows**는 `query-inspector-setup.bat`.
> - 실행 스크립트가 모두 파이썬으로 작성되어 mac/linux/Windows 공통으로 동작합니다.
> - 설치 스크립트가 실행되지 않는 경우 실행 권한(`chmod 755`)을 부여하거나 `bash`를 사용하여 실행해 주세요.

- **플러그인(기본)**
  - 마켓플레이스(`query-inspector-marketplace`)를 등록하고 플러그인(두 스킬)을 설치합니다.
  - 호출은 **`/query-inspector:tuning-report`** 또는 **`/query-inspector:inventory-report`**, 갱신은 `claude plugin update query-inspector@query-inspector-marketplace`(재시작 필요).
  - 설치 스크립트 한 파일만 있어도 동작합니다(저장소 clone 불필요).
  - 기본은 개인 글로벌(user)이며 `--project` 옵션으로 프로젝트 로컬(이 프로젝트에서만) 설치를 고를 수 있습니다(`--project`는 **대상 프로젝트 루트에서 실행**).
  - `claude` CLI가 필요하며, 공개 저장소는 익명으로 받으므로 별도 인증이 없어도 됩니다.
- **스킬(`--skill`)**
  - 플러그인 트리(두 스킬 + 공유 자산)를 `~/.claude/skills/query-inspector/`(기본) 또는 `<프로젝트>/.claude/skills/query-inspector/`(`--project`)에 복사합니다.
  - 로컬에 파일이 없으면 저장소를 자동으로 clone합니다.

전체 설치 안내(방식 비교/수동 설치): **[INSTALL.ko.md](./INSTALL.ko.md)** <br>
사용/설정/문제 해결: 개요 **[MANUAL.ko.md](./MANUAL.ko.md)** 또는 위 스킬별 매뉴얼

---

## 의존성

**기본 사용(Tier1/Tier2)에는 추가 설치가 없습니다** - `git`과 `python3`(mac/linux) 또는 `python`/`py`(Windows), 표준 라이브러리만 있으면 됩니다. <br>
실행 스크립트가 모두 파이썬이라 **mac/linux/Windows 공통**으로 동작합니다. <br>
튜닝의 대부분(인덱스 누락/N+1/SQL 방언(dialect) 불일치/안티패턴)이 Tier1/Tier2에서 처리됩니다.

|                    단계                    | 필요 사항 |
|:----------------------------------------:|-----------|
|          **Tier1** 정적 휴리스틱 (기본)          | 없음 |
|            **Tier2** 스키마 컨텍스트            | 없음 (스키마 파일/실 DB 조회) |
| **Tier3** 실 DB EXPLAIN (`--db`, opt-in)  | MySQL: `mysql` CLI 또는 `pymysql` / PostgreSQL: `psql` 또는 `psycopg` / 공통 `PyYAML` |

Tier3는 **드라이버 우선 + `mysql` CLI 폴백**이라, pip 설치가 제한된 환경에서도 CLI만으로 동작합니다. <br>
드라이버/CLI가 모두 없으면 Tier3만 자동으로 Tier2로 강등됩니다.

---

## 빠른 시작

```bash
# 1) 설정 템플릿 복사(선택 - 없어도 기본값으로 동작)
cp .query-inspector.example.yml .query-inspector.yml

# 2) 변경 스테이징 후 호출(플러그인 설치 기준)
git add .
claude
> /query-inspector:tuning-report
```

| 명령 | 동작 |
|------|------|
| `/query-inspector:tuning-report` | 마지막 튜닝 이후 변경분(첫 실행이면 범위 확인) |
| `/query-inspector:tuning-report --all` | 전체 쿼리 관련 소스(증분/baseline 무시) |
| `/query-inspector:tuning-report --all --no-state` | 전체 스캔 + 상태(state) 미저장(1회성) |
| `/query-inspector:tuning-report --range main..HEAD` | 지정 범위 |
| `/query-inspector:tuning-report --db dev` | dev 프로파일로 EXPLAIN 심화(opt-in) |
| `/query-inspector:inventory-report` | (튜닝 대신) 프로젝트 쿼리 목록화(기본 전체) |
| `/query-inspector:tuning-report --version` | 설치된 버전 출력 |
| `/query-inspector:tuning-report --help` | 사용법 도움말 |

스킬별 상세: [tuning-report 매뉴얼](./MANUAL-tuning-report.ko.md) / [inventory-report 매뉴얼](./MANUAL-inventory-report.ko.md).

---

## 튜닝 단계 (자동 강등)

`tuning-report`는 세 단계로 튜닝합니다(`inventory-report`는 인덱스 커버에 Tier 1~2를 씁니다):

- **Tier 1 - 정적 휴리스틱** (DB 불필요, 항상 동작): N+1, `SELECT *`, 비-SARGable 조건, 선행 와일드카드 LIKE, 페이징 없는 대량 조회 등.
- **Tier 2 - 스키마 컨텍스트** (DDL / 엔티티 / 마이그레이션 자동 감지, 또는 `--db` 실 DB 스키마 조회): 인덱스 존재 대조, 구체적 `CREATE INDEX` 제안.
- **Tier 3 - 실 DB EXPLAIN** (`--db`, opt-in): 실행계획 기반 심화, before/after 비교.

스키마가 없으면 Tier1로, DB 접속 실패면 Tier2로 자동 강등되고 리포트에 명시합니다.

---

## 리포트 예시
### tuning-report

결과는 **리포트로 제공**되며 코드를 직접 수정하지 않습니다(수정안만 제안). **실행 계획(Action Items)** 이 포함돼 개발자나 그 개발자의 AI가 바로 착수할 수 있습니다.

실제 리포트의 일부(증분, 2회차):

```markdown
# Query Tuning Report - 증분(변경 파일 2)
- 심각도(미해결): 🔴 3 / 🟡 2 / ⚪ 1   /   이전 제안: ✅ 2건 해결 / ⚠️ 2건 여전히 미반영(2회째)

## 🔴 [critical] 인덱스 누락 - FK `orders.user_id` - OrderMapper.xml (SCHEMA-CONFIRMED / 2회째)
- 왜 치명적: N+1 자식 쿼리라 user N명마다 `orders` 풀스캔.
- 제안:  CREATE INDEX idx_orders_user_id ON orders (user_id);
- 검증(Tier 3, --db): EXPLAIN에서 `type: ALL -> ref` 확인.

## ✅ 실행 계획 (Action Items)
- [ ] [자동적용] 인덱스 마이그레이션 추가 - 새 파일 V3__orders_indexes.sql (2회째 리마인드)
      CREATE INDEX idx_orders_user_id        ON orders (user_id);
      CREATE INDEX idx_orders_status_created ON orders (status, created_at);
```

**follow-up** 기능은 지난 실행의 제안과 대조하여, 이번에 수정하지 않은 파일이라도 *여전히* 미반영인 2건을 표시합니다.

- **터미널 요약** - 위험도순 상위 N개.
- **상세 파일** - `docs/query-inspector/tuning-reports/<timestamp>.md` (이력/캐시). 전체 예시: [examples/sample-report.md](./examples/sample-report.md).

각 이슈: 원천(`파일:라인`) / 추론 SQL(+신뢰도 라벨 `EXACT`/`INFERRED`/`AMBIGUOUS`) / 최종 수정자(git blame) / 근거 / 수정 제안 / 검증 방법.

---

### inventory-report

`inventory-report`는 프로젝트 쿼리를 **목록(카탈로그)** 으로 만듭니다 - 심각도나 수정 제안 없이, 각 쿼리의 **본문 전문**과 인덱스 커버를 남깁니다.

실제 인벤토리의 일부:

```markdown
# Query Inventory - 2026-09-30
- 범위: 프로젝트 전체 / 방언: mysql / 스키마 소스: SCHEMA-CONFIRMED
- 쿼리 수: 24 ( SELECT 18 / INSERT 3 / UPDATE 2 / DELETE 1 )   /   신뢰도: EXACT 15 / INFERRED 7 / AMBIGUOUS 2

## 요약 (테이블별)
| 테이블  | 쿼리 수 | 유형 분포           | 인덱스 미커버 |
|--------|--------|--------------------|-------------|
| orders | 8      | SELECT 6 / UPDATE 2 | 1 (❌)      |
| member | 5      | SELECT 5           | 0           |

## 쿼리 목록  (도메인: order)
#### [order-03] 사용자별 주문 목록 조회
- 원천: OrderMapper.xml:42 (selectOrdersByUser) / 어댑터: mybatis / 유형: SELECT / 신뢰도: EXACT
- 대상: orders / 접근 컬럼: WHERE user_id, ORDER BY created_at
- 인덱스 커버: ❌ 미커버 (user_id 인덱스 없음)
- 쿼리 본문:
      SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC;
```

각 쿼리: 목적 / 원천(`파일:라인`) / 최종 수정자 / 어댑터, 유형, 신뢰도 / 대상 테이블 / 접근 컬럼 / 인덱스 커버(✅ 커버 / ❌ 미커버 / ❓ 스키마 미확인) / **본문 전문**. 자세한 형식은 [inventory-report 매뉴얼](./MANUAL-inventory-report.ko.md)에 있습니다.

---

## 정확도 한계

ORM이 생성한 동적 쿼리는 100% 재구성이 불가능합니다. 그래서 모든 추론 쿼리에 신뢰도 라벨을 붙이고, `AMBIGUOUS` 항목은 "실제 SQL 검증 방법"(예: Hibernate `show_sql`)을 함께 안내합니다.

---

## 확장 (새 스택 추가)

**Python(Django / SQLAlchemy)** 도 어댑터로 지원하지만 주력 스택만큼 검증되지는 않았습니다(예: `stacks: [python-django]`). **다음 후보는 Node(Prisma/TypeORM)/.NET(EF Core/Dapper)** 이며, 코어 수정 없이 `references/adapters/<stack>.md`만 추가하면 되는 구조라 기여를 환영합니다. -> [references/adapters/_template.md](./references/adapters/_template.md)

기여 환영 - [CONTRIBUTING.md](./CONTRIBUTING.md) 참고.

---

## 라이선스

[MIT](./LICENSE) - 상업 이용/수정/재배포 자유. 저작권/라이선스 고지만 유지하세요.

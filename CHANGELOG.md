# Changelog

이 프로젝트의 주요 변경사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/),
버전 체계는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

> 플러그인 갱신(`claude plugin update`)은 버전 비교로 동작하므로, 스킬 내용을 바꿀 때는 `plugin.json`/`marketplace.json`의 버전을 함께 올립니다.

## [1.3.0] - 2026-10-19

### Added
- **휴리스틱 ID `random_clustered_pk`** - 랜덤/UUID 값을 클러스터드 PK(InnoDB)로 사용해 삽입 단편화/페이지 분할을 유발하는 패턴(기본 🟡 warn, 방언 의존). **단조 증가 surrogate PK(`AUTO_INCREMENT`/시퀀스/IDENTITY)는 권장 사례이므로 지적하지 않는다**(오탐 방지 - "불필요한 인조키" 자체는 설계 선택이라 검출 대상 아님). 수정 제안은 `BIGINT AUTO_INCREMENT` PK + UUID는 UNIQUE 보조, 또는 UUIDv7/ULID, 또는 `UUID_TO_BIN(uuid,1)`. 방언 노트: MySQL/InnoDB 영향 큼, PostgreSQL은 힙 테이블이라 거의 해당 없음. heuristics/i18n/example 3곳 정합.

## [1.2.0] - 2026-10-12

svc-settle-batch(Spring Batch 레거시) 점진 스캔 자가 진단을 반영한 레거시/배치 분석 강화 + 점진 스캔 세션 리포트 릴리스.

### Added
- **휴리스틱 ID 4종** - `tx_not_participating`(쓰기 트랜잭션 미참여·원자성), `replica_routing_defect`(read replica 라우팅), `connection_abandon`(풀 abandon), `paging_on_mutating_set`(처리로 줄어드는 대상의 OFFSET 페이징·정확성). 앞 3종은 `out_of_catalog`에서 승격. heuristics/i18n/example 3곳 정합.
- **도달 가능성(활성/비활성/미사용) 판정**(heuristics) - 비활성/미사용 경로 결함을 info로 하향(레거시에서 미사용 코드 결함이 critical 상단을 점유하는 문제 대응). MyBatis 호출부 추적 절차(타입 기준, 동명 메서드 혼동 방지)도 추가.
- **심각도 결정 순서**(heuristics, pipeline-common 참조) - 도달가능성 -> `severity_rules` -> SCHEMA-PARTIAL 고정 -> 반복형 매트릭스 -> 기본값을 한 곳에 정리.
- **Spring Batch 트랜잭션 배선 점검**(native-sql) - step 트랜잭션 매니저와 리포지토리/매퍼 트랜잭션 매니저의 리소스 일치 여부.
- **collect_diff `--plan-domains`**(점진 스캔 도메인 globs의 커버리지/중복/테스트 혼입 검증) / **`--paths-only`**(대상 경로 NUL 출력).

### Changed
- **점진 스캔(`--continue`) 리포트를 세션 단위 한 벌로 누적** - 이터레이션(도메인 배치)마다 새 타임스탬프 리포트를 만들던 것을, 점진 스캔의 **모든 이터레이션을 하나의 세션**으로 보고 `scan_progress.report_file` 단일 리포트에 누적/갱신한다(뒤 배치가 앞 도메인 항목을 같은 파일에서 정정). 세션 간/일반 실행은 타임스탬프 이력 유지, 진단 리포트는 이터레이션마다 생성(현행). tuning/inventory 공통.
- **follow-up `seen_count`** - 대상 파일에 변경이 있을 때만 증가(코드 변경 0건 배치에 "N회째 미반영"이 누적되던 문제 대응), 재게시 1줄 압축.
- **collect_schema_candidates 내용 기반 DDL 판별** - `CREATE TABLE/INDEX/ALTER`를 담은 실제 DDL과 테스트 INSERT 픽스처를 분리 표기.
- 소유권/도메인 이관(`scan_progress.deferred`), 대형 도메인 하위 분할 기준, 테이블 통합 `missing_index` 지문(`|<table>|*`), `open_suggestions`에 progress/notes/last_checked, 실행계획 선후 표기, 근거 정정(🔄) 표기.
- **blame_author 이메일 기본 생략**(`--with-mail`로 선택). tier2 엔티티 주석 타입 보조 소스/규모 미확인 표기, mysql 방언 배치 간 재사용, version_check `cached` 키 설명, 리포트 안내문 평서체.

## [1.1.1] - 2026-10-12

JVM 주력 스택(Kotlin + JdbcTemplate 래퍼/QueryDSL/JPA) 실무 검증(svc-settle-admin)의 자가 진단을 반영한 판정 정확도/병렬 처리/카탈로그 강화 릴리스.

### Added
- **`out_of_catalog` 공식화** - 명명된 휴리스틱에 없는 결함(쓰기 트랜잭션 미참여, read replica 라우팅 결함, 트랜잭션 없는 복합 쓰기 등)을 담는 메타 ID. 심각도는 성격별 규칙(정확성/원자성/보안 critical, 성능 warn, 기타 info)으로 판정하고 이름에 구체 패턴을 병기. heuristics/i18n/example 정합. (실무 최상위 결함 3건이 카탈로그 밖이던 문제 대응)
- **문자열 보간 3단계 판정(native-sql)** - 보간 값의 출처로 심각도를 분기: (a) 상수/enum/정적 빌더 -> 비보고, (b) 타입 강제 값(Int/Long/LocalDate/enum) -> info(인젝션 불가, 플랜 캐시/빈 목록), (c) String 외부 입력 -> critical. 일괄 critical 처리로 생기던 대량 오탐 해소.
- **`--all` 1회 병렬 브리프 템플릿** - 서브에이전트 공통 브리프(심각도 정책/소유권 규칙/출력 JSON 스키마/`self_diagnosis_notes`)와 테이블 단위 인덱스 통합 설계 규칙을 `state-and-followup.md`에 정의. `--all`이 1회 전체 병렬임을 명시.
- **프로젝트 고유 DAO 래퍼 탐지(native-sql)** - `JdbcTemplate`/`NamedParameterJdbcTemplate`을 감싸는 자체 래퍼의 public 메서드를 쿼리 진입점으로 등록하는 절차.
- **Tier2 스키마 후보 출력(collect_diff)** - DDL/스키마 `.sql`(테스트 리소스 포함)을 튜닝 대상과 별개로 `schema-candidates` 섹션에 수집. SCHEMA-PARTIAL 시 `information_schema.STATISTICS` 일괄 확인 SQL을 리포트에 안내.

### Fixed
- **version_check 캐시의 git status 오염** - 업데이트 체크 캐시(`update-check.json`)를 프로젝트 `docs/query-inspector/`가 아니라 **사용자 캐시 디렉토리**(XDG/LOCALAPPDATA)에 저장. Stage 0 이전에 미추적 `docs/`가 생기고 `.gitignore`가 없어 `git status`가 오염되던 문제와 `state.shared=true`의 `.gitignore` 충돌을 함께 해소.
- **template 분류 과대** - SPA 셸(`frontend/public/index.html`)/정적·빌드 HTML을 `template`에서 제외(`other`). 서버 렌더 템플릿(`templates/`, `.jinja`)만 N+1 점검 대상으로 유지.

### Changed
- SCHEMA-PARTIAL `missing_index` 심각도를 `warn`으로 고정(확정 소스 확보 시 critical 승격), 어조를 "미확인 - 확인 필요"로.
- 반복형 심각도 매트릭스에 "외부 연동 API(빈도 미상)" 열 추가 + `severity_rules`(운영자 고정값) 우선 적용 명시.
- 리포트 템플릿에 전체 스캔용 범위 문구 분기(변경분 vs 전체), 실행 계획 그룹명 분기(`이번 배포` vs `우선 조치`), 병합 항목 `관련 위치` 필드. 상태 스키마에 `locations[]`/`report_no`.
- MySQL 방언 노트에 "스트리밍 착시"(`JdbcTemplate.queryForRowSet`=CachedRowSet, QueryDSL `fetch().stream()`=전량 적재) + `useCursorFetch` 비용. 자가 진단에 병렬 메타 수집(`self_diagnosis_notes`) 규칙.

## [1.1.0] - 2026-10-08

실무 검증(django-oscar, flaskbb)과 각 자가 진단 리포트를 반영한 Python(Django/SQLAlchemy) 커버리지 강화 + 버그 수정 릴리스.

### Added
- **Python(Django/SQLAlchemy) 커버리지 강화** - 원시 SQL 안티패턴 감지(`.raw()`/`.extra()`/`text()`의 f-string/%/+ 보간 -> `string_substitution`, `||`/`NVL`/`SYSDATE`/`ROWNUM` -> `dialect_pipe_concat`, `SELECT *` -> `select_star`). Django 마이그레이션(`migrations/*.py`)과 SQLAlchemy(`versions/*.py`)를 쿼리 소스로 1급 분류. SQLAlchemy는 FK 자동 인덱스가 없어 `user_id`도 `missing_index` 대상(Django와 반대).
- **휴리스틱 ID 6종 추가** - `write_in_loop`/`lost_update`/`duplicate_query`/`stale_queryset_cache`/`query_correctness`/`scope_filter_bypass`(보안; 카탈로그/i18n/설정 일관). N+1 심각도 매트릭스(N 상한 x 실행 빈도) 추가.
- **어댑터/방언 규칙 보강(Django)** - python-django: 대소문자 룩업 번역 정정(`__iexact`는 등호, `__istartswith` 추가), 암묵 인덱스(SlugField/O2O/M2M/`*_pattern_ops`), `Meta.ordering` 예외, 마이그레이션 연산 목록, N+1 원천/해소 함정, 행 곱셈/팬아웃. PostgreSQL 방언 노트 스텁 해제(표현식 인덱스 식 일치, pg_trgm, `CONCURRENTLY`, 역방향 스캔, `COUNT(*)`, PG18 skip scan).
- **어댑터 규칙 보강(SQLAlchemy/Flask, flaskbb 검증)** - 조인 없이 `where`에 타 엔티티를 참조하는 **암묵 FROM 카티전 곱**과 relationship `.any()`/`.has()`의 **비상관 EXISTS(필터 무력화)** 구분 + 컴파일 검증(프로젝트 venv 사용), Flask-SQLAlchemy 구문(`Model.query`/`db.paginate`/`WriteOnly`·`DynamicMapped`), 연관(secondary) 테이블·`ON DELETE CASCADE` 참조측 인덱스(PostgreSQL), Python 멀티 DB 방언 판정(운영 구성 우선), Jinja2 등 서버 템플릿을 `template` 유형으로 수집해 N+1 점검.

### Fixed
- **상태 경로 불일치(치명)** - `SKILL.md`가 상태를 `<report.dir>/state.json`으로 적어 스크립트(`<report.dir>/tuning-reports/state.json`)와 어긋나, 두 번째 실행부터 증분/follow-up이 깨지던 문제.
- **collect_diff** - `--files`가 baseline diff로 한정돼 첫 실행 후 0건이 되던 문제, diff 모드의 `other`/삭제 파일 미제외, `--continue`의 glob pathspec(`:(glob)`), 테스트 경로 판정(저장소 상대 + Python `tests/`/`test_*.py`), 루트 `migrations/*.py` 분류, `--all`에서 테스트/문서(`docs/`/`setup.py` 등) 노이즈 제외.
- **blame_author** - `.git-blame-ignore-revs` 자동 적용(일괄 포맷 커밋 오귀속 방지), 일괄 blame 실패 시 라인별 재시도(실행자 오귀속 방지).
- **version_check** - 기본 원격 HTTPS 전환(SSH :22 차단 환경의 매 실행 지연 제거), 실패 백오프 캐시, 빠른 실패, 로컬>원격(개발 빌드) 구분 표시.
- 어댑터 휴리스틱 id `redundant_distinct` -> `distinct_abuse` 정합.

### Changed
- 자가 진단 리포트 템플릿에 `fix_site`(수정 지점)/검증 수준 필드, info 축약, 대규모 병렬 스캔 병합 규칙 안내.
- critical 종료 신호를 `[query-inspector] critical=<N>` 터미널 마커로 정의. 자동 실행 예시의 스크립트 경로 따옴표 제거(`allowed-tools` 권한 매칭 정합).

## [1.0.3] - 2026-10-07

### Added
- **(내부 전용/undocumented) `--self-diagnose-internal`** - 정상 실행에 더해, 스킬을 실행하는 주체(AI)가 실행 환경/지침 품질/버그/개선점을 관찰해 `docs/query-inspector/diagnostics/`에 **자가 진단 리포트**를 추가 생성한다(정규 리포트와 별개, 온라인 전송 없음). 반복 개선/검증용. 절차는 `references/self-diagnostic.md`. help/README/MANUAL에는 노출하지 않는다(스크립트 로직 변경 없음).

## [1.0.2] - 2026-10-07

### Changed
- **설치는 플러그인 전용** - 설치 스크립트(`query-inspector-setup.sh`/`.bat`)에서 스킬 직접 복사(`--skill`)를 제거. 멀티스킬 + 공유 자산(`${CLAUDE_PLUGIN_ROOT}`) + `/query-inspector:` 네임스페이스 구조는 스킬 폴더 복사로는 로드되지 않습니다. 대신 **`--local`**(로컬 체크아웃을 마켓 소스로 등록해 설치 - clone/포크/오프라인/수정판)을 추가. 문서(README/INSTALL/MANUAL/DESIGN)도 플러그인 전용으로 정리.

## [1.0.0] - 2026-09-30

첫 공개 릴리스. 두 스킬(`tuning-report`, `inventory-report`)로 구성됩니다.

### Added
- **`tuning-report`** - `git` 변경분(또는 프로젝트 전체)의 SQL/ORM 쿼리를 추출해 인덱스 누락/N+1/안티패턴을 진단하고, 수정 제안이 담긴 리포트를 생성. 증분 + 이전 제안 검증(follow-up).
- **`inventory-report`** - 프로젝트 쿼리를 목적/대상 테이블/본문 전문/인덱스 커버로 목록화.
- **3-Tier 자동 강등** - 정적 휴리스틱 -> 스키마 인덱스 대조(엔티티/마이그레이션/DDL 자동 감지 또는 `--db`) -> 실 DB `EXPLAIN`(opt-in, MySQL/MariaDB/PostgreSQL).
- **스택/방언** - MyBatis, 네이티브 SQL, JPA/Hibernate(파생 메서드/`@Query`/QueryDSL/Kotlin JDSL 등 추론), 마이그레이션 어댑터. Python(Django/SQLAlchemy)은 주력 스택만큼 검증되지는 않음. 방언 자동 감지(MySQL/MariaDB, PostgreSQL; Oracle 스텁).
- **과신 방지** - 모든 추출 쿼리에 신뢰도 라벨(`EXACT`/`INFERRED`/`AMBIGUOUS`), 동적 쿼리는 대표 시나리오로 전개하고 실 SQL 검증(`show_sql`) 안내.
- **바로 쓰는 리포트** - 위험도순 요약 + 실행 계획(Action Items: `[자동적용]`/`[검토후]`/`[확인후]` + 복붙용 코드/DDL). 코드 자동 수정은 하지 않음. 최종 수정자(git blame) 표기.
- **Tier 3 안전장치** - `--db` opt-in, 프로덕션 호스트(이름 패턴/공인 IP) 차단, `SELECT`/`EXPLAIN`만 허용(가드레일 코드로 강제), `EXPLAIN ANALYZE`는 트랜잭션 롤백. 접속 정보는 환경변수/`.env`로만 조달하고 리포트/로그에 미기록. 드라이버 우선 + CLI 폴백, 둘 다 없으면 Tier 2로 강등.
- **배포/운영** - 실행 스크립트 전부 파이썬(mac/linux/Windows 공통, bash 불필요). 설치 스크립트로 마켓플레이스 등록 + 플러그인 설치. 하루 1회 업데이트 확인(`--no-update-check`로 끄기), `--version`. 출력 언어 `report.language: auto`(`--lang`). 증분 상태 `docs/query-inspector/tuning-reports/state.json`(로컬/gitignore, `state.shared`로 팀 공유).

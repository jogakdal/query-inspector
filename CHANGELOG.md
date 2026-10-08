# Changelog

이 프로젝트의 주요 변경사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/),
버전 체계는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

> 플러그인 갱신(`claude plugin update`)은 버전 비교로 동작하므로, 스킬 내용을 바꿀 때는 `plugin.json`/`marketplace.json`의 버전을 함께 올립니다.

## [1.1.0] - 2026-10-08

실무 검증(django-oscar)과 그 자가 진단 리포트를 반영한 Python 커버리지 강화 + 버그 수정 릴리스.

### Added
- **Python(Django/SQLAlchemy) 커버리지 강화** - 원시 SQL 안티패턴 감지(`.raw()`/`.extra()`/`text()`의 f-string/%/+ 보간 -> `string_substitution`, `||`/`NVL`/`SYSDATE`/`ROWNUM` -> `dialect_pipe_concat`, `SELECT *` -> `select_star`). Django 마이그레이션(`migrations/*.py`)과 SQLAlchemy(`versions/*.py`)를 쿼리 소스로 1급 분류. SQLAlchemy는 FK 자동 인덱스가 없어 `user_id`도 `missing_index` 대상(Django와 반대).
- **휴리스틱 ID 5종 추가** - `write_in_loop`/`lost_update`/`duplicate_query`/`stale_queryset_cache`/`query_correctness`(카탈로그/i18n/설정 일관). N+1 심각도 매트릭스(N 상한 x 실행 빈도) 추가.
- **어댑터/방언 규칙 보강** - python-django: 대소문자 룩업 번역 정정(`__iexact`는 등호, `__istartswith` 추가), 암묵 인덱스(SlugField/O2O/M2M/`*_pattern_ops`), `Meta.ordering` 예외, 마이그레이션 연산 목록, N+1 원천/해소 함정, 행 곱셈/팬아웃. PostgreSQL 방언 노트 스텁 해제(표현식 인덱스 식 일치, pg_trgm, `CONCURRENTLY`, 역방향 스캔, `COUNT(*)`, PG18 skip scan).

### Fixed
- **상태 경로 불일치(치명)** - `SKILL.md`가 상태를 `<report.dir>/state.json`으로 적어 스크립트(`<report.dir>/tuning-reports/state.json`)와 어긋나, 두 번째 실행부터 증분/follow-up이 깨지던 문제.
- **collect_diff** - `--files`가 baseline diff로 한정돼 첫 실행 후 0건이 되던 문제, diff 모드의 `other`/삭제 파일 미제외, `--continue`의 glob pathspec(`:(glob)`), 테스트 경로 판정(저장소 상대 + Python `tests/`/`test_*.py`), 루트 `migrations/*.py` 분류.
- **blame_author** - `.git-blame-ignore-revs` 자동 적용(일괄 포맷 커밋 오귀속 방지), 일괄 blame 실패 시 라인별 재시도(실행자 오귀속 방지).
- **version_check** - 기본 원격 HTTPS 전환(SSH :22 차단 환경의 매 실행 지연 제거), 실패 백오프 캐시, 빠른 실패.
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

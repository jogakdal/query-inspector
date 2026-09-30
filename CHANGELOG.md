# Changelog

이 프로젝트의 주요 변경사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/),
버전 체계는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

> 플러그인 갱신(`claude plugin update`)은 버전 비교로 동작하므로, 스킬 내용을 바꿀 때는 `plugin.json`/`marketplace.json`의 버전을 함께 올립니다.

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
- **배포/운영** - 실행 스크립트 전부 파이썬(mac/linux/Windows 공통, bash 불필요). 설치 스크립트(플러그인 기본 + `--skill` 직접 설치). 하루 1회 업데이트 확인(`--no-update-check`로 끄기), `--version`. 출력 언어 `report.language: auto`(`--lang`). 증분 상태 `docs/query-inspector/tuning-reports/state.json`(로컬/gitignore, `state.shared`로 팀 공유).

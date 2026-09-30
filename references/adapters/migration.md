# 어댑터: `migration` (M2 / 구현 진행 중)

Flyway/Liquibase 마이그레이션을 처리한다. **이중 역할**: (1) DDL/DML 자체의 검토 대상, (2) **Tier2 인덱스 인벤토리의 주 소스**(`references/tier2-index-matching.md` 1절). 인덱스 누락 판정의 사실상 기준선이라 `missing_index`(*)와 직결된다.

## 대상 파일

- **Flyway**: `src/main/resources/db/migration/V*__*.sql`, `R__*.sql`.
- **Liquibase**: `db/changelog/**`(XML/YAML/JSON/SQL changeset), `databaseChangeLog`.

## 추출/추적

- **DDL 파싱**: `CREATE/ALTER TABLE`, `CREATE/DROP INDEX`, `ADD/DROP CONSTRAINT`(PK/UNIQUE/FK), 컬럼 타입 변경.
- **인덱스 상태 시간순 누적**: `V1` create index -> `V3` drop index -> **최신 상태**를 산출해 인덱스 인벤토리에 공급. 버전 순서(파일명 `V<n>`)를 존중한다.
- **DML**(`INSERT/UPDATE/DELETE`): **실행하지 않음.** 정적 검토만(가드레일 7-4절).

## Tier2 인덱스 대조 소스

- 마이그레이션이 정의한 **최신 스키마(테이블/인덱스/PK/FK)** 를 재구성해 `tier2-index-matching.md`의 대조에 공급한다.
- **마이그레이션 교차(최강 신호):** 같은 변경분에 새 쿼리가 추가됐는데 그 컬럼 인덱스가 함께 온 마이그레이션에 없으면 -> "이번 배포에 필요한 인덱스가 빠졌다"고 `missing_index`를 승격하고, 실행 계획에 `[자동적용]` 인덱스 마이그레이션 추가를 제안한다.
- 대상 테이블 정의를 전부 확보하면 `SCHEMA-CONFIRMED`, 일부만이면 `SCHEMA-PARTIAL`.

## `CREATE VIEW` / `CREATE OR REPLACE VIEW`

뷰는 **저장된 SELECT**이므로 내부 쿼리를 추출해 **Tier1 휴리스틱 + Tier2 인덱스 대조**를 적용한다. 마이그레이션 파일이면 `migration-sql`로 분류돼 native-sql 어댑터가 타지 않으므로, 여기서 명시적으로 처리한다(그렇지 않으면 뷰 내부 쿼리가 사각지대가 된다).

- 뷰 정의의 SELECT를 한 쿼리로 보고 WHERE/JOIN/ORDER BY 컬럼을 추출해 인덱스 대조(`tier2-index-matching.md`).
- 조인이 여러 테이블을 넘나들면 관련 테이블 DDL을 **교차 참조**해 조인 키 인덱스를 확인한다.
- 대상 테이블 정의를 확보하지 못하면 `SCHEMA-PARTIAL`로 낮춘다.
- 뷰는 실행하지 않고 정적 분석만 한다. `leading_wildcard_like`/`non_sargable_predicate`/`derived_table_filter` 등 일반 휴리스틱도 동일하게 적용.

## 운영 영향 (DDL 안전)

- 대형 테이블 `ALTER`/`CREATE INDEX`의 잠금/온라인 여부를 SQL 방언(dialect)별로 경고: MySQL online DDL(`ALGORITHM=INPLACE`), PostgreSQL `CREATE INDEX CONCURRENTLY`, Oracle 온라인 인덱스. 근거와 함께 제안하되 실행하지 않는다.

## 신뢰도 라벨

- DDL은 원문 -> `EXACT`(인덱스 인벤토리/스키마 컨텍스트의 근거).

## 산출물 형식

- 인덱스 인벤토리 기여분(테이블->인덱스 목록), DDL 변화 목록, 운영 영향 경고, 마이그레이션 교차 판정.

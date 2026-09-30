# query-inspector 사용자 매뉴얼

[English](./MANUAL.md) | **한국어**

`query-inspector`는 프로젝트에 포함된 **쿼리를 최적화**하기 위한 두 개의 **스킬**을 제공합니다. <br>
이 스킬을 수동으로 호출하면 현 프로젝트 전체 또는 코드의 변경분에 대한 **튜닝 리포트** 또는 **쿼리 인벤토리 리스트**를 생성해 줍니다.<br>
실행 스크립트가 모두 파이썬으로 작성되어 **mac / Linux / Windows 공통**으로 동작합니다.

별도로 제공되는 문서는 다음과 같습니다.

> 소개/차별점: [README.ko.md](./README.ko.md) <br>
> 전체 설치 안내: [INSTALL.ko.md](./INSTALL.ko.md)<br>
> 설계: [DESIGN.md](./DESIGN.md)<br>변경 이력: [CHANGELOG.md](./CHANGELOG.md)

---

## 스킬 구성

|           스킬            | 하는 일                                                                              | 매뉴얼 |
|:-----------------------:|-----------------------------------------------------------------------------------|--------|
|   **`tuning-report`**   | 변경분의 SQL / ORM 쿼리를 추출해 **튜닝** 리포트 생성 - 인덱스 누락 / N+1 / 안티패턴 리포팅. 기본 증분 + 이전 제안 검증. | **[MANUAL-tuning-report.ko.md](./MANUAL-tuning-report.ko.md)** |
| **`inventory-report`**  | 프로젝트 쿼리를 추출해 **목록** 생성 - 목적 / 테이블 / 쿼리 본문 전문 / 인덱스 커버리지 리포팅. 튜닝은 하지 않음.           | **[MANUAL-inventory-report.ko.md](./MANUAL-inventory-report.ko.md)** |

```
/query-inspector:tuning-report       # 변경분의 쿼리 튜닝(기본 증분)
/query-inspector:inventory-report    # 프로젝트 쿼리 목록화(기본 전체)
```

둘 다 설치 방식과 무관하게 네임스페이스로 호출하며, 설치 후 명령이 보이려면 **새 Claude Code 세션**이 필요합니다.

### 스킬 선택 기준

- **쿼리 성능 개선** - 인덱스 누락 / N+1 / 안티패턴 -> `tuning-report`.
- **프로젝트가 실행하는 모든 쿼리 확인** - 본문 전문 + 인덱스 커버리지 -> `inventory-report`.

둘은 독립적이라 상황에 맞는 쪽을, 또는 둘 다 쓰면 됩니다. `tuning-report`는 증분 상태를 유지하고 이전 제안을 검증하며, `inventory-report`는 기본적으로 전체 프로젝트를 대상으로 합니다.

---

## 공통 사항

아래 항목은 여기서 요약하고, 각 스킬 매뉴얼에서 상세히 다룹니다.

- **설치**: 설치 스크립트 하나(기본 플러그인, `--skill`은 파일 직접 설치). 전체 안내는 [INSTALL.ko.md](./INSTALL.ko.md), 요약은 각 스킬 매뉴얼 2절.
- **옵션 적용 범위**: 
  - 공통 옵션: `--all` / `--range` / `--files` / `--staged` / `--continue` / `--dialect` / `--lang` / `--version` / `--help` 
  - 튜닝 전용 옵션: `--depth` / `--db` / `--no-state` / `--reset-state`
- **실 DB 접근은 opt-in**: 
  - 두 스킬 모두 기본 실행 시 정적 분석만 수행합니다. (Tier1, Tier2) 
  - `--db <profile>`일 때만 DB에 접근해 `EXPLAIN`(Tier 3)을 실행하며, 이때도 **프로덕션 DB 접근은 차단**되고 **읽기 전용** 쿼리만 수행합니다. 
  - 접속 정보는 환경변수/`.env`로만 들어가며 설정 파일이나 리포트에 남지 않습니다.
- **설정**: `.query-inspector.yml` 파일에 설정값을 지정합니다. 
  - `.query-inspector.example.yml`에서 복사 가능하고, 없어도 기본값으로 동작합니다. 
  - 리포트가 생성되는 디렉토리의 루트는 `report.dir`의 값(기본 `docs/query-inspector`)입니다. 튜닝 리포트는 `tuning-reports/`, 인벤토리는 `inventory-reports/`에 저장됩니다.
- **자동 업데이트**: 두 스킬 모두 실행 시 하루 1회 확인하며, 상세는 각 매뉴얼 8절에 있습니다.

---

## 관련 문서

- **[MANUAL-tuning-report.ko.md](./MANUAL-tuning-report.ko.md)** - 튜닝 사용법 / 옵션 / 3-Tier / Tier 3 실 DB EXPLAIN / 리포트 형식 / 설정 / FAQ
- **[MANUAL-inventory-report.ko.md](./MANUAL-inventory-report.ko.md)** - 인벤토리 사용법 / 옵션 / 카탈로그 파이프라인 / 인덱스 커버리지 / 리포트 형식 / 설정 / FAQ
- **[INSTALL.ko.md](./INSTALL.ko.md)** - 플러그인 vs 스킬 / 수동 설치 / 설치 확인

전체 휴리스틱 카탈로그와 설계는 `references/`와 [DESIGN.md](./DESIGN.md)를 참고하세요.

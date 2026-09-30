# 내부 배포판 동기화 (public -> internal)

이 디렉토리는 **공개판(upstream, 이 저장소)** 에서 **내부 배포판(downstream)** 을 생성하기 위한 유지보수용 도구입니다. 자체 마켓플레이스로 배포하는 조직이 공개판을 그대로 따라가되, 네임스페이스/저장소 URL 등 조직 고유값만 갈아끼우기 위한 것입니다.

## 원칙

- **공개판이 유일한 개발 소스(source of truth).** 모든 기능/버그픽스는 공개판에서.
- **내부 배포판은 공개판에서 생성되는 산출물.** 내부 저장소를 직접 고치지 않습니다(고치면 다음 생성에 덮임). 조직 고유 요소는 아래 프로파일로만 주입합니다.
- 방향: **글로벌 우선 -> 내부 동기화.**

## 처리 파이프라인 (`build-internal.py`)

공개판 트리 + `sync/internal.profile` -> 내부 배포판 트리:

1. **복사** - 공개판 트리를 출력 디렉토리로 복사(EXCLUDE 제외).
2. **언어 승격** - `README.ko.md`->`README.md`, `MANUAL.ko.md`->`MANUAL.md`, 스킬별 매뉴얼(`MANUAL-tuning-report.ko.md`/`MANUAL-inventory-report.ko.md`)과 `INSTALL.ko.md`도 동일(내부 배포판은 한국어 단일). 상단 언어 스위처 줄 제거.
3. **치환** - `internal.profile`의 `공개값 ||| 내부값` 매핑을 전 파일에 적용(긴 값 먼저).
4. **네임스페이스** - 소문자 `query-inspector`(호출표기/플러그인 참조/매니페스트 `name`/설치 스크립트/서술문)를 `@PLUGIN_NAMESPACE`로 전량 치환. `displayName`("Query Inspector")/스킬명(`tuning-report`/`inventory-report`)은 유지.
5. **점검** - 공개값/미해결 placeholder 잔존 여부를 리포트로 출력.

산출물은 출력 디렉토리에 **생성만** 합니다. 내부 저장소 반영(커밋/push)은 사람이 diff 확인 후 수행합니다.

## 무엇이 어떻게 바뀌나

| 처리 | 대상 | 방법 |
|---|---|---|
| **치환** | `scripts/**`/`references/**`/`assets/help.md`/`.query-inspector.example.yml`/`.claude-plugin/*`/`skills/**/SKILL.md`/설치 스크립트 | `internal.profile`의 값 매핑 + 네임스페이스 |
| **언어 승격** | `README.md`/`MANUAL.md`/`MANUAL-*-report.md`/`INSTALL.md` | 영어 원본을 제외하고 `*.ko.md`를 기본 문서로 승격, 스위처 줄 제거 |
| **제외** | `LICENSE`/`CONTRIBUTING.md`/`*.ko.md`(승격 후 원본)/`sync/` 자신/`.git` | 내부 배포판에 포함하지 않음 |

> 문서를 승격 방식으로 처리하는 이유: 내부 배포판은 **한국어 단일**이라, 영어/한국어 2본 + 스위처를 그대로 둘 필요가 없기 때문입니다. `help.md`는 런타임에 `report.language`로 렌더되므로 치환(공통)만으로 충분합니다.

## 사용법

```bash
cp sync/internal.profile.example sync/internal.profile     # 최초 1회, 값 입력
python3 sync/build-internal.py --out /tmp/qi-internal                    # 생성
python3 sync/build-internal.py --out /tmp/qi-internal --diff <현_내부판경로>   # 생성 + 파일목록 대조
```

- `internal.profile` 형식은 `internal.profile.example` 주석 참고.
- 종료 코드: `0` 정상, `2` 프로파일/입력 오류.
- `--diff`는 현 내부 배포판과 파일 목록 차이를 참고용으로 보여줍니다(공개판 신기능으로 인한 차이는 정상).

## 검증

생성 후 스크립트가 자동으로 **공개값/placeholder 잔존**을 점검합니다(`jogakdal`/`github.com/jogakdal`/`query-inspector-marketplace`/`<<...>>`). "✅ 공개값/placeholder 잔존 없음"이 나와야 합니다. 추가로 현 내부 배포판을 정답지로 `--diff` 대조를 권장합니다.

## 보안

- `sync/internal.profile`은 **조직 고유값**을 담으므로 **공개 저장소에 커밋 금지**(`.gitignore` 등록됨). 공개판에는 값 없는 `internal.profile.example`만 둡니다.

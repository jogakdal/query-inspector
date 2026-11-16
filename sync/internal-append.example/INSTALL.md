<!--
internal-append/ 사용법: 이 디렉토리의 파일 내용이, 같은 상대경로의 생성 문서(승격/네임스페이스 치환 후) 끝에 덧붙습니다.
사내 전용으로만 필요한 안내(구 버전 재설치 등)를 공개판 문서를 건드리지 않고 사내판에만 추가할 때 씁니다.
파일명은 대상 문서의 "생성 후" 이름을 씁니다(예: INSTALL.ko.md는 승격되어 INSTALL.md가 되므로 INSTALL.md).
아래는 예시 틀입니다. sync/internal-append/INSTALL.md 로 복사해 사내 실제 식별자로 채우세요.
-->

---

## 기존 설치자 재설치 (구 버전 사용 중인 경우)

구 버전을 설치해 둔 경우, 플러그인 이름/마켓이 바뀌었으면 자동 갱신으로 반영되지 않습니다. 구 버전을 제거한 뒤 위 설치 절차로 다시 설치해 주세요.

```bash
# 1) 구 플러그인 제거
claude plugin uninstall <OLD_PLUGIN>@<OLD_MARKET>

# 2) 구 마켓플레이스 제거
claude plugin marketplace remove <OLD_MARKET>

# 3) 신규 설치 (위 설치 절차와 동일)
```

- 호출/설정 파일/리포트 경로가 바뀐 경우 함께 안내하세요.

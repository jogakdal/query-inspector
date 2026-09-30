@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

rem ─────────────────────────────────────────────────────────────
rem query-inspector 설치 스크립트 (Windows) — query-inspector-setup.sh의 .bat 버전.
rem 기본은 플러그인 설치(마켓 대행), --skill 옵션은 스킬 직접 설치(파일 없으면 자동 clone).
rem 네임스페이스/저장소를 바꿀 때는 이 블록과 매니페스트를 함께 수정합니다.
rem   PLUGIN_NAME : 플러그인 네임스페이스(.claude-plugin/plugin.json "name"과 일치)
rem                 호출은 /<PLUGIN_NAME>:tuning-report · /<PLUGIN_NAME>:inventory-report
rem   MARKET_NAME : .claude-plugin/marketplace.json 최상위 "name"과 일치
rem   INSTALL_DIR : 스킬 직접 설치 시 ~/.claude/skills/ 아래 디렉토리명(플러그인 루트 전체를 복사)
rem   REPO_URL    : 마켓 소스 / 스킬 clone 소스 (환경변수 QT_REPO_URL로 덮어쓰기 가능)
rem ─────────────────────────────────────────────────────────────

set "REPO_URL=git@github.com:jogakdal/query-inspector.git"
if defined QT_REPO_URL set "REPO_URL=%QT_REPO_URL%"
set "PLUGIN_NAME=query-inspector"
set "MARKET_NAME=query-inspector-marketplace"
set "INSTALL_DIR=query-inspector"
set "COMPONENTS=skills .claude-plugin references scripts assets .query-inspector.example.yml"

set "MODE=plugin"
set "SCOPE=global"
set "PROJECT_DIR=."
set "FORCE=0"

:parse
if "%~1"=="" goto endparse
if /i "%~1"=="--skill"   ( set "MODE=skill"   & shift & goto parse )
if /i "%~1"=="--plugin"  ( set "MODE=plugin"  & shift & goto parse )
if /i "%~1"=="--global"  ( set "SCOPE=global" & shift & goto parse )
if /i "%~1"=="--project" (
  set "SCOPE=project"
  set "next=%~2"
  if defined next if not "!next:~0,1!"=="-" ( set "PROJECT_DIR=%~2" & shift )
  shift & goto parse
)
if /i "%~1"=="--force"   ( set "FORCE=1" & shift & goto parse )
if /i "%~1"=="-f"        ( set "FORCE=1" & shift & goto parse )
if /i "%~1"=="--help"    goto usage
if /i "%~1"=="-h"        goto usage
echo error: 알 수 없는 옵션: %~1  ^(사용법은 --help^)
exit /b 1
:endparse

if "%MODE%"=="skill" ( call :install_skill ) else ( call :install_plugin )
exit /b %errorlevel%

:usage
echo query-inspector 설치 스크립트 ^(Windows^)
echo.
echo 사용법:
echo   query-inspector-setup.bat                          플러그인 설치^(기본·개인 글로벌^). 호출: /%PLUGIN_NAME%:tuning-report · :inventory-report
echo   query-inspector-setup.bat --project [DIR]          플러그인 설치^(프로젝트 로컬^). 대상 프로젝트 루트에서 실행^(DIR로 지정 가능^)
echo   query-inspector-setup.bat --skill                  스킬 직접 설치^(개인 글로벌, 멀티스킬 전체 복사^)
echo   query-inspector-setup.bat --skill --project [DIR]  스킬 직접 설치^(프로젝트 로컬^)
echo   query-inspector-setup.bat --skill --force          기존 설치를 확인 없이 덮어씀
echo   query-inspector-setup.bat --help                   이 도움말
echo.
echo 플러그인 방식^(권장^): claude CLI + git 인증 필요. 이 파일 하나만 있어도 동작^(마켓에서 내려받음^).
echo 스킬 방식:          로컬에 파일이 없으면 저장소를 자동 clone해 복사합니다^(멀티스킬 직접 설치는 실동작 확인 필요^).
exit /b 0

rem ───────── 플러그인 방식 (기본) ─────────
:install_plugin
where claude >nul 2>nul
if errorlevel 1 ( echo error: claude CLI가 필요합니다^(플러그인 설치^). 스킬 방식은 --skill 을 쓰세요. & exit /b 1 )
set "CLAUDE_SCOPE=user"
if "%SCOPE%"=="project" set "CLAUDE_SCOPE=local"
echo 플러그인 방식으로 설치합니다 ^(마켓: %MARKET_NAME%, scope: %CLAUDE_SCOPE%^)
claude plugin marketplace list 2>nul | findstr /C:"%MARKET_NAME%" >nul
if errorlevel 1 (
  echo   - 마켓 등록: %REPO_URL%
  claude plugin marketplace add "%REPO_URL%"
  if errorlevel 1 ( echo error: 마켓 등록 실패 — git 인증^(SSH 키/App Password^)·저장소 접근 권한 확인 & exit /b 1 )
) else (
  echo   - 마켓이 이미 등록됨 → 갱신
  claude plugin marketplace update "%MARKET_NAME%" >nul 2>nul
)
echo   - 플러그인 설치: %PLUGIN_NAME%@%MARKET_NAME% ^(scope: %CLAUDE_SCOPE%^)
if "%CLAUDE_SCOPE%"=="local" (
  if not exist "%PROJECT_DIR%" ( echo error: 프로젝트 디렉토리가 없습니다: %PROJECT_DIR% & exit /b 1 )
  pushd "%PROJECT_DIR%"
  claude plugin install "%PLUGIN_NAME%@%MARKET_NAME%" -y --scope local
  set "rc=!errorlevel!"
  popd
  if not "!rc!"=="0" ( echo error: 플러그인 설치 실패 & exit /b 1 )
) else (
  claude plugin install "%PLUGIN_NAME%@%MARKET_NAME%" -y --scope user
  if errorlevel 1 ( echo error: 플러그인 설치 실패 & exit /b 1 )
)
echo.
echo [OK] 설치 완료 — 새 세션에서  /%PLUGIN_NAME%:tuning-report  또는  /%PLUGIN_NAME%:inventory-report  로 호출하세요.
echo      갱신: claude plugin update %PLUGIN_NAME%@%MARKET_NAME% ^(적용에 재시작^)     제거: claude plugin uninstall %PLUGIN_NAME%@%MARKET_NAME%
exit /b 0

rem ───────── 스킬 방식 (--skill) ─────────
:install_skill
set "SRC=%~dp0"
set "TMP="
if not exist "%SRC%skills" (
  where git >nul 2>nul
  if errorlevel 1 ( echo error: git이 필요합니다^(스킬 파일이 없어 clone 필요^). & exit /b 1 )
  set "TMP=%TEMP%\qtskill_%RANDOM%%RANDOM%"
  echo 스킬 파일이 없어 저장소를 clone합니다: %REPO_URL%
  git clone --depth 1 "%REPO_URL%" "!TMP!" >nul 2>nul
  if errorlevel 1 ( echo error: clone 실패 — git 인증·접근 권한 확인 & exit /b 1 )
  set "SRC=!TMP!\"
)
if not exist "!SRC!skills" ( echo error: skills\ 를 찾을 수 없습니다: !SRC! & call :cleanup & exit /b 1 )

if "%SCOPE%"=="project" (
  if not exist "%PROJECT_DIR%" ( echo error: 프로젝트 디렉토리가 없습니다: %PROJECT_DIR% & call :cleanup & exit /b 1 )
  set "DEST=%PROJECT_DIR%\.claude\skills\%INSTALL_DIR%"
) else (
  set "DEST=%USERPROFILE%\.claude\skills\%INSTALL_DIR%"
)

if exist "!DEST!" (
  if "%FORCE%"=="0" (
    set /p "yn=이미 설치돼 있습니다: !DEST!  덮어쓸까요? [y/N]: "
    if /i not "!yn!"=="y" ( echo 취소되었습니다. & call :cleanup & exit /b 1 )
  )
  rmdir /s /q "!DEST!"
)
mkdir "!DEST!"
for %%C in (%COMPONENTS%) do (
  if exist "!SRC!%%C\" (
    robocopy "!SRC!%%C" "!DEST!\%%C" /E /NFL /NDL /NJH /NJS /NP >nul
  ) else if exist "!SRC!%%C" (
    copy /y "!SRC!%%C" "!DEST!\" >nul
  ) else (
    echo   구성 요소 누락^(건너뜀^): %%C
  )
)
rem self-update 버전 기준 기록(매니페스트 version에서 파생)
python -c "import json;open(r'!DEST!\.qt-version','w').write(json.load(open(r'!SRC!.claude-plugin\plugin.json'))['version'])" 2>nul
call :cleanup
echo.
echo [OK] 설치 완료: !DEST!
echo      새 세션에서  /%INSTALL_DIR%:tuning-report  또는  /%INSTALL_DIR%:inventory-report  로 호출하세요.
echo      ^(멀티스킬 직접 설치는 실동작 확인이 필요합니다 — 안 되면 플러그인 방식을 쓰세요.^)
if "%SCOPE%"=="project" echo      이 프로젝트에서만 사용됩니다^(다른 프로젝트엔 영향 없음^).
exit /b 0

:cleanup
if defined TMP if exist "%TMP%" rmdir /s /q "%TMP%"
exit /b 0

@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

rem ─────────────────────────────────────────────────────────────
rem query-inspector 설치 스크립트 (Windows, 플러그인 전용) — query-inspector-setup.sh의 .bat 버전.
rem 멀티스킬(tuning-report + inventory-report) + 공유 자산 + /query-inspector: 네임스페이스 구조라
rem 플러그인 방식으로만 설치한다(스킬 직접 복사는 구조/네임스페이스/경로가 맞지 않아 미지원).
rem   PLUGIN_NAME : 플러그인 네임스페이스(.claude-plugin/plugin.json "name"과 일치)
rem   MARKET_NAME : .claude-plugin/marketplace.json 최상위 "name"과 일치
rem   REPO_URL    : 마켓 소스(원격). 환경변수 QT_REPO_URL로 덮어쓰기 가능
rem ─────────────────────────────────────────────────────────────

set "REPO_URL=git@github.com:jogakdal/query-inspector.git"
if defined QT_REPO_URL set "REPO_URL=%QT_REPO_URL%"
set "PLUGIN_NAME=query-inspector"
set "MARKET_NAME=query-inspector-marketplace"

set "SCOPE=global"
set "PROJECT_DIR=."
set "USE_LOCAL=0"

:parse
if "%~1"=="" goto endparse
if /i "%~1"=="--global"  ( set "SCOPE=global" & shift & goto parse )
if /i "%~1"=="--local"   ( set "USE_LOCAL=1" & shift & goto parse )
if /i "%~1"=="--project" (
  set "SCOPE=project"
  set "next=%~2"
  if defined next if not "!next:~0,1!"=="-" ( set "PROJECT_DIR=%~2" & shift )
  shift & goto parse
)
if /i "%~1"=="--help"    goto usage
if /i "%~1"=="-h"        goto usage
echo error: 알 수 없는 옵션: %~1  ^(사용법은 --help^)
exit /b 1
:endparse

call :install_plugin
exit /b %errorlevel%

:usage
echo query-inspector 설치 스크립트 ^(Windows, 플러그인 전용^)
echo.
echo 사용법:
echo   query-inspector-setup.bat                   플러그인 설치^(개인 글로벌^). 호출: /%PLUGIN_NAME%:tuning-report · :inventory-report
echo   query-inspector-setup.bat --project [DIR]   플러그인 설치^(프로젝트 로컬^). 대상 프로젝트 루트에서 실행^(DIR로 지정 가능^)
echo   query-inspector-setup.bat --local           이 로컬 체크아웃을 마켓 소스로 사용^(clone/포크/오프라인/검증^)
echo   query-inspector-setup.bat --help            이 도움말
echo.
echo 이 스킬은 플러그인 방식으로만 설치합니다^(멀티스킬 + 공유 자산 + 네임스페이스 구조라 스킬 직접 설치는 불가^).
echo 기본은 마켓^(%REPO_URL%^)에서 받아 설치하고, --local은 이 스크립트가 있는 로컬 체크아웃을 마켓으로 등록해 설치합니다.
exit /b 0

rem ───────── 플러그인 설치 ─────────
:install_plugin
where claude >nul 2>nul
if errorlevel 1 ( echo error: claude CLI가 필요합니다^(플러그인 설치^). & exit /b 1 )
set "CLAUDE_SCOPE=user"
if "%SCOPE%"=="project" set "CLAUDE_SCOPE=local"

rem 마켓 소스: 기본=원격 REPO_URL, --local=이 스크립트 디렉토리(로컬 마켓)
set "MARKET_SRC=%REPO_URL%"
if "%USE_LOCAL%"=="1" (
  if not exist "%~dp0.claude-plugin\marketplace.json" ( echo error: 로컬 마켓 소스가 아닙니다^(.claude-plugin\marketplace.json 없음^): %~dp0 & exit /b 1 )
  set "MARKET_SRC=%~dp0"
)

echo 플러그인 설치 ^(마켓: %MARKET_NAME%, 소스: !MARKET_SRC!, scope: %CLAUDE_SCOPE%^)
claude plugin marketplace list 2>nul | findstr /C:"%MARKET_NAME%" >nul
if errorlevel 1 (
  echo   - 마켓 등록: !MARKET_SRC!
  claude plugin marketplace add "!MARKET_SRC!"
  if errorlevel 1 ( echo error: 마켓 등록 실패 — git 인증^(원격^)·경로^(로컬^) 확인 & exit /b 1 )
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

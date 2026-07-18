@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0APLICAR_SPRINT_7_2.ps1"
if errorlevel 1 (
  echo.
  echo ERRO: a Sprint 7.2 nao foi aplicada.
  pause
  exit /b 1
)
echo.
pause

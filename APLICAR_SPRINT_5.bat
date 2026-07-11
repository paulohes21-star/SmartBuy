@echo off
setlocal
cd /d "%~dp0"
title SmartBuy - Aplicar Sprint 5

echo ==========================================
echo       SMARTBUY - APLICAR SPRINT 5
echo ==========================================
echo.

set "PY="
where py >nul 2>nul
if %errorlevel%==0 set "PY=py -3"

if not defined PY (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY=python"
)

if not defined PY (
  echo Python nao encontrado.
  pause
  exit /b 1
)

%PY% aplicar_sprint_5.py
if errorlevel 1 (
  echo.
  echo A Sprint 5 nao foi aplicada.
  echo Fotografe as ultimas linhas desta janela.
  pause
  exit /b 1
)

echo.
echo Sprint 5 aplicada com sucesso.
echo Execute INICIAR_SMARTBUY.bat na raiz do projeto.
pause
endlocal

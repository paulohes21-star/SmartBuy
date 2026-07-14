@echo off
setlocal
cd /d "%~dp0"
title SmartBuy - Aplicar Sprint 6.2 Enterprise

echo ==============================================
echo    SMARTBUY - SPRINT 6.2 ENTERPRISE - FASE A
echo ==============================================
echo.

set "PY="
where py >nul 2>nul
if %errorlevel%==0 set "PY=py -3"
if not defined PY (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY=python"
)

if not defined PY (
  echo ERRO: Python nao encontrado.
  pause
  exit /b 1
)

%PY% aplicar_sprint_6_2.py
if errorlevel 1 (
  echo.
  echo A Sprint 6.2 nao foi aplicada.
  echo Fotografe as ultimas linhas desta janela.
  pause
  exit /b 1
)

echo.
echo Sprint 6.2 Enterprise - Fase A aplicada com sucesso.
echo Execute INICIAR_SMARTBUY.bat na raiz do projeto.
pause
endlocal

@echo off
setlocal
cd /d "%~dp0"
title SmartBuy - Servidor Local

echo ==========================================
echo          SMARTBUY - SPRINT 1
echo ==========================================
echo Pasta atual: %CD%
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
  echo Instale Python 3.11 ou superior e marque Add Python to PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual...
  %PY% -m venv .venv
  if errorlevel 1 goto erro
)

echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro

echo.
echo Abrindo http://127.0.0.1:8000
echo MANTENHA ESTA JANELA ABERTA.
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
goto fim

:erro
echo.
echo Ocorreu um erro. Fotografe as ultimas linhas.
pause
exit /b 1

:fim
endlocal

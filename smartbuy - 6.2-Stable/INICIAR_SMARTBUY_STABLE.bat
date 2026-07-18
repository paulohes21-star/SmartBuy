@echo off
setlocal
cd /d "%~dp0"
title SmartBuy Enterprise 6.2 Stable

if not exist .venv (
  py -3 -m venv .venv 2>nul
  if errorlevel 1 python -m venv .venv
)

.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERRO: nao foi possivel instalar as dependencias.
  pause
  exit /b 1
)

start "" http://127.0.0.1:8000/purchasing-intelligence
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
endlocal

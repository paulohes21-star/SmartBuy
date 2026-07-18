@echo off
setlocal
cd /d "%~dp0"

title SmartBuy - Transfer Intelligence 6.6.0
echo ==============================================================
echo SMARTBUY TRANSFER INTELLIGENCE 6.6.0
echo ==============================================================
echo.
echo Execute este arquivo dentro da pasta raiz do SmartBuy.
echo O instalador criara backup antes de qualquer alteracao.
echo.

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE (
  where py >nul 2>nul && set "PYTHON_EXE=py -3"
)
if not defined PYTHON_EXE (
  where python >nul 2>nul && set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
  echo ERRO: Python nao encontrado.
  pause
  exit /b 1
)

%PYTHON_EXE% install_patch.py
if errorlevel 1 (
  echo.
  echo A instalacao falhou. O backup foi restaurado.
  pause
  exit /b 1
)

echo.
echo Modulo instalado.
echo Inicie o SmartBuy normalmente e abra:
echo http://127.0.0.1:8000/transfer-intelligence
echo.
pause
endlocal

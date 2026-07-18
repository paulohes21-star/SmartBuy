@echo off
setlocal
cd /d "%~dp0"
title SmartBuy Hotfix 6.6.1 Premium
echo ================================================================
echo SMARTBUY HOTFIX 6.6.1 - TRANSFER INTELLIGENCE PREMIUM
echo ================================================================
echo.
set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE where py >nul 2>nul && set "PYTHON_EXE=py -3"
if not defined PYTHON_EXE where python >nul 2>nul && set "PYTHON_EXE=python"
if not defined PYTHON_EXE (
 echo Python nao encontrado.
 pause
 exit /b 1
)
%PYTHON_EXE% install_hotfix.py
if errorlevel 1 (
 echo.
 echo Hotfix nao aplicado.
 pause
 exit /b 1
)
echo.
echo Reinicie o SmartBuy e atualize a pagina com CTRL+F5.
pause
endlocal

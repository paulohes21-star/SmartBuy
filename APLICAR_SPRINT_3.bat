@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo       SMARTBUY - APLICAR SPRINT 3
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
  echo Execute este arquivo dentro do projeto SmartBuy que ja possui Python.
  pause
  exit /b 1
)

%PY% aplicar_sprint_3.py
if errorlevel 1 (
  echo.
  echo A Sprint 3 nao foi aplicada.
  echo Leia a mensagem acima e envie uma foto se precisar.
  pause
  exit /b 1
)

echo.
echo Sprint 3 aplicada com sucesso.
echo Agora execute INICIAR_SMARTBUY.bat.
pause
endlocal

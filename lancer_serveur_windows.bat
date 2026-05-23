@echo off
setlocal EnableExtensions
title Vert-Tige - serveur local

cd /d "%~dp0"

if "%VERT_TIGE_PORT%"=="" set "VERT_TIGE_PORT=8000"
if "%VERT_TIGE_HOST%"=="" set "VERT_TIGE_HOST=127.0.0.1"
set "APP_URL=http://%VERT_TIGE_HOST%:%VERT_TIGE_PORT%"

set "PYTHON_CMD="
set "PYTHON_ARGS="
set "BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

python --version >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  py -3 --version >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=py"
    set "PYTHON_ARGS=-3"
  )
)

if not defined PYTHON_CMD (
  if exist "%BUNDLED_PYTHON%" (
    set "PYTHON_CMD=%BUNDLED_PYTHON%"
  )
)

if not defined PYTHON_CMD (
  echo.
  echo Python est introuvable.
  echo Installe Python 3.11 ou plus depuis https://www.python.org/downloads/windows/
  echo puis relance ce fichier.
  echo.
  pause
  exit /b 1
)

if /I "%~1"=="--check" (
  echo Python utilise : "%PYTHON_CMD%" %PYTHON_ARGS%
  exit /b 0
)

echo.
echo Vert-Tige demarre...
echo Site public      : %APP_URL%
echo Administration  : %APP_URL%/admin
echo.
echo Ferme cette fenetre ou appuie sur Ctrl+C pour arreter le serveur.
echo.

start "" "%APP_URL%"
"%PYTHON_CMD%" %PYTHON_ARGS% app.py

echo.
echo Le serveur s'est arrete.
pause

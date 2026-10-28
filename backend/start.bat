@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>nul
cd /d "%~dp0"

rem ===========================================================================
rem  MoodReel backend launcher (Windows)
rem    start.bat            default port 8000, no hot reload
rem    start.bat 8001       custom port
rem    start.bat dev        port 8000 + uvicorn hot reload
rem    start.bat dev 8001   custom port + hot reload
rem
rem  First run creates .venv-win and installs requirements automatically.
rem  An existing .venv with a "bin" folder is a Linux venv and is left alone.
rem ===========================================================================

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "VENV=.venv-win"
set "PORT=8000"
set "RELOAD="

rem ---- parse arguments ------------------------------------------------------
set "ARG1=%~1"
set "ARG2=%~2"
if /i "%ARG1%"=="dev" goto :arg_dev
if not "%ARG1%"=="" set "PORT=%ARG1%"
goto :arg_done
:arg_dev
set "RELOAD=--reload"
if not "%ARG2%"=="" set "PORT=%ARG2%"
:arg_done

rem ---- .env ----------------------------------------------------------------
if exist ".env" goto :env_ok
if not exist ".env.example" goto :env_missing
echo [setup] .env not found, copying from .env.example
copy /y ".env.example" ".env" >nul
goto :env_ok
:env_missing
echo [warn]  neither .env nor .env.example found, using built-in defaults
:env_ok

rem ---- virtualenv ----------------------------------------------------------
set "PY=%VENV%\Scripts\python.exe"
if not exist "%PY%" goto :venv_create

rem venv exists but the previous install may have been interrupted; probe imports
"%PY%" -c "import fastapi, uvicorn, sqlalchemy" >nul 2>nul
if not errorlevel 1 goto :venv_ready
echo [setup] dependencies incomplete, reinstalling
goto :venv_install

:venv_create
if not exist ".venv\bin\python" goto :venv_create2
echo [info]  found a Linux venv at .venv (WSL), keeping it untouched
echo [info]  this script will use a separate Windows venv: %VENV%

:venv_create2
echo [setup] creating Windows venv: %VENV%
py -3.12 -m venv "%VENV%"
if exist "%PY%" goto :venv_install
python -m venv "%VENV%"
if exist "%PY%" goto :venv_install
echo [error] failed to create venv - is Python 3.10+ installed? check with: py -0
goto :fail

:venv_install
echo [setup] installing dependencies, first run only, this takes a few minutes
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt -r requirements-dev.txt
if errorlevel 1 goto :pip_fail
echo [setup] dependencies ready

:venv_ready
rem ---- optional torch ------------------------------------------------------
"%PY%" -c "import torch" >nul 2>nul
if not errorlevel 1 goto :torch_ok
echo [warn]  torch is not installed: /analyze/en will be unavailable.
echo         Chinese analysis, crawl, recommend and auth all work without it.
echo         To enable it, run:
echo           %PY% -m pip install torch --index-url https://download.pytorch.org/whl/cpu
:torch_ok

rem ---- address hint --------------------------------------------------------
echo.
echo ============================================================
echo  MoodReel backend  -  listening on port %PORT%
echo    local  : http://127.0.0.1:%PORT%
echo    docs   : http://127.0.0.1:%PORT%/docs
echo    health : http://127.0.0.1:%PORT%/health
echo  LAN address for the App settings page:
ipconfig | findstr /i "IPv4"
echo ============================================================
echo.

rem ---- run -----------------------------------------------------------------
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% %RELOAD%
if errorlevel 1 goto :run_fail
goto :eof

:run_fail
echo.
echo [error] server exited unexpectedly.
echo         If the port is taken, try another one: start.bat 8001
echo         Runtime logs are under backend\logs\
goto :eof

:pip_fail
echo [error] pip install failed - check your network or configure a pip mirror.

:fail
endlocal
exit /b 1

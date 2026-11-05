@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "PYTHON=%cd%\.venv-web\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [error] .venv-web Python not found. See src\README.md
    pause
    exit /b 1
)

"%PYTHON%" "%cd%\scripts\ask_assist.py" %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" pause
if "%~1"=="" if "%ERR%"=="0" pause
exit /b %ERR%

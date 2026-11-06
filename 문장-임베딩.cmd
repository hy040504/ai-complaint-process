@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHON=%cd%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [error] .venv Python not found. See rag\README.md
    pause
    exit /b 1
)
chcp 65001 >nul
"%PYTHON%" "%cd%\scripts\문장_임베딩.py" %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" pause
if "%~1"=="" if "%ERR%"=="0" pause
exit /b %ERR%

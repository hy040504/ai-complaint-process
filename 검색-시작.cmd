@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHON=%cd%\.venv-web\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [error] .venv-web Python not found. See src\README.md
    pause
    exit /b 1
)
chcp 65001 >nul
"%PYTHON%" "%cd%\scripts\검색_시작.py"
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" pause
exit /b %ERR%

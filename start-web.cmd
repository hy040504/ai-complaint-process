@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON=%cd%\.venv-web\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [error] .venv-web Python not found. See src\README.md
    pause
    exit /b 1
)

"%PYTHON%" "%cd%\scripts\start_web.py"
if errorlevel 1 pause
exit /b %ERRORLEVEL%

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
echo.
echo PostgreSQL과 검색 API는 각자 창에서 유지됩니다.
echo 이 창은 상태만 보여 줍니다. 닫으려면 키를 누르세요.
pause
exit /b %ERR%

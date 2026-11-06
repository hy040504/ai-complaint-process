@echo off
setlocal EnableExtensions EnableDelayedExpansion
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
if "%~1"=="" (
    echo 한 문장을 임베딩한 뒤 pgvector로 비슷한 FAQ와 공개 사례를 찾습니다.
    set /p "SENTENCE=임베딩할 문장: "
    "%PYTHON%" "%cd%\scripts\문장_임베딩.py" "!SENTENCE!"
) else (
    "%PYTHON%" "%cd%\scripts\문장_임베딩.py" %*
)
set "ERR=!ERRORLEVEL!"
echo.
if "!ERR!"=="0" (
    echo 벡터 출력이 끝났습니다. 이 창을 닫으려면 키를 누르세요.
) else (
    echo 임베딩이 끝나지 않았습니다. 메시지를 확인한 뒤 키를 누르세요.
)
pause
exit /b !ERR!

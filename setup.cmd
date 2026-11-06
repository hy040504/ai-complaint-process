@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "BOOTSTRAP="
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "BOOTSTRAP=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined BOOTSTRAP if exist "%LocalAppData%\Programs\Python\Launcher\py.exe" set "BOOTSTRAP=%LocalAppData%\Programs\Python\Launcher\py.exe"
if not defined BOOTSTRAP if exist "%cd%\.venv\Scripts\python.exe" set "BOOTSTRAP=%cd%\.venv\Scripts\python.exe"
if not defined BOOTSTRAP if exist "%cd%\.venv-web\Scripts\python.exe" set "BOOTSTRAP=%cd%\.venv-web\Scripts\python.exe"
if not defined BOOTSTRAP (
    where py >nul 2>&1
    if not errorlevel 1 set "BOOTSTRAP=py"
)
if not defined BOOTSTRAP (
    echo [error] Python 3.12 not found. Install Python 3.12, then run setup.cmd again.
    pause
    exit /b 1
)
if /I "%BOOTSTRAP:~-6%"=="py.exe" (
    "%BOOTSTRAP%" -3.12 "%cd%\scripts\setup_env.py" %*
) else if /I "%BOOTSTRAP%"=="py" (
    py -3.12 "%cd%\scripts\setup_env.py" %*
) else (
    "%BOOTSTRAP%" "%cd%\scripts\setup_env.py" %*
)
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" pause
if "%~1"=="" if "%ERR%"=="0" pause
exit /b %ERR%

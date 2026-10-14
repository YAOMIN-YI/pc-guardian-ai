@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -e ".[test]" -c constraints-windows.txt
if errorlevel 1 goto fail
echo Setup complete. Open Run-Demo.cmd to start.
pause
exit /b 0
:fail
echo Setup failed. Install 64-bit Python 3.11 or newer and check network access.
pause
exit /b 1


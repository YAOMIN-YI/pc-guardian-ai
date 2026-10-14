@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please run Setup.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -e ".[build]" -c constraints-windows.txt
if errorlevel 1 exit /b 1
rem Prevent unrelated tools on PATH from supplying incompatible ICU/Qt DLLs.
set "PATH=%CD%\.venv\Scripts;%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0"
".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm --onedir --console --name PCGuardianAI --paths . --collect-data app --hidden-import win32evtlog --hidden-import pywintypes app\__main__.py
if errorlevel 1 exit /b 1
copy /y "packaging\windows\*" "dist\PCGuardianAI\" >nul
echo Copy the entire dist\PCGuardianAI directory to USB. Start PCGuardianAI.exe --demo for simulation.
pause


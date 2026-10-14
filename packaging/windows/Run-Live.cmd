@echo off
setlocal
cd /d "%~dp0"
PCGuardianAI.exe
if errorlevel 1 pause


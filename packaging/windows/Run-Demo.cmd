@echo off
setlocal
cd /d "%~dp0"
PCGuardianAI.exe --demo
if errorlevel 1 pause


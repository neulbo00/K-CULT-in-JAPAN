@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set "LOG=%~dp0logs\sync.log"
echo ==== %DATE% %TIME% ====>> "%LOG%"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (py -3 sync_notion.py >> "%LOG%" 2>&1) else (python sync_notion.py >> "%LOG%" 2>&1)
exit /b %ERRORLEVEL%

@echo off
setlocal
call "%~dp0Stop Usage Bar.cmd"
if errorlevel 1 exit /b 1
timeout /t 3 /nobreak >nul
call "%~dp0Start Usage Bar.cmd"

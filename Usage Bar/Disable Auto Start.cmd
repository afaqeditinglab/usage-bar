@echo off
setlocal
call "%~dp0python-path.cmd"
if errorlevel 1 exit /b 1
"%USAGE_BAR_PYTHON%" -B "%~dp0usage_bar.py" startup disable
pause

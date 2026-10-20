@echo off
setlocal
call "%~dp0python-path.cmd"
if errorlevel 1 (
  pause
  exit /b 1
)
"%USAGE_BAR_PYTHON%" -B "%~dp0check_setup.py"
set "CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %CHECK_RESULT%

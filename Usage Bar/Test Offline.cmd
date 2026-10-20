@echo off
setlocal
call "%~dp0python-path.cmd"
if errorlevel 1 exit /b 1
"%USAGE_BAR_PYTHON%" -B "%~dp0test_release.py"
set "CHECK_RESULT=%ERRORLEVEL%"
pause
exit /b %CHECK_RESULT%

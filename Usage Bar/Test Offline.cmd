@echo off
setlocal
call "%~dp0python-path.cmd"
if errorlevel 1 exit /b 1
"%USAGE_BAR_PYTHON%" -B "%~dp0test_release.py"
set "CHECK_RESULT=%ERRORLEVEL%"
if not "%CHECK_RESULT%"=="0" goto finish
"%USAGE_BAR_PYTHON%" -B "%~dp0test_foreground.py"
set "CHECK_RESULT=%ERRORLEVEL%"
if not "%CHECK_RESULT%"=="0" goto finish
"%USAGE_BAR_PYTHON%" -B "%~dp0test_job_events.py"
set "CHECK_RESULT=%ERRORLEVEL%"
:finish
pause
exit /b %CHECK_RESULT%

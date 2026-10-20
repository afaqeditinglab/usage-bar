@echo off
setlocal
call "%~dp0python-path.cmd"
if errorlevel 1 exit /b 1
"%USAGE_BAR_PYTHON%" -B "%~dp0usage_bar.py" startup enable
if errorlevel 1 (
  echo Automatic startup could not be enabled. No launch has been attempted.
  pause
  exit /b 1
)
call "%~dp0Stop Usage Bar.cmd"
timeout /t 2 /nobreak >nul
call "%~dp0Start Usage Bar.cmd"
echo Usage Bar will now start when you sign in to Windows. Use ChatGPT's normal icon.
pause

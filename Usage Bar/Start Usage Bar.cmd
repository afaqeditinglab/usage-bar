@echo off
setlocal
call "%~dp0python-path.cmd"
if errorlevel 1 exit /b 1
for %%P in ("%USAGE_BAR_PYTHON%") do set "USAGE_BAR_PYTHONW=%%~dpPpythonw.exe"
if not exist "%USAGE_BAR_PYTHONW%" (
  echo pythonw.exe was not found beside Python. Nothing was installed.
  exit /b 1
)
cd /d "%~dp0"
start "" /b "%USAGE_BAR_PYTHONW%" -B "%~dp0usage_bar.py" ui

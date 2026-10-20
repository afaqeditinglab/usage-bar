@echo off
if defined USAGE_BAR_PYTHON if not exist "%USAGE_BAR_PYTHON%" (
  echo USAGE_BAR_PYTHON does not point to an existing Python executable.
  exit /b 1
)
if not defined USAGE_BAR_PYTHON if exist "%~dp0runtime\python.exe" set "USAGE_BAR_PYTHON=%~dp0runtime\python.exe"
if not defined USAGE_BAR_PYTHON for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined USAGE_BAR_PYTHON set "USAGE_BAR_PYTHON=%%P"
if not defined USAGE_BAR_PYTHON (
  echo Python was not found. Read docs/SETUP.md for prerequisites.
  echo Nothing has been downloaded or installed.
  exit /b 1
)
set "TEMP=%~dp0tmp"
set "TMP=%~dp0tmp"
set "PYTHONDONTWRITEBYTECODE=1"
if not exist "%TEMP%" mkdir "%TEMP%"
exit /b 0

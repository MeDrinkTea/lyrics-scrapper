@echo off
setlocal
cd /d "%~dp0"
title Lyrics ripper

set "PY="
set "PYW="

rem Prefer the interpreter on PATH: it is the one with the dependencies.
where python >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    set "PYW=pythonw"
) else (
    where py >nul 2>nul
    if errorlevel 1 goto nopython
    set "PY=py -3"
    set "PYW=pyw -3"
)

%PY% -c "import requests, bs4" >nul 2>nul
if not errorlevel 1 goto launch

echo Installing dependencies...
%PY% -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto pipfail

:launch
start "" %PYW% gui.py
exit /b 0

:nopython
echo.
echo Python 3.9+ not found.
echo Install it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during setup.
echo.
pause
exit /b 1

:pipfail
echo.
echo Could not install dependencies. Run manually:
echo     pip install -r requirements.txt
echo.
pause
exit /b 1

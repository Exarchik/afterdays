@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 afterdays.py %*
goto done
:use_python
where python >nul 2>nul
if errorlevel 1 goto missing
python afterdays.py %*
goto done
:missing
echo Python was not found. Install Python 3.10+ with Tcl/Tk, then run INSTALL_GAME.bat.
pause
exit /b 1
:done
if errorlevel 1 pause
endlocal

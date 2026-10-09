@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 goto use_py
python -c "import tkinter; from PIL import Image, ImageTk" >nul 2>nul
if errorlevel 1 goto use_py
python afterdays.py
goto done
:use_py
where py >nul 2>nul
if errorlevel 1 goto diagnose_python
py -3 afterdays.py
goto done
:diagnose_python
where python >nul 2>nul
if errorlevel 1 goto missing
python afterdays.py
goto done
:missing
echo Python was not found. Install Python 3.10+ with Tcl/Tk and add it to PATH.
pause
exit /b 1
:done
if errorlevel 1 pause
endlocal

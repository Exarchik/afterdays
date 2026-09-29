@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 event_editor.py
    goto done
)
where python >nul 2>nul
if not errorlevel 1 (
    python event_editor.py
    goto done
)
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" event_editor.py
    goto done
)
echo Python was not found. Install Python 3.10+ with Tcl/Tk and add it to PATH.
pause
exit /b 1
:done
if errorlevel 1 pause
endlocal

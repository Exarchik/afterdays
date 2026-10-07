@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 -m pip install -r requirements-game.txt
goto done
:use_python
python -m pip install -r requirements-game.txt
:done
if errorlevel 1 (
  echo Installation failed. See the error above.
  pause
  exit /b 1
)
echo Arcade installed. Start the game with START_WINDOWS.bat.
pause
endlocal

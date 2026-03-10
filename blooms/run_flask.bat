@echo off
cd /d "%~dp0"
echo Blooms - Flask (prihlaseni funguje)
echo Port 5000 - pokud 8000 nejde, pouzije se 5000
echo.
call venv\Scripts\activate.bat
python run_flask.py
pause

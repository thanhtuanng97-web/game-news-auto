@echo off
echo Dang cai thu vien...
pip install flask flask-cors feedparser trafilatura -q
echo.
echo Khoi dong server...
start "" "app.html"
python server.py
pause

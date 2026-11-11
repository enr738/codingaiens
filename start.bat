@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting Coding AI Server with Permanent SQLite Database...
start "" http://localhost:3000
python server.py
pause


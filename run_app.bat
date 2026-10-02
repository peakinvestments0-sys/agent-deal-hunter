@echo off
title AGENT DEAL HUNTER - Florida Off-Market Pocket Finder
cd /d "%~dp0"
echo ========================================================
echo  STARTING AGENT DEAL HUNTER
echo  Realtor Off-Market and Pocket Listing Engine
echo ========================================================
echo.
start "" cmd /c "timeout /t 2 /nobreak >nul & start chrome http://127.0.0.1:8001"
python server.py
pause

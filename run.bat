@echo off
title TalentFlow AI - Smart Talent Sourcing Suite
echo ====================================================
echo Starting TalentFlow AI Server...
echo ====================================================
cd /d "%~dp0"
echo Server running at: http://localhost:8080
echo Press Ctrl+C to stop the server at any time.
echo.
python server.py
pause


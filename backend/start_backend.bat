@echo off
cd /d "%~dp0"
echo Starting Backend...
python -m uvicorn main:app --reload
pause

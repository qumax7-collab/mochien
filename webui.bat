@echo off
cd /d C:\mochien
echo Mochien Web UI - http://localhost:8000
venv\Scripts\python -m uvicorn webui:app --reload --port 8000 --host 0.0.0.0
pause

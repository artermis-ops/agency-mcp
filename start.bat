@echo off
cd /d %~dp0
python -m venv venv
call venv\Scripts\activate
pip install fastapi uvicorn requests --quiet >nul
python server.py
pause
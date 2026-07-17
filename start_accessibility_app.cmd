@echo off
set "PYTHON=%~dp0.venv\Scripts\python.exe"
"%PYTHON%" -m streamlit run "%~dp0streamlit_app.py"

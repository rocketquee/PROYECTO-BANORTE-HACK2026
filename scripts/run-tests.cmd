@echo off
rem Ejecuta la suite de pruebas del backend
set ROOT=%~dp0..
cd /d %ROOT%\backend
..\.venv\Scripts\python -m pytest tests -v

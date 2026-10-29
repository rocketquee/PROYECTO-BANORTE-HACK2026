@echo off
rem Detiene backend y frontend de Banorte AI Finanzas
echo Deteniendo procesos...

taskkill /fi "windowtitle eq Banorte Backend*" >nul 2>nul
taskkill /fi "windowtitle eq Banorte Frontend*" >nul 2>nul

rem Respaldo: matar por puerto
for /f "tokens=5" %%p in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /pid %%p /f >nul 2>nul
for /f "tokens=5" %%p in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do taskkill /pid %%p /f >nul 2>nul

echo Listo. Backend (8000) y frontend (3000) detenidos.
pause

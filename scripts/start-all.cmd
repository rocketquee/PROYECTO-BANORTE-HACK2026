@echo off
setlocal enabledelayedexpansion
rem ============================================================
rem  Banorte AI Finanzas - arranca todo con UN solo script
rem  (backend + MCP integrado + frontend + navegador)
rem ============================================================
set ROOT=%~dp0..

rem --- Verificar Python ---
if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo [ERROR] No se encontro Python en .venv.
  echo Instala Python 3.11+ y ejecuta:  python -m venv .venv
  echo y luego:  .venv\Scripts\pip install -r backend\requirements.txt
  pause
  exit /b 1
)

rem --- Verificar Node/npm ---
where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se encontro npm ^(Node.js^).
  echo Instala Node.js 18+ desde https://nodejs.org y vuelve a intentar.
  pause
  exit /b 1
)

rem --- Verificar dependencias del frontend ---
if not exist "%ROOT%\frontend\node_modules" (
  echo Instalando dependencias del frontend ^(primera vez^)...
  pushd "%ROOT%\frontend" && call npm install && popd
)

echo [1/3] Iniciando backend en http://localhost:8000 ...
start "Banorte Backend" /min cmd /c "cd /d %ROOT%\backend && ..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

rem --- Esperar a que el backend responda ---
set /a TRIES=0
:wait_backend
set /a TRIES+=1
if %TRIES% GEQ 60 (
  echo [ERROR] El backend no respondio en 60 segundos. Revisa la ventana "Banorte Backend".
  pause
  exit /b 1
)
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait_backend
)
echo       Backend listo.

echo [2/3] Iniciando frontend en http://localhost:3000 ...
start "Banorte Frontend" /min cmd /c "cd /d %ROOT%\frontend && npm run dev"

set /a TRIES=0
:wait_frontend
set /a TRIES+=1
if %TRIES% GEQ 90 (
  echo [ERROR] El frontend no respondio en 90 segundos. Revisa la ventana "Banorte Frontend".
  pause
  exit /b 1
)
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing http://localhost:3000 -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait_frontend
)
echo       Frontend listo.

echo [3/3] Abriendo el navegador...
start http://localhost:3000

echo.
echo ============================================================
echo  Todo listo:
echo   - Aplicacion: http://localhost:3000
echo   - API:        http://localhost:8000/api/health
echo  Para detener todo, ejecuta scripts\stop-all.cmd
echo ============================================================
pause

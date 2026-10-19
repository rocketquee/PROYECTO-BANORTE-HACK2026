@echo off
rem Inicia backend, frontend y verifica el servidor MCP (3 ventanas)
set ROOT=%~dp0..

start "Backend FastAPI (8000)" cmd /k "cd /d %ROOT%\backend && ..\.venv\Scripts\python -m uvicorn app.main:app --port 8000"
start "Frontend Next.js (3000)" cmd /k "cd /d %ROOT%\frontend && npm run dev"
start "Servidor MCP (prueba manual)" cmd /k "cd /d %ROOT% && .venv\Scripts\python mcp-server\server.py"

echo Ventanas iniciadas:
echo  - Backend:  http://localhost:8000  (docs: /docs)
echo  - Frontend: http://localhost:3000
echo  - MCP: se lanza automaticamente por el backend (stdio);
echo    la tercera ventana solo es para prueba manual del protocolo.

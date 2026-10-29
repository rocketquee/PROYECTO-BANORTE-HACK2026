@echo off
setlocal
set "ROOT=%~dp0.."
pushd "%ROOT%" || exit /b 1

where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 goto :python_missing
  set "PYTHON=python"
) else (
  set "PYTHON=py -3"
)

%PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto :python_version

where node >nul 2>nul
if errorlevel 1 goto :node_missing
node -e "const [major, minor] = process.versions.node.split('.').map(Number); process.exit(major > 18 || (major === 18 && minor >= 18) ? 0 : 1)" >nul 2>nul
if errorlevel 1 goto :node_version

if not exist ".venv\Scripts\python.exe" (
  echo Creando el entorno virtual de Python...
  %PYTHON% -m venv .venv
  if errorlevel 1 goto :venv_failed
)

".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto :venv_version

echo Instalando dependencias del backend...
".venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto :backend_requirements_failed

echo Instalando dependencias del servidor MCP...
".venv\Scripts\python.exe" -m pip install -r "mcp-server\requirements.txt"
if errorlevel 1 goto :mcp_requirements_failed

if not exist ".env" (
  echo Creando .env desde .env.example...
  copy /Y ".env.example" ".env" >nul
  if errorlevel 1 goto :env_copy_failed
) else (
  echo .env ya existe; se conserva sin cambios.
)

echo Instalando dependencias del frontend...
pushd "frontend"
call npm.cmd install
if errorlevel 1 (
  popd
  goto :frontend_install_failed
)
popd

echo.
echo Listo, ejecuta scripts\start-all.cmd
popd
exit /b 0

:python_missing
echo [ERROR] No se encontro Python 3.11 o posterior. Descargalo en https://www.python.org/downloads/windows/
goto :failed

:python_version
echo [ERROR] Se requiere Python 3.11 o posterior. Descargalo en https://www.python.org/downloads/windows/
goto :failed

:node_missing
echo [ERROR] No se encontro Node.js 18.18 o posterior. Descargalo en https://nodejs.org/
goto :failed

:node_version
echo [ERROR] Se requiere Node.js 18.18 o posterior. Descargalo en https://nodejs.org/
goto :failed

:venv_failed
echo [ERROR] No se pudo crear .venv.
goto :failed

:venv_version
echo [ERROR] El Python de .venv es anterior a 3.11. Revisa o recrea .venv manualmente.
goto :failed

:backend_requirements_failed
echo [ERROR] Fallo la instalacion de backend\requirements.txt.
goto :failed

:mcp_requirements_failed
echo [ERROR] Fallo la instalacion de mcp-server\requirements.txt.
goto :failed

:env_copy_failed
echo [ERROR] No se pudo copiar .env.example a .env.
goto :failed

:frontend_install_failed
echo [ERROR] Fallo npm.cmd install en frontend.
goto :failed

:failed
popd
exit /b 1

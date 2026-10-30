# Estructura del proyecto

Organización de carpetas y archivos principales. Se excluyen `node_modules`, `.next`, `.venv`, `__pycache__`, `.git`, `.env` y archivos con claves o secretos.

```mermaid
flowchart TB
    ROOT["proyecto-banorte-ai-finanzas/"]

    ROOT --> FE
    ROOT --> BE
    ROOT --> MCP
    ROOT --> DOCS
    ROOT --> SCRIPTS
    ROOT --> ROOTFILES

    subgraph FE["frontend/ — Next.js 15 + TypeScript + Tailwind"]
        FE_SRC["src/"]
        FE_APP["app/<br/>layout.tsx · page.tsx · globals.css"]
        FE_COMP["components/<br/>AppShell · DashboardView · AgentView · CardsView · TopBar · IconSidebar ..."]
        FE_DYN["components/dynamic/<br/>DynamicRenderer · SpendingChart · BudgetPlanner · CreditSimulator ..."]
        FE_LIB["lib/<br/>api.ts · chatStore.ts · format.ts · navigation.ts · chatSecurity.mjs"]
        FE_HOOKS["hooks/<br/>useReducedMotion.ts"]
        FE_TYPES["types/<br/>contract.ts"]
        FE_TESTS["tests/<br/>assistantExperience.test.mjs · chatSecurity.test.mjs"]
        FE_CFG["package.json · tsconfig.json · tailwind.config.ts · postcss.config.mjs"]

        FE_SRC --> FE_APP
        FE_SRC --> FE_COMP
        FE_SRC --> FE_LIB
        FE_SRC --> FE_HOOKS
        FE_SRC --> FE_TYPES
        FE_COMP --> FE_DYN
    end

    subgraph BE["backend/ — FastAPI + Pydantic + SQLite"]
        BE_APP["app/"]
        BE_MAIN["main.py"]
        BE_API["api/<br/>routes.py"]
        BE_CORE["core/<br/>config.py · database.py · migrate.py · money.py<br/>reconcile.py · seed.py · structured_logging.py"]
        BE_SCHEMAS["schemas/<br/>api.py · ui.py"]
        BE_SERVICES["services/<br/>finance.py · credit.py · savings.py · domain.py · mcp_client.py"]
        BE_AGENT["services/agent/<br/>orchestrator.py · composer.py · providers.py"]
        BE_DATA["data/<br/>banorte.db · backups/"]
        BE_TESTS["tests/<br/>pytest: servicios, contrato UI, MCP, dinero, migración ..."]
        BE_CFG["requirements.txt · pytest.ini"]

        BE_APP --> BE_MAIN
        BE_APP --> BE_API
        BE_APP --> BE_CORE
        BE_APP --> BE_SCHEMAS
        BE_APP --> BE_SERVICES
        BE_SERVICES --> BE_AGENT
    end

    subgraph MCP["mcp-server/ — Servidor MCP (FastMCP, stdio)"]
        MCP_SERVER["server.py"]
        MCP_TOOLS["tools/<br/>finance_tools.py"]
        MCP_CFG["requirements.txt · README.md"]
    end

    subgraph DOCS["docs/ — Documentación técnica y evidencia"]
        DOCS_TECH["ARCHITECTURE.md · DECISIONS.md · DOMAIN.md<br/>DATA-DICTIONARY.md · ESTADO-PROYECTO.md<br/>MIGRACION-FASE1.md · REPORTE-QA.md"]
        DOCS_BIT["bitacora-banorte-ai/<br/>Diario/ · Bitacoras/ · Plantillas/"]
        DOCS_EVI["ui-evidence/<br/>capturas de pantalla"]
    end

    subgraph SCRIPTS["scripts/ — Automatización local"]
        SCRIPTS_FILES["setup.cmd · start-all.cmd<br/>stop-all.cmd · run-tests.cmd"]
    end

    subgraph ROOTFILES["raíz del repositorio"]
        R_README["README.md"]
        R_VERCEL["vercel.json"]
        R_ENV[".env.example<br/>(plantilla sin secretos)"]
        R_GIT[".gitignore"]
        R_GH[".github/skills/archify/<br/>skill de arquitectura"]
    end
```

## Para qué sirve cada carpeta

| Carpeta | Propósito |
| --- | --- |
| `frontend/` | Aplicación web en Next.js 15 + TypeScript + Tailwind. Contiene la UI conversacional y los componentes dinámicos que el agente renderiza. |
| `frontend/src/app/` | Rutas y layout principal de Next.js (`page.tsx`, `layout.tsx`, estilos globales). |
| `frontend/src/components/` | Componentes de interfaz reutilizables (shell, barra superior, sidebar, vistas, tarjetas, animaciones). |
| `frontend/src/components/dynamic/` | Registro de componentes autorizados que el contrato JSON del agente puede renderizar (gráficos, tablas, simuladores, formularios). |
| `frontend/src/lib/` | Lógica del cliente: cliente HTTP, estado del chat, formato de montos, navegación y seguridad del chat. |
| `frontend/src/hooks/` | Hooks personalizados de React (por ejemplo, respeto a movimiento reducido). |
| `frontend/src/types/` | Tipos TypeScript del contrato entre frontend y backend. |
| `frontend/tests/` | Pruebas de la experiencia del asistente y de seguridad del chat. |
| `backend/` | API en FastAPI + Pydantic + SQLite. Orquesta el agente, valida el contrato y expone los endpoints. |
| `backend/app/api/` | Definición de rutas HTTP (incluye `POST /api/agent/chat`). |
| `backend/app/core/` | Infraestructura: configuración, base de datos, migraciones, manejo de dinero, reconciliación, seed y logging estructurado. |
| `backend/app/schemas/` | Modelos Pydantic que validan las respuestas de la API y el contrato de UI. |
| `backend/app/services/` | Lógica de negocio financiera (finanzas, crédito, ahorro, dominio) y cliente MCP. |
| `backend/app/services/agent/` | Núcleo del agente: orquestador, compositor determinista de UI y proveedores de IA. |
| `backend/data/` | Base SQLite sintética (`banorte.db`) y respaldos automáticos. |
| `backend/tests/` | Suite de pytest: cálculos, contrato UI, servicios, MCP, seguridad y migraciones. |
| `mcp-server/` | Servidor MCP independiente (FastMCP, transporte stdio) con las herramientas financieras que consume el backend. |
| `mcp-server/tools/` | Implementación de las herramientas financieras expuestas por MCP. |
| `docs/` | Documentación de arquitectura, decisiones, dominio, diccionario de datos, estado del proyecto y QA. |
| `docs/bitacora-banorte-ai/` | Bitácoras de trabajo, diario y plantillas del proyecto. |
| `docs/ui-evidence/` | Capturas de pantalla que evidencian la interfaz en distintos tamaños. |
| `scripts/` | Scripts `.cmd` para instalar, arrancar, detener y ejecutar pruebas en Windows. |
| `.github/skills/archify/` | Skill/herramienta de apoyo para generar diagramas de arquitectura. |
| `frontend/ui-evidence/` | Evidencia visual adicional del frontend. |
| `.archify/` | Artefactos generados por la herramienta de arquitectura (no forma parte del código de la app). |

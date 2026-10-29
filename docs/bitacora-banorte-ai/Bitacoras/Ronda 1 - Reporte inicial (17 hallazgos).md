---
tags: [bitacora, ronda-1]
fecha: 2026-10-19
herramienta: Verdent (modelo GLM-5.3-Flash gratis, vía OpenRouter)
---
# Ronda 1 · Reporte inicial (17 hallazgos)

## Qué se pidió
Reporte de pruebas con 17 hallazgos (BUG-001 a BUG-017), de severidad Crítico > Alto > Medio > Bajo. Para cada uno: reproducir, explicar causa, corregir, agregar prueba automática y reportar. Entorno: Windows, Chrome, modo demostración.

## Qué entregó Verdent (16:53, trabajó 19 min 35 s)
- 17 de 17 marcados como **corregidos**.
- 152 pruebas de backend pasan (34 originales + 118 nuevas).
- 65 frases de QA ejecutadas, 0 fugas.
- Frontend compila en producción.
- 27 archivos cambiados (+1778 / −292). **Sin commit en Git.**
- Entregables: reporte QA, README y ARQUITECTURA actualizados, `scripts/start-all.cmd` y `stop-all.cmd`.
- Límites que admitió: BUG-002, 010, 015, 016 sin prueba automática; BUG-006 solo por reglas en demo (mejora con `AI_PROVIDER`); concurrencia entre pestañas parcial.

> [!warning] Las pruebas las escribió y corrió la misma IA. Por eso se verificó a mano (ver [[Ronda 2 - Verificacion manual]]).

## Tabla de hallazgos

| ID | Severidad | Qué era | Dijo Verdent | Verificado a mano |
|---|---|---|---|---|
| BUG-001 | 🔴 Crítico | Ignoraba "últimos 4 meses" | Corregido | 🟡 Parcial: la tendencia funciona, pero "categoría en barras" y "línea del tiempo" devuelven la misma tendencia |
| BUG-002 | 🔴 Crítico | Chat se pierde al cambiar de pantalla | Corregido | ⚪ Sin probar |
| BUG-003 | 🔴 Crítico | Fuga técnica (MCP, tool, JSON) | Corregido | 🟢 OK en las respuestas de texto; falta revisar subtítulos de la UI |
| BUG-004 | 🔴 Crítico | Manipulación del prompt | Corregido | 🟢 OK en 2 pruebas; faltan variantes |
| BUG-005 | 🟠 Alto | Resultado duplicado | Corregido | ⚪ Sin probar en pantalla |
| BUG-006 | 🟠 Alto | Lenguaje cotidiano | Corregido (reglas) | 🟡 Parcial: nómina/aguinaldo fallan, "comida" incompleto |
| BUG-007 | 🟠 Alto | Faltan herramientas/componentes | Corregido | 🟡 Parcial: faltan barras por categoría y timeline |
| BUG-008 | 🟠 Alto | Datos sintéticos poco realistas | Corregido | 🟡 Parcial: duplicado Rappi sí; falsos positivos en "inusuales" |
| BUG-009 | 🟠 Alto | Superficie técnica expuesta | Corregido | ⚪ Sin probar (`/docs`, errores) |
| BUG-010 | 🟡 Medio | Accesibilidad | Corregido | ⚪ Sin probar (A-/A/A+, contraste) |
| BUG-011 | 🟡 Medio | Estados intermedios | Corregido | ⚪ Sin probar (cancelar, reintentar) |
| BUG-012 | 🟡 Medio | Formato MX | Corregido | 🔴 Falla: `348.9`, `14800.0`, `$-8,673`, límites sin `$` |
| BUG-013 | 🟡 Medio | Recomendaciones genéricas | Corregido | 🟢 OK: solo si se piden, separa Dato/Sugerencia |
| BUG-014 | 🟡 Medio | Escrituras sin validación | Corregido | ⚪ Sin probar |
| BUG-015 | 🔵 Bajo | Menú lateral incompleto | Corregido | ⚪ Sin probar |
| BUG-016 | 🔵 Bajo | Scripts de inicio | Corregido | ⚪ Sin confirmar |
| BUG-017 | 🔵 Bajo | Identidad y avisos | Corregido | 🔴 Falla: no aclara que es IA/demo |

Leyenda: 🟢 OK · 🟡 Parcial · 🔴 Falla · ⚪ Sin probar

## Resumen
- Verificados OK: 3 (003, 004, 013)
- Parciales: 4 (001, 006, 007, 008)
- Fallan: 2 (012, 017)
- Sin probar: 8

## Siguiente paso
[[Ronda 2 - Verificacion manual]]

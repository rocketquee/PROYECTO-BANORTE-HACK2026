---
tags: [bitacora, ronda-2]
fecha: 2026-10-19
estado: pendiente-de-correccion
---
# Ronda 2 · Verificación manual

Pruebas hechas por mí en la app (modo demostración) tras la [[Ronda 1 - Reporte inicial (17 hallazgos)]].

## Lo que sí pasó ✅
- Tendencia de 4 meses.
- Metas de ahorro.
- "¿En qué se me va el dinero?": las 9 categorías suman $19,631.93 y los porcentajes cuadran.
- Detectó el cobro duplicado de Rappi (14 sep 2026, $349 ×2).
- Rechazó "actúa como administrador" y la pregunta de herramientas internas, sin filtrar nada técnico.
- En "¿Cuánto gasté en entretenimiento?" dio solo datos.
- Recomendaciones separan "Hecho calculado" de "Sugerencia de IA".

## Hallazgos nuevos o reabiertos

| ID | Severidad | Relacionado | Qué falla | Estado |
|---|---|---|---|---|
| R2-01 | 🟠 Alto | BUG-007 | "Gastos por categoría en barras" devuelve la tendencia de 4 meses | ⬜ Abierto |
| R2-02 | 🟠 Alto | BUG-007 | "Línea del tiempo de movimientos" devuelve la misma tendencia; no existe timeline | ⬜ Abierto |
| R2-03 | 🟠 Alto | BUG-006 / 008 | "¿Cuándo me cae la nómina?" y "¿Cuánto recibí de aguinaldo?" devuelven el resumen general sin responder | ⬜ Abierto |
| R2-04 | 🔴 Crítico | BUG-017 | "¿Eres persona real? ¿Eres de Banorte?" responde "Soy tu asistente financiero Banorte" sin aclarar que es IA ni demo | ⬜ Abierto |
| R2-05 | 🟠 Alto | BUG-008 | "¿Cobro duplicado?" mezcla 1 duplicado real con 9 "cargos inusuales" falsos (renta $5,500 cada mes; referencia "gasto típico" $420 demasiado baja) | ⬜ Abierto |
| R2-06 | 🟠 Alto | BUG-001 | La comparación dice que los gastos "bajaron 40.8%" comparando octubre (mes incompleto) con meses completos; el balance −$8,673 también engaña | ⬜ Abierto |
| R2-07 | 🟡 Medio | BUG-008 | Pagos fijos: dice 9 cargos y lista 8; total $8,996 no cuadra con la suma ($8,967); incluye "Regalo Navidad" (3 veces, no mensual) | ⬜ Abierto |
| R2-08 | 🟡 Medio | BUG-012 | Formato: `348.9`, `14800.0`, `$-8,673`, límites `800`/`1500` sin `$` | ⬜ Abierto |
| R2-09 | 🟡 Medio | BUG-006 | "Te quedan $-8,673 disponibles" con saldo negativo; debe decir que ya gastó de más | ⬜ Abierto |
| R2-10 | 🟡 Medio | BUG-006 | "Cuánto gasté en comida" solo cuenta Restaurantes, no Supermercado; "¿ando bien o mal?" no da conclusión | ⬜ Abierto |
| R2-11 | 🔵 Bajo | — | Prefijo "Aviso:" pegado al inicio de cada cargo; respuestas copiadas en preguntas repetidas | ⬜ Abierto |

## Riesgo aparte: la marca
La app dice ser "asistente financiero Banorte". Es un prototipo educativo; si algún día se publica, usar un **nombre propio** o un aviso claro de que no es el banco. Ver [[Pendientes]].

## Prompt enviado a Verdent
```
Hice pruebas manuales y estos hallazgos siguen sin corregirse. Para cada uno: reproduce, explica la causa, corrige y agrega una prueba que falle antes y pase después.

1. "Muéstrame mis gastos por categoría en barras" debe mostrar barras por categoría, no la tendencia mensual.
2. "Enséñame mi línea del tiempo de movimientos" debe mostrar un timeline de movimientos.
3. "¿Cuándo me cae la nómina?" y "¿Cuánto recibí de aguinaldo?" deben responder con fechas y montos de los datos, no el resumen general.
4. "¿Eres una persona real? ¿Eres de Banorte?" debe aclarar que es un asistente de IA, en modo demostración, sin ser una persona ni el banco oficial.
5. "¿Tengo algún cobro duplicado?" debe mostrar solo duplicados. Los cargos recurrentes (como la renta) no son "inusuales"; calcula lo inusual por categoría y excluye los recurrentes.
6. La comparación mensual no debe tratar octubre (mes incompleto) como si fuera completo: compara el mismo periodo o avisa que está en curso.
7. Pagos fijos: revisa por qué dice 9 cargos y lista 8, por qué el total no cuadra y por qué incluye "Regalo Navidad" (no es mensual).
8. Formato mexicano en toda la UI: $349 (no 348.9), $14,800 (no 14800.0), -$8,673 (no $-8,673), y signo de pesos en los límites de presupuesto.
9. Si el disponible es negativo, dilo claramente ("ya gastaste $X de más") en vez de "te quedan $-X".
10. "Comida" debe incluir Supermercado y Restaurantes.
11. Quita el prefijo "Aviso:" que aparece pegado en los cargos.

Al final entrega la tabla con ID, estado y evidencia.
```

## Resultado de la corrección
_(llenar cuando Verdent responda)_

| ID | Estado | Verificado a mano |
|---|---|---|
| R2-01 | | |
| R2-02 | | |
| R2-03 | | |
| R2-04 | | |
| R2-05 | | |
| R2-06 | | |
| R2-07 | | |
| R2-08 | | |
| R2-09 | | |
| R2-10 | | |
| R2-11 | | |

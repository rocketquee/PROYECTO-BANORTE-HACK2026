---
tags: [bitacora, ronda-3, interfaz, diseno]
fecha: 2026-10-19
estado: pendiente-de-correccion
---
# Ronda 3 · Interfaz y rediseño

Hallazgos de pantalla tras la [[Ronda 2 - Verificacion manual]] (capturas de `localhost:3000`).

## Hallazgos nuevos

| ID | Severidad | Relacionado | Qué falla | Estado |
|---|---|---|---|---|
| R3-01 | 🟠 Alto | BUG-010 / 015 | Al usar la rueda del mouse se desplaza **toda la página** en vez de solo el panel de contenido: la app queda corrida hacia arriba y abajo se ve un área vacía. La barra lateral y el historial de conversaciones quedan cortados | ⬜ Abierto |
| R3-02 | 🟠 Alto | BUG-005 | El botón «Ver detalle expandido» no abre nada; el panel derecho solo muestra su texto de ayuda | ⬜ Abierto |
| R3-03 | 🟡 Medio | BUG-010 | Botón «Enviar» deshabilitado casi invisible (gris sobre gris); textos pequeños y gris claro (etiquetas de ingreso/gastado/disponible, nota «Edita un límite...») | ⬜ Abierto |
| R3-04 | 🟡 Medio | BUG-012 / R2-08 | Los límites de presupuesto (800, 1500, 9000...) siguen sin `$` ni separador de miles | ⬜ Abierto |
| R3-05 | 🔵 Mejora | — | Rediseño visual inspirado en la referencia [[Referencia diseno - tarjeta bancaria]] | ⬜ Pendiente |

## Avances vistos en la captura
- `-$8,672.66` ya se muestra con el formato correcto (parte de R2-08).
- El menú lateral ya tiene las secciones (Pagos y transferencias, Presupuesto, Créditos y simulador, Ahorro y metas, Inversiones, Seguros, Notificaciones, Perfil, Ayuda) → avance en BUG-015.
- Existe «Historial de conversaciones» y «Nueva conversación» → avance en BUG-002 (falta probar la persistencia al recargar).
- El ícono «N» abajo a la izquierda es del modo desarrollo de Next.js; no aparece en la versión de producción.

## Prompt para Verdent (hallazgos R3-01 a R3-04)
```
Encontré estos problemas de interfaz. Para cada uno: reproduce, explica la causa, corrige y verifica con captura o prueba.

1. Scroll: al usar la rueda del mouse se desplaza toda la página y queda un espacio vacío debajo; la barra lateral y el historial se cortan. La app debe ocupar exactamente el alto de la ventana (usa 100dvh), la página no debe tener scroll propio, y solo deben desplazarse (con overflow-y auto y min-h-0) el área de mensajes, el panel de contenido y la lista del historial. La barra lateral debe poder desplazarse por sí sola si no cabe. Prueba en 768, 1366 y 1920 px de ancho, y con zoom 150% y 200%.
2. El botón «Ver detalle expandido» no abre el panel derecho. Haz que abra el resultado en ese panel y que se pueda cerrar. Si el panel está cerrado no debe ocupar espacio ni mostrar texto de ayuda.
3. Botón «Enviar» deshabilitado: contraste mínimo 3:1 y visible. Subir el tamaño y contraste de las etiquetas pequeñas (mínimo 16 px, contraste 4.5:1).
4. Límites de presupuesto: mostrar con $ y separador de miles ($1,500), conservando el campo editable.

Al final entrega la tabla con ID, estado y evidencia.
```

## Resultado de la corrección
| ID | Estado | Verificado a mano |
|---|---|---|
| R3-01 | | |
| R3-02 | | |
| R3-03 | | |
| R3-04 | | |

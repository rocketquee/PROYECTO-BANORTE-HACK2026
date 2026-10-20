---
tags: [diseno, referencia]
fecha: 2026-10-19
---
# Referencia de diseño · tablero con tarjeta bancaria

Captura de un video de un tablero bancario (pantalla «Manage») que me gustó. **Es solo inspiración**: no copiar su nombre, logo ni textos.

## Qué tiene la referencia
- Fondo claro con tarjetas blancas de esquinas muy redondeadas y sombras suaves.
- Barra superior con pestañas en forma de píldora (la activa en negro): Overview, Activity, Manage, Programs, Account, Reports.
- Botón principal negro «New card» arriba a la derecha, con avatar y notificaciones.
- Tarjeta bancaria negra grande como protagonista, con las últimas cuatro cifras y la marca.
- Fila de acciones rápidas bajo la tarjeta: congelar, mostrar número, copiar número, voltear.
- Panel «Card controls» a la derecha con interruptores (pagos en línea, sin contacto, retiros en cajero).
- Barra lateral estrecha de íconos.

## Cómo adaptarlo a mi app
| Elemento de la referencia | En mi app |
|---|---|
| Pestañas en píldora | Resumen · Movimientos · Presupuesto · Metas · Asistente |
| Tarjeta negra | Tarjeta ficticia de débito/crédito con «Prototipo educativo» |
| Acciones rápidas | Congelar (simulado), ver número (enmascarado), copiar, ver movimientos |
| Controles con interruptores | Pagos en línea, sin contacto, retiros (simulados) |
| Tarjetas blancas | Saldo, ingresos, gastos, metas, pagos fijos |
| Asistente | Panel de chat al costado o botón flotante |

## Reglas para no perder accesibilidad (ver BUG-010)
- Letra base mínima de 18 px; la referencia usa texto pequeño y gris claro, **eso no se copia**.
- Contraste de texto 4.5:1; botones de 48 px.
- Los interruptores deben tener texto «Activado / Desactivado», no solo color.
- Conservar los botones A- / A / A+.

## Plan por bloques (un bloque por mensaje, con commit entre bloques)
1. Base: colores, tipografía, esquinas, sombras y barra superior con pestañas.
2. Resumen: tarjetas de saldo, ingresos, gastos y metas.
3. Componente de tarjeta bancaria + acciones rápidas + controles.
4. Chat del asistente integrado en el nuevo diseño.
5. Revisión en celular, tableta y escritorio.

## Prompt para Verdent (bloque 1)
```
Quiero rediseñar la interfaz con un estilo inspirado en un tablero bancario moderno: fondo claro, tarjetas blancas con esquinas redondeadas (16 a 24 px) y sombra suave, pestañas superiores en forma de píldora con la activa en negro, botón principal negro, y una tarjeta bancaria negra protagonista. No copies marcas ni textos de ningún banco.

Reglas obligatorias: letra base mínima de 18 px, contraste de texto 4.5:1, botones de 48 px, interruptores con texto «Activado/Desactivado», y conservar A- / A / A+. No rompas ninguna función ni prueba existente.

Haz solo el bloque 1: sistema de diseño (colores, tipografía, radios, sombras como variables), barra superior con pestañas Resumen, Movimientos, Presupuesto, Metas y Asistente, y adaptar la barra lateral. Antes de empezar propón la paleta y la estructura en pocas líneas y espera mi aprobación.
```

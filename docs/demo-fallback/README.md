# Respaldo de la demo — capturas y PDF

Esta carpeta es el **Plan B** si el proyector falla. No sustituye la demo en
vivo: permite narrar los 5 pasos con capturas si no hay señal de video.

## Contenido esperado

| Archivo | Paso | Qué debe mostrar |
|---|---|---|
| `paso1-saldo.png` | 1 | Respuesta con `StatCard` de saldo total |
| `paso2-tendencia.png` | 2 | `LineChart` de gastos de 6 meses |
| `paso3-metas.png` | 3 | `ProgressRing` de una meta |
| `paso4-formulario.png` | 4 | `TransferForm` de $500 a Viaje a Japón |
| `paso4-resultado.png` | 4 | `StatCard` + `ProgressRing` de Viaje a Japón 19.3% |
| `paso5-degradacion.png` | 5 | Respuesta con `degraded=true` y `reason=provider_unavailable` |
| `guion-demo.pdf` | — | Guion completo para leer en segunda pantalla |

Las capturas las genera el presentador antes de la demo; no se versionan para
evitar imágenes obsoletas o datos de pantalla. El PDF sí se versiona.

## Cómo generar las capturas

1. Arranca la demo con los endpoints de desarrollo habilitados:

   ```powershell
   $env:DEV_MODE = "true"
   $env:BANORTE_DEMO_TODAY = "2026-10-30"
   scripts\start-all.cmd
   ```

2. Abre `http://localhost:3000` y entra a **Asistente**.
3. Ejecuta cada mensaje exacto de `docs/DEMO-SCRIPT.md`.
4. Con la respuesta en pantalla, pulsa `Win + Shift + S`, recorta la tarjeta o
   el panel y guarda la imagen en esta carpeta con el nombre de la tabla.
5. En el paso 4 guarda **dos** imágenes: antes de pulsar **Confirmar abono**
   (`paso4-formulario.png`) y después de confirmar (`paso4-resultado.png`).
6. En el paso 5, si la respuesta se ve en la interfaz, captura el aviso de
   degradación; si se ejecuta por API, captura la terminal con
   `mode=demo`, `degraded=true` y `reason=provider_unavailable`.

### Verificación rápida

```powershell
Get-ChildItem docs\demo-fallback\*.png | Select-Object Name,Length
```

Deben aparecer las seis capturas. Si falta alguna, usa el PDF y el guion de
narración del Plan B en `docs/DEMO-SCRIPT.md`.

## Cómo generar el PDF

El PDF se genera desde `docs/DEMO-SCRIPT.md`. Si el guion cambia, regenéralo:

1. Abre `docs/DEMO-SCRIPT.md` en el navegador o en un editor con vista previa.
2. Usa **Imprimir → Guardar como PDF**.
3. Guarda como `docs/demo-fallback/guion-demo.pdf`.

Alternativa con Edge instalado, sin abrir ventanas:

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  --headless=new --disable-gpu --no-pdf-header-footer `
  --print-to-pdf="docs\demo-fallback\guion-demo.pdf" `
  "file:///C:/ruta/al/repositorio/docs/demo-fallback/guion-demo.html"
```

## Privacidad

- Usa solo la base sintética de demostración.
- No captures claves, tokens de sesión, rutas personales ni correo.
- Revisa cada imagen antes de proyectarla.

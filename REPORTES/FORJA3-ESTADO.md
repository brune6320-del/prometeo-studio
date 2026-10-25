# Forja 3 · estado de la campaña

| Campo | |
|---|---|
| Rama | `studio/collage` |
| Fecha | 2026-10-25 |
| Último commit | `4796665` (G2) |
| Fases cerradas | **G0, G1, G2** |
| Siguiente fase | **G3 · Paridad Milanote (las 10 de G0)** |
| Push | **Nunca.** No se ha hecho push. |

## 1. Hashes

| Fase | Commit | Qué entró |
|---|---|---|
| G0 · Inventario | `11bf05f` | `REPORTES/G0-milanote.md`, capturas de referencia, config Playwright Forja 3 |
| G1 · Trackpad | `2b5394a` | capturas de puntero, limpieza de gestos, rueda estable, `gesture*` de WebKit, inercia/rubber-band, imán con guías, inclinación, hover, 3 tests Playwright |
| G2 · Medios libres | `4796665` | imagen/vídeo como objeto libre, `BoardFreeMedia`, redimensionar con proporción, drop del Finder, Cmd+V de imagen, vídeo silenciado, 2 tests Playwright |

## 2. Comprobaciones del último cierre (G2)

Ejecutadas dentro de `studio/frontend`:

| Comprobación | Resultado |
|---|---|
| `npx tsc -b` | limpio |
| `npx vitest run` | 29 archivos, 165 tests |
| `npx oxlint` | 0 errores; warnings preexistentes y de pureza/refs ya declarados |
| `npx vite build` | correcto |
| `npx playwright test -c playwright.forja3.config.ts g2-medios` | 2 tests, 2 pasan |

Capturas en `REPORTES/capturas-forja3/`: `g0-antes.png`, `g0-despues.png`, `g1-antes.png`, `g1-despues.png`, `g2-antes.png`, `g2-despues.png`, `g2-despues-imagenes.png`.

## 3. Lo que quedó verificado (E1)

- **G1:** 200 gestos mezclados (pinceladas de pellizco, dos dedos, arrastre de fondo, arrastre de tarjeta, doble clic, cambio de vista y cambio de tablero) sin `panning` ni `dragging` colgados; la rueda sigue moviendo la cámara después de cada bloque; ningún overlay invisible tapa el centro.
- **G1:** los eventos `gesturestart/gesturechange/gestureend` de WebKit se traducen al zoom de cámara; `requestAnimationFrame` medido a **61,3 fps** en este Brave/Chromium (entorno de 60 Hz).
- **G1:** hover con subida de 1,5 px y sombra; inclinación según velocidad; asentado con muelle; guías rosadas; `prefers-reduced-motion` apaga inclinación, asentado y transiciones.
- **G2:** vídeo 1920×1080 libre, `videoWidth` 1920 a 200 % de zoom, proporción 16:9, silencio por defecto, play/pausa con clic, redimensionado desde esquina manteniendo proporción; Shift libera la proporción.
- **G2:** drop del Finder y Cmd+V de imagen crean objetos libres de 1920×1080; el título/comentario solo se ve al pasar el ratón.

### 120 Hz

No hay un tope artificial de 60 en el código: no existe `setTimeout(…, 16)`; cámara, inercia y guías usan `requestAnimationFrame`. No se encontró una opción **documentada** de WKWebView/Tauri para forzar 120 Hz. No se aplicó ningún truco no documentado. Queda anotado como límite: el WebView empaquetado no se ha medido en un Mac con ProMotion.

### Bug de producto encontrado y cerrado en G1

El selector de tablero leía `event.target.value` **después** de `await flushBoardWrites()`. Al ser un select controlado, el valor ya se había revertido y el cambio de tablero se perdía. Ahora el destino se guarda antes del `await`. El test de 200 gestos lo cubre cambiando de tablero 25 veces.

## 4. Siguiente: G3

Alcance ya fijado en `G0-milanote.md` §3:

1. Conectores que siguen a las tarjetas (tirador, ancla y actualización al mover).
2. Selección múltiple con rectángulo.
3. Alt/Opción + arrastrar duplica.
4. Columnas contenedoras.
5. Listas de tareas.
6. Pegar URL con vista previa **por el backend local**, sin claves en el frontend.
7. Notas con formato mínimo.
8. Tablero dentro de tablero como tarjeta.
9. Bloquear tarjeta.
10. Plantillas de tablero.

Obligatorios dentro de las 10: conectores, rectángulo, Alt+arrastrar, columnas, tareas y URL con vista previa.

## 5. Deuda declarada

- **G3–G8 pendientes.** No se ha tocado código de G3.
- **Trackpad físico:** Playwright simula rueda y puntero; falta la prueba de Bruno en la app de escritorio (WKWebView) con dedos reales.
- **120 Hz:** no medido en WKWebView empaquetado; no hay opción documentada que aplicar.
- **Medios:** los archivos siguen guardándose como data URL dentro del tablero (límite 12 MB). No hay miniaturas; a menos del 35 % el navegador reescala la fuente completa.
- **G3 URL preview:** requiere endpoint local; hoy no existe en `studio/backend/app.py` (comprobado).
- **G0:** la columna «Milanote» se basa en ayuda pública; no se hizo ingeniería inversa ni se copiaron assets.

## 6. Cómo retomar

1. Leer este archivo, `G0-milanote.md`, `docs/STUDIO/DESIGN.md` y `prometeo-fisica`.
2. Abrir G3 por el registro (`src/board/tools/registry.ts`): un archivo por herramienta, una línea de registro y su test.
3. Cerrar G3 con las cuatro comprobaciones + Playwright + capturas antes/después y commit `studio: G3 …`.
4. No avanzar a G4 con algo en rojo.

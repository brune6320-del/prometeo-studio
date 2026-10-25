# Forja 3 · estado de la campaña

| Campo | |
|---|---|
| Rama | `studio/collage` |
| Fecha | 2026-10-25 |
| Último commit | `7e89ae2` (G3) |
| Fases cerradas | **G0, G1, G2, G3** |
| Siguiente fase | **G4 · Irene** (alcance sin spec localizada; ver §5) |
| Push | **Nunca.** No se ha hecho push. |

## 1. Hashes

| Fase | Commit | Qué entró |
|---|---|---|
| G0 · Inventario | `11bf05f` | `REPORTES/G0-milanote.md`, capturas de referencia, config Playwright Forja 3 |
| G1 · Trackpad | `2b5394a` | capturas de puntero, limpieza de gestos, rueda estable, `gesture*` de WebKit, inercia/rubber-band, imán con guías, inclinación, hover, 3 tests Playwright |
| G2 · Medios libres | `4796665` | imagen/vídeo como objeto libre, `BoardFreeMedia`, redimensionar con proporción, drop del Finder, Cmd+V de imagen, vídeo silenciado, 2 tests Playwright |
| G3 · Paridad Milanote | `7e89ae2` | las 10 de `G0-milanote.md` §3: conectores, rectángulo, Alt+arrastrar, columnas, tareas, URL preview por backend, formato de nota, tablero anidado, bloqueo y plantillas; `REPORTES/G3-paridad.md`; 10 tests Playwright |

## 2. Comprobaciones del último cierre (G3)

Ejecutadas dentro de `studio/frontend`:

| Comprobación | Resultado |
|---|---|
| `npx tsc -b` | limpio |
| `npx vitest run` | 30 archivos, 176 tests |
| `npx oxlint` | 0 errores; warnings preexistentes y de pureza/refs ya declarados |
| `npx vite build` | correcto |
| `npx playwright test -c playwright.forja3.config.ts` | 16 tests, 16 pasan (G0, G1, G2 y G3) |

Backend: `python3 -m py_compile studio/backend/app.py` correcto. El endpoint `GET /api/url-preview` se probó con el Python empaquetado: bloquea `127.0.0.1` y `ftp://`, normaliza la URL y devuelve `Example Domain` desde `https://example.com/`. Detalle en `REPORTES/G3-paridad.md`.

Capturas en `REPORTES/capturas-forja3/`: `g0-antes.png`, `g0-despues.png`, `g1-antes.png`, `g1-despues.png`, `g2-antes.png`, `g2-despues.png`, `g2-despues-imagenes.png`, `g3-despues.png`.

## 3. Lo que quedó verificado (E1)

- **G1:** 200 gestos mezclados sin `panning` ni `dragging` colgados; la rueda sigue moviendo la cámara; zoom por `gesture*` de WebKit; `requestAnimationFrame` a 61,7 fps en este entorno; hover, inclinación, guías y `prefers-reduced-motion`.
- **G2:** vídeo 1920×1080 libre, `videoWidth` 1920 a 200 % de zoom, 16:9, silencio por defecto, play/pausa, redimensionado con proporción; drop del Finder y Cmd+V crean objetos libres.
- **G3:** conector con tirador y ancla lateral, etiqueta con doble clic y curva que se recalcula al mover; ⇧ + rectángulo selecciona 3 tarjetas y muestra la barra de alineación; Alt+arrastrar deja 1 original + 1 copia; una nota suelta entra en una columna, la columna se pliega y conserva su hijo; tareas marcan, añaden y guardan; URL con vista previa pinta título, descripción e imagen; tablero anidado se crea y se abre; plantilla «Proyecto» crea 3 columnas; tarjeta bloqueada no se mueve ni se borra hasta desbloquear; nota con título, negrita, lista, cita y código se pinta al abrir y ofrece barra de formato.
- **G3 URL preview:** el bloqueo SSRF resuelve el host y revalida la URL final tras redirección. No fija la IP durante la conexión: queda como **H1** declarado, no como garantía SPEC.

## 4. Deuda acumulada

- **G4–G8 pendientes.** No se ha tocado código de G4.
- **G3 · rectángulo:** exige `⇧` para no quitarle el pan al fondo (G1). Si se quiere arrastre simple, mover el pan a Espacio+arrastrar (fila 15 de G0, G7).
- **G3 · columnas:** no se redimensionan a mano; el orden es por altura, no manual.
- **G3 · conectores:** no hay selector visual de color/grosor; el modelo ya guarda `tone`.
- **G3 · plantillas:** las guardadas viven en `localStorage`, no viajan con el proyecto.
- **Trackpad físico:** Playwright simula rueda y puntero; falta la prueba de Bruno en la app de escritorio (WKWebView) con dedos reales.
- **120 Hz:** no medido en WKWebView empaquetado; no hay opción documentada que aplicar.
- **Medios:** data URL dentro del tablero (límite 12 MB); sin miniaturas.
- **G0:** la columna «Milanote» se basa en ayuda pública; no se hizo ingeniería inversa ni se copiaron assets.

## 5. Siguiente: G4, con una precisión

Se buscó el encargo `SUPER-2-forja3.txt` en `~/Desktop/deepseek-trabajo`, `/mnt` y el repo: **no existe en esta máquina**. De la supercampaña solo quedan los nombres de fase (`G4 Irene`, `G5 Open Design + open-codesign`, `G6 editor PDF`, `G7 detalles`, `G8 caza de errores`).

La única referencia a «Irene» en el material disponible es la vista **Archivo** (`docs/STUDIO/04-LIENZO-ARCHIVO.md`, `ArchivoView.tsx`, `ARCHIVO` en los reportes H-4/H-5) y la regla de collage `irene`. **G4 no se abrió para no inventar un alcance.** Antes de codificarla hay que fijar si significa:

1. pulir la vista Archivo existente (deudas de H-4: pausar vídeos inactivos, teclado, móvil, contador), o
2. llevar el tono Irene a toda la app, o
3. la regla de collage `irene` en la Vista de Entropía.

## 6. Cómo retomar

1. Leer este archivo, `G0-milanote.md`, `G3-paridad.md`, `docs/STUDIO/DESIGN.md` y `docs/STUDIO/04-LIENZO-ARCHIVO.md`.
2. Fijar el alcance de G4 (los tres caminos de §5) y escribirlo en `REPORTES/G4-irene.md` antes de tocar código.
3. Cerrar cada fase con las cuatro comprobaciones + Playwright + captura antes/después y commit `studio: G4 …`.
4. No avanzar a G5 con algo en rojo.

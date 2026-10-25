# Forja 3 · estado de la campaña

| Campo | |
|---|---|
| Rama | `studio/collage` |
| Fecha | 2026-10-25 |
| Último commit | `4b898f5` (G4) |
| Fases cerradas | **G0, G1, G2, G3, G4** |
| Siguiente fase | **G5 · Open Design + open-codesign** |
| Push | **Nunca desde aquí.** El remoto es `github.com/brune6320-del/prometeo-studio`; Bruno hace el push. |

**Ramas de otros agentes:** `studio/recortador` y `studio/indice-visual`. No tocar `tools/recortador/` ni `tools/indice/` ni mergearlas desde esta rama.

## 1. Hashes

| Fase | Commit | Qué entró |
|---|---|---|
| G0 · Inventario | `11bf05f` | `REPORTES/G0-milanote.md`, capturas de referencia, config Playwright Forja 3 |
| G1 · Trackpad | `2b5394a` | capturas de puntero, limpieza de gestos, rueda estable, `gesture*` de WebKit, inercia/rubber-band, imán con guías, inclinación, hover, 3 tests Playwright |
| G2 · Medios libres | `4796665` | imagen/vídeo como objeto libre, `BoardFreeMedia`, redimensionar con proporción, drop del Finder, Cmd+V de imagen, vídeo silenciado, 2 tests Playwright |
| G3 · Paridad Milanote | `7e89ae2` | las 10 de `G0-milanote.md` §3: conectores, rectángulo, Alt+arrastrar, columnas, tareas, URL preview por backend, formato de nota, tablero anidado, bloqueo y plantillas; `REPORTES/G3-paridad.md`; 10 tests Playwright |
| G4 · Irene, 2.ª pasada | `4b898f5` | deuda H-4 (vídeos inactivos, flechas, contador, móvil), pliego de dos páginas, filas por año, zonas de cursor en muro, tono mono/punteado en Archivo, Muro y Mesa; `REPORTES/G4-irene.md`; 4 tests unitarios y 5 E2E nuevos |

## 2. Comprobaciones del último cierre (G4)

Ejecutadas dentro de `studio/frontend`:

| Comprobación | Resultado |
|---|---|
| `npx tsc -b` | limpio |
| `npx vitest run` | 30 archivos, 180 tests |
| `npx oxlint` | 0 errores; sin warnings nuevos en los archivos de G4 |
| `npx vite build` | correcto (aviso de chunk > 500 kB, ya existente) |
| `npx playwright test -c playwright.forja3.config.ts` | 21 tests, 21 pasan (G0–G4) |

Backend sin cambios en G4. El endpoint `GET /api/url-preview` sigue como se cerró en G3. Detalle en `REPORTES/G3-paridad.md`.

Capturas en `REPORTES/capturas-forja3/`: las de G0–G3 más `g4-antes.png`, `g4-antes-completo.png`, `g4-despues.png`, `g4-despues-movil.png`, `g4-despues-pliego.png`, `g4-despues-anos.png`.

## 3. Lo que quedó verificado (E1)

- **G1:** 200 gestos mezclados sin `panning` ni `dragging` colgados; la rueda sigue moviendo la cámara; zoom por `gesture*` de WebKit; `requestAnimationFrame` a 61,7 fps en este entorno; hover, inclinación, guías y `prefers-reduced-motion`.
- **G2:** vídeo 1920×1080 libre, `videoWidth` 1920 a 200 % de zoom, 16:9, silencio por defecto, play/pausa, redimensionado con proporción; drop del Finder y Cmd+V crean objetos libres.
- **G3:** conector con tirador y ancla lateral, etiqueta con doble clic y curva que se recalcula al mover; ⇧ + rectángulo selecciona 3 tarjetas y muestra la barra de alineación; Alt+arrastrar deja 1 original + 1 copia; una nota suelta entra en una columna, la columna se pliega y conserva su hijo; tareas marcan, añaden y guardan; URL con vista previa pinta título, descripción e imagen; tablero anidado se crea y se abre; plantilla «Proyecto» crea 3 columnas; tarjeta bloqueada no se mueve ni se borra hasta desbloquear; nota con título, negrita, lista, cita y código se pinta al abrir y ofrece barra de formato.
- **G3 URL preview:** el bloqueo SSRF resuelve el host y revalida la URL final tras redirección. No fija la IP durante la conexión: queda como **H1** declarado, no como garantía SPEC.
- **G4:** cerrada la deuda H-4. El vídeo de la diapositiva inactiva se pausa; `←`/`→` mueven el bloque activo; contador `1 / 3`; móvil en una columna con barra fija. Pliego de dos páginas al doble clic en un proyecto. Mesa con modo «Por año» y `More →`. Muro con zonas de cursor y tono blanco/punteado. Capturas y detalles en `REPORTES/G4-irene.md`.

## 4. Deuda acumulada

- **G5–G8 pendientes.** No se ha tocado código de G5.
- **G3 · rectángulo:** exige `⇧` para no quitarle el pan al fondo (G1). Si se quiere arrastre simple, mover el pan a Espacio+arrastrar (fila 15 de G0, G7).
- **G3 · columnas:** no se redimensionan a mano; el orden es por altura, no manual.
- **G3 · conectores:** no hay selector visual de color/grosor; el modelo ya guarda `tone`.
- **G3 · plantillas:** las guardadas viven en `localStorage`, no viajan con el proyecto.
- **Trackpad físico:** Playwright simula rueda y puntero; falta la prueba de Bruno en la app de escritorio (WKWebView) con dedos reales.
- **120 Hz:** no medido en WKWebView empaquetado; no hay opción documentada que aplicar.
- **Medios:** data URL dentro del tablero (límite 12 MB); sin miniaturas.
- **G0:** la columna «Milanote» se basa en ayuda pública; no se hizo ingeniería inversa ni se copiaron assets.

## 5. Siguiente: G5 · bibliotecas de diseño

Alcance fijado en el encargo de Bruno:

1. Clonar `https://github.com/OpenCoworkAI/open-codesign` (MIT) en `~/Projects/open-codesign` y verificar su LICENSE.
2. Estudiar `~/Projects/open-design` y `open-codesign`: cómo organizan bibliotecas gigantes de skills y sistemas de diseño, y cómo el segundo pasa de prompt a prototipo.
3. Aplicar a Prometeo:
   - **a)** el menú «+ Más» como biblioteca navegable de herramientas, con búsqueda, categorías y vista previa;
   - **b)** un selector de «sistema de diseño» por tablero que cambie los tokens (al menos Forja 2 y uno inspirado en Irene).
4. Copiar solo código MIT/Apache y dejar `PROCEDENCIA.md`.

## 6. Cómo retomar

1. Leer este archivo, `G4-irene.md`, `G0-milanote.md`, `G3-paridad.md` y `docs/STUDIO/DESIGN.md`.
2. Escribir el alcance de G5 en `REPORTES/G5-open-design.md` antes de tocar código.
3. Cerrar cada fase con las cuatro comprobaciones + Playwright + captura antes/después y commit `studio: G5 …`.
4. No avanzar a G6 con algo en rojo.

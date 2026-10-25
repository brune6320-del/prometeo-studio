# Forja 3 · estado de la campaña

| Campo | |
|---|---|
| Rama | `studio/collage` |
| Fecha | 2026-10-25 |
| Último commit | `f15261f` (G8) |
| Fases cerradas | **G0, G1, G2, G3, G4, G5, G6, G7, G8** |
| Siguiente fase | **Ninguna. Campaña cerrada.** |
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
| G5 · Open Design | `6f64c7e` | clone y licencias verificadas, estudio de catálogos de skills/sistemas, «+ Más» navegable con búsqueda/categorías/vista previa, selector de sistema por tablero (Forja 2 + Archivo Irene); `PROCEDENCIA.md`, `REPORTES/G5-open-design.md`; 7 tests unitarios y 2 E2E |
| G6 · Editor PDF | `4c335d6` | reintento de parche idempotente (reutiliza la operación), tabla «Comprobación / Esperado / Obtenido», checks vectoriales y raster, paneles plegables y ventana estrecha; `REPORTES/G6-pdf.md`; 3 tests unittest y 3 E2E con motor real |

## 2. Comprobaciones del último cierre (G8)

Ejecutadas dentro de `studio/frontend`:

| Comprobación | Resultado |
|---|---|
| `npx tsc -b` | limpio |
| `npx vitest run` | 34 archivos, 195 tests |
| `npx oxlint` | 0 errores; 27 warnings preexistentes |
| `npx vite build` | correcto (aviso de chunk > 500 kB, ya existente) |
| `npx playwright test -c playwright.forja3.config.ts` | 30 tests, 30 pasan (G0–G8; soak de 15 min aparte) |
| `playwright.config.ts g6-pdf.spec.ts` | 3 tests, 3 pasan con motor real |
| `unittest tests.studio.test_g6_pdf` | 3 tests, 3 pasan con `case_a` y `case_b_scan` |
| Soak G8 | 903 s, 691 ciclos, 15 recargas, 0 errores, peor FPS 57 |

Backend sin cambios en G4. El endpoint `GET /api/url-preview` sigue como se cerró en G3. Detalle en `REPORTES/G3-paridad.md`.

Capturas en `REPORTES/capturas-forja3/`: todas las de G0–G7 más `g8-despues.png`. El cierre completo y la tabla Milanote están en `REPORTES/FORJA3.md`.

## 3. Lo que quedó verificado (E1)

- **G1:** 200 gestos mezclados sin `panning` ni `dragging` colgados; la rueda sigue moviendo la cámara; zoom por `gesture*` de WebKit; `requestAnimationFrame` a 61,7 fps en este entorno; hover, inclinación, guías y `prefers-reduced-motion`.
- **G2:** vídeo 1920×1080 libre, `videoWidth` 1920 a 200 % de zoom, 16:9, silencio por defecto, play/pausa, redimensionado con proporción; drop del Finder y Cmd+V crean objetos libres.
- **G3:** conector con tirador y ancla lateral, etiqueta con doble clic y curva que se recalcula al mover; ⇧ + rectángulo selecciona 3 tarjetas y muestra la barra de alineación; Alt+arrastrar deja 1 original + 1 copia; una nota suelta entra en una columna, la columna se pliega y conserva su hijo; tareas marcan, añaden y guardan; URL con vista previa pinta título, descripción e imagen; tablero anidado se crea y se abre; plantilla «Proyecto» crea 3 columnas; tarjeta bloqueada no se mueve ni se borra hasta desbloquear; nota con título, negrita, lista, cita y código se pinta al abrir y ofrece barra de formato.
- **G3 URL preview:** el bloqueo SSRF resuelve el host y revalida la URL final tras redirección. No fija la IP durante la conexión: queda como **H1** declarado, no como garantía SPEC.
- **G4:** cerrada la deuda H-4. El vídeo de la diapositiva inactiva se pausa; `←`/`→` mueven el bloque activo; contador `1 / 3`; móvil en una columna con barra fija. Pliego de dos páginas al doble clic en un proyecto. Mesa con modo «Por año» y `More →`. Muro con zonas de cursor y tono blanco/punteado. Capturas y detalles en `REPORTES/G4-irene.md`.

## 4. Deuda acumulada

- **Forja 3 cerrada.** El cierre completo está en `REPORTES/FORJA3.md`.
- **Fuera de alcance:** comentarios, búsqueda global entre tableros, etiquetas de color de Milanote, columnas redimensionables a mano, selector visual de conectores, miniaturas de medios y soak del PDF.
- **Solo Bruno:** WKWebView empaquetado, 120 Hz reales y trackpad/dedos físicos.
- **G5 · biblioteca:** el test de G3 que abría «Tablero anidado» se adaptó al nuevo flujo (elegir + «Añadir al tablero»); no cambió la app para complacer al test.
- **G5 · sistemas:** el sistema Irene cambia tokens, no la geometría interna de cada herramienta. No se copió código de los repos estudiados; ver `PROCEDENCIA.md`.
- **G3 · rectángulo:** exige `⇧` para no quitarle el pan al fondo (G1). Si se quiere arrastre simple, mover el pan a Espacio+arrastrar (fila 15 de G0, G7).
- **G3 · columnas:** no se redimensionan a mano; el orden es por altura, no manual.
- **G3 · conectores:** no hay selector visual de color/grosor; el modelo ya guarda `tone`.
- **G3 · plantillas:** las guardadas viven en `localStorage`, no viajan con el proyecto.
- **Trackpad físico:** Playwright simula rueda y puntero; falta la prueba de Bruno en la app de escritorio (WKWebView) con dedos reales.
- **120 Hz:** no medido en WKWebView empaquetado; no hay opción documentada que aplicar.
- **Medios:** data URL dentro del tablero (límite 12 MB); sin miniaturas.
- **G0:** la columna «Milanote» se basa en ayuda pública; no se hizo ingeniería inversa ni se copiaron assets.

## 5. Campaña cerrada

`REPORTES/FORJA3.md` contiene el cierre: hashes, tabla Milanote antes/después, capturas, FPS, los 6 pasos que debe probar Bruno y la deuda que queda. No se hizo push.

## 6. Cómo retomar

1. Leer este archivo y `REPORTES/FORJA3.md`.
2. Repetir las cuatro comprobaciones en `studio/frontend` y, si se toca el tablero, `g8-caza.spec.ts`.
3. El soak de 15 min se ejecuta solo con `PROMETEO_SOAK=1 npx playwright test -c playwright.forja3.config.ts g8-soak.spec.ts`.
4. Cualquier fase nueva va en su propio commit y su propio reporte; no se reabre esta campaña.

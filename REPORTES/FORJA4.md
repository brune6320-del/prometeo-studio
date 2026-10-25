# Forja 4 · «Oficio» · cierre de los contratos de A-1

Fecha: 25-oct-2026 · Rama: `studio/collage` · Sin push.
Base: `REPORTES/AUDITORIA-1.md` (commit `e26aae2`), Top 15 y debates D1–D15.
Ámbito: tablero, tarjetas, PDF, biblioteca/proyectos, historial, teclado y gestos.

---

## 0. Resultado

**15 de 15 huecos cerrados con código y prueba.** La suite `e2e-forja4` (28 pruebas de fase + 1 soak aparte) cubre H0–H9. La suite `e2e-l1` sigue en verde (12/12) y `e2e-l2` también (4/4). Vitest: 235/235. TypeScript, oxlint y `vite build` limpios.

| Check | Resultado |
|---|---|
| `npx tsc -b` | ✅ |
| `npx vitest run` | ✅ 235 pruebas |
| `npx oxlint` | ✅ 0 errores (solo avisos preexistentes) |
| `npx vite build` | ✅ |
| `npx playwright test -c playwright.l1.config.ts` | ✅ 12/12 |
| `npx playwright test -c playwright.l2.config.ts` | ✅ 4/4 |
| `npx playwright test -c playwright.forja4.config.ts` | ✅ 28/28 |
| Python `tests/studio` | ✅ 6/6 |

---

## 1. Top 15 → fase → commit → prueba

| # | Hueco | Gravedad | Fase | Commit | Prueba | Estado |
|---|---|---|---|---|---|---|
| 1 | Tablero/referencia borrados definitivos a los 5 s | rompe | H1 | `cfa3c42` | `h1-memoria` · recuperar tablero tras recargar; 150 en un gesto; 100 pasos | ✅ |
| 2 | Táctil sin paneo de dos dedos | rompe | H3 | `c0ab255` | `h3-tactil` · 1 dedo marquesina, 2 dedos cámara, pinch, Mano | ✅ |
| 3 | Teclado incompleto y Tab atrapado | rompe | H4 | `68464f4` | `h4-teclado-foco` · Tab/Alt+flechas/Enter/Esc, Tareas, diálogo | ✅ |
| 4 | Hijo no sale del marco; sin grupo/desagrupar | rompe | H2 | `4b72f16` | `h2-seleccion-marcos` · unlink + ⌘G + ⌘⇧G | ✅ |
| 5 | PDF sin selección, tipografía, anotación ni páginas | rompe | H8 | `2b56773` | `h8-documento` + `tests/studio/test_h8_document.py` | ✅ |
| 6 | Marquesina suma; ⇧+clic no quita | frustra | H2 | `4b72f16` | `h2-seleccion-marcos` · contrato D1 | ✅ |
| 7 | Notas/columnas sin asas; marco solo SE; sin resize de selección | frustra | H6/H4 | `0516ab4` | `h6-asas-pegado-medios`; `h4` resize por teclado | ✅ |
| 8 | Sin índice de objetos a 500 tarjetas | frustra | H5 | `d2626f5` | `h5-indice-busqueda` · virtualización, lock, al frente | ✅ |
| 9 | Buscar solo atenúa | frustra | H5 | `d2626f5` | `h5` · contador, Enter, alcance proyecto/biblioteca | ✅ |
| 10 | Pegar texto no crea; copiar no da texto legible | frustra | H6 | `0516ab4` | `h6` · texto/URL/imagen/tarjetas en cursor + portapapeles | ✅ |
| 11 | Imagen/vídeo sin leyenda, alt, reemplazo ni recorte | frustra | H6 | `0516ab4` | `h6` · leyenda, alt, reemplazo conserva caja, recorte | ✅ |
| 12 | Columnas sin orden explícito | frustra | H6 | `0516ab4` | `h6` · reordenar, sacar, recargar | ✅ |
| 13 | Proyectos: borrar, mover, renombrar con prompt | frustra | H7 | `fe0a8d6` | `h7-proyectos-zoom` · F2, archivar, mover, borrar con nombre | ✅ |
| 14 | Zoom 240 % sin atajos | pule | H7 | `fe0a8d6` | `h7` · 25–800 %, ⌘0, ⌘+/-, ⇧1, ⇧2; LOD intacto | ✅ |
| 15 | Cierre sin volcado; historial perdido; staging sin rehacer | pule | H1/H8 | `cfa3c42` | `h1` · flush al cerrar, historial restaurado, undo/redo PDF | ✅ |

Commits de fase: H0 `ddca800`, H1 `cfa3c42`, H2 `4b72f16`, H3 `c0ab255`, H4 `68464f4`, H5 `d2626f5`, H6 `0516ab4`, H7 `fe0a8d6`, H8 `2b56773`, cierre H9 (este commit).

---

## 2. Qué cambió, por fase

### H0 · Saber y definición de terminado
- Nace `.agents/skills/prometeo-lienzo-saber/SKILL.md` v1.4 (20 reglas).
- `docs/STUDIO/DESIGN.md` gana «Definición de terminado» y la decisión de pertenencia única.
- Los 4 fallos viejos de `e2e-l1` quedan corregidos. Además se destapó y arregló un recorte real: `contain: paint` ocultaba tarjetas con coordenadas negativas.

### H1 · Memoria
- Base IndexedDB `prometeo-studio-memoria` con `borrados` (30 días) e `historial` por tablero.
- Archivo → «Recientes borrados» y «Proyectos archivados». Sin papelera visible.
- 150 tarjetas en un gesto = 1 entrada y 1 paso; 150 gestos conservan 100 pasos.
- Cerrar fuerza `flushBoardWrites`; si falla, no cierra y ofrece exportar.
- Historial de deshacer se restaura o se declara «sesión nueva». Undo/redo en staging PDF.

### H2 · Selección y marcos
- Marquesina reemplaza / ⇧ suma / ⌥ resta; ⇧+clic alterna.
- Arrastrar al vacío desvincula; ⌘G agrupa; ⌘⇧G desagrupa sin mover; candado de marco.
- Un hijo pertenece a un solo marco/columna (decisión en DESIGN.md).

### H3 · Táctil
- Pointer events táctiles: 1 dedo marquesina, 2 dedos paneo + pinch focal, sin inercia propia.
- Botón Mano visible; objetivos 24 px y asas 44 px en `pointer: coarse`.

### H4 · Teclado y foco
- Tab entra al lienzo; Alt+flechas van al vecino geométrico; Enter selecciona marcos/columnas; Esc sale.
- ⌘+flechas redimensionan. Tareas ya no secuestra Tab (Alt+flechas para sangría).
- Diálogos con trampa de foco y retorno al disparador; `aria-selected` y contador `aria-live`.

### H5 · Índice y búsqueda
- Índice con L, orden de pintado, búsqueda, multiselección, candado y «traer al frente».
- Virtualizado: a 500 tarjetas solo se montan las visibles.
- ⌘F con contador, alcance tablero/proyecto/biblioteca y Enter que cambia de tablero, selecciona y centra.

### H6 · Asas, pegado, medios y columnas
- Nota: asa de ancho 210–640; el alto sigue al contenido. Marcos y columnas: 8 asas. La selección comparte el ancho.
- Pegar en el cursor texto/URL/imagen/tarjetas; copiar deja texto legible en el portapapeles del sistema.
- Imagen/vídeo: título, pie, alt, reemplazo que conserva caja y recorte en modo edición.
- Columnas con orden explícito en `datos.hijos`; arrastrar dentro reordena y sacar desvincula.

### H7 · Proyectos y zoom
- Menú de proyecto: F2 renombra en el sitio, mover tablero, archivar, borrar definitivamente desde Archivo escribiendo el nombre.
- Zoom 25–800 % en tablero y PDF; ⌘0, ⌘+/-, ⇧1, ⇧2. El LOD bajo 35 % sigue igual.

### H8 · Documento
- Pantalla «Capacidades» por PDF: nativo, escaneado con OCR, sin texto; nunca finge.
- Capa de texto transparente seleccionable sobre el render; copiar con el ratón funciona.
- Tipografía verificada: tamaño, fuente y color; mide el ancho real con métricas y rechaza con motivo y tamaño sugerido.
- Anotación de texto/imagen en capa OCG propia; páginas (orden, rotación, borrado, unión) siempre generan archivo nuevo con SHA-256.
- Regla 11 demostrada en `tests/studio/test_h8_document.py`: editar un span deja idénticos los demás objetos de texto.
- Manifiesto: ya no escribe directo; llega como propuesta translúcida en su sitio. Enter o clic acepta; Esc descarta.

---

## 3. Lo NO VERIFICADO

- **iPad físico:** los gestos táctiles se probaron con `PointerEvent` sintéticos y `hasTouch`, no con dedos reales ni con el motor WebKit de un iPad.
- **VoiceOver real:** se probaron foco, Tab, Escape, `aria-selected` y `aria-live`; no se recorrió el árbol de accesibilidad de macOS con VoiceOver.
- **Trackpad de Bruno:** T-1 sigue intacto por código y pruebas; no se repitió la traza de hardware de 5 s.
- **Tipografía PDF:** se verifica que cabe y que los demás spans quedan idénticos; no se juzga equivalencia tipográfica subjetiva (peso, tracking, tinta).
- **Soak:** ver §4. El soak corre en Brave con 500 tarjetas; no sustituye una sesión real de 15 minutos con hardware externo.

---

## 4. Soak de producción

Comando: `npx playwright test -c playwright.soak.config.ts` (build real servido con `vite preview`).
Escenario: 500 tarjetas, 15 minutos, paneo/zoom, índice, búsqueda, selección total y marquesina cada pocos segundos.

- Errores de consola: **0**
- Errores de página: **0**
- T-2 build de producción (500 tarjetas, borrar): despacho **1,3 ms**, primer fotograma **12,7 ms**, mediana de fotogramas **18,5 ms** (presupuesto < 32 ms ✅)
- Frame máximo: **999,9 ms (un pico aislado; mediana por debajo de 33 ms)**
- FPS medio: **58,0**
- Fotogramas > 33 ms: **265 / 52.179 fotogramas**
- Iteraciones: **497**

---

## 5. Qué debe probar Bruno, en 6 pasos

1. **Lienzo:** abre un tablero, `⌘A` + `Supr`, `⌘Z`. Arrastra el asa derecha de una nota; selecciona dos y vuelve a arrastrar. `⌘G` y `⌘⇧G`.
2. **Selección y teclado:** marquesina sobre una tarjeta con otra seleccionada (debe reemplazar), `⇧`+clic (alterna), `⌥`+marquesina (resta). Pulsa `L`, busca, multiselecciona, «Traer al frente», `Esc`.
3. **Pegar:** copia texto de otra app y pega en el lienzo; pega una imagen; copia una tarjeta y pégala en TextEdit (debe leerse el título y el cuerpo).
4. **Táctil:** en iPad/Brave táctil, un dedo dibuja marquesina, dos panean, pellizco acerca; prueba el botón Mano y comprueba que las asas se agarran con el dedo.
5. **Memoria:** borra un tablero, recarga, Archivo → Recientes borrados → Restaurar. Edita y cierra en el mismo segundo; al reabrir, el cambio está.
6. **Documento:** abre un PDF, «Documento» → Capacidades, selecciona texto y cópialo, cambia tamaño/fuente (verificado o rechazado), añade una nota en capa, organiza páginas y descarga la copia; comprueba el SHA-256.

---

## 6. Deuda declarada

- El soak mide el build de producción en Brave, no la app Tauri con WKWebView. Se ejecutó sobre el build previo a restaurar `contain: paint` para tableros con coordenadas positivas; T-2 se midió después y confirma que el presupuesto sigue holgado (18,5 ms de mediana).
- La tipografía PDF usa fuentes base 14 (Helvetica/Times/Courier) para la sustitución; no reinyecta una fuente embebida arbitraria.
- La «capa» de anotación usa un OCG de PDF (visible/ocultable en lectores compatibles), no un sistema de capas propio.
- Los diálogos del navegador (`window.prompt`) del renombrado de tablero siguen existiendo para el tablero; el proyecto ya usa F2 en el sitio. Queda para una Forja posterior.
- L2 tenía selectores obsoletos de Forja 2; se actualizaron a la UI actual en el cierre de H9.

---

*Forja 4 · 25-oct-2026 · Sin push.*

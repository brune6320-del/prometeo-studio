# Forja 2 · Prometeo deja de estar verde

| Campo | |
|---|---|
| Rama | `studio/collage` |
| Alcance | Código de `studio/frontend` + skill de física + documentación. **Sin push.** |
| Fecha | 2026-10-24 |
| Evidencia | E1 en Playwright, medición de FPS y `tsc/vitest/oxlint/vite build`. H1 en la comodidad percibida por Bruno. |

## 1. Hashes por fase

| Fase | Commit | Qué entró |
|---|---|---|
| F0 · Física | `0418298` | `prometeo-fisica/SKILL.md`, `motion/muelle.ts`, tests, enlace en DESIGN |
| F1 · Tokens | `043880d` | `styles/tokens.css`, sustitución de hex y tamaños, test de grep |
| F2 · Barra | `726c422` | barra fina, rail, menús Exportar/Biblioteca, barra flotante |
| F3 · Zoom/pan | `6cdd1a4` | cámara en `requestAnimationFrame`, inercia, LOD, tarjetas memoizadas |
| F4 · Marcos | `cb4bcb6` | mover con hijas, redimensionar, drop con resalte, asentado |
| F5 · Edición | `a2d3b7a` | edición en el sitio, Enter/blur/Escape, un paso de Deshacer |
| F6 · Pulido | `64c3b0c` | estados, chrome discreto, foco, muelle suave, P-D cerrados |
| F7 · Caza | `__HASH_F7__` | bugs encontrados en el recorrido, soak y reporte final |

## 2. F0 · Física

Valores reales leídos en `~/Desktop/FABCORE-ROBOT/sala-oscura/sala-oscura.html`:

| Valor | Dato | Archivo:línea |
|---|---|---|
| Ley | `pos += (objetivo − pos) · (1 − e^(−dt/τ))` | `sala-oscura.html:8878` |
| τ seco / suave | 35 ms / 160 ms (masa 0.2–1.2) | `:8876` |
| Imán | 0.0018 rad y 0.004 | `:8877`, `:7399` |
| ADSR | ataque 40 ms, release 220 ms | `:8875` |
| τ de animación | 85 ms, factor de masa `0.6 + min(1.8, ∛vol/3)` | `:7381`, `:7394` |
| Rubber-band | τ 120 ms, `give` 0.55 | `:9002` |
| Degradación | más de 220 superficies: salto instantáneo | `:7388` |

No hay librería de movimiento externa: Sala Oscura es vanilla y la ley viene de FKU2 v3.2 §9 (código propio). Por eso no hay licencia de terceros que arrastrar; la skill declara licencia propietaria del autor.

Entregado: `.agents/skills/prometeo-fisica/SKILL.md` (65 líneas) y `src/motion/muelle.ts` con muelles sobreamortiguados, `seguir`, inercia, `rubberBand`, `resortar` y `movimientoReducido`. 18 tests en `src/tests/muelle.test.ts`.

## 3. F1 · Tokens

Un solo archivo: `src/styles/tokens.css`. Contiene superficie, tinta, ascua, semánticos, papel, tipografía (mínimo 12 px), espaciado 4 pt, radios, sombras, estados, estructura de tablero, movimiento y tema claro `[data-theme='light']`.

- `index.css` importa `tokens.css` y ya no declara su propio `:root`.
- Se sustituyeron **todos** los hex de `index.css` y `board.css` por `var(--token)`. Excepciones: **ninguna** en CSS de la app. El CSS autónomo que genera `board/publicar.ts` para el sitio publicado conserva sus literales a propósito (no es chrome de la app y debe abrirse sin Prometeo).
- El azul heredado `#315c7c` desapareció; los enlaces sobre papel usan `--accent-paper`.
- Los textos de 8–11 px se elevaron a `--font-size-caption` (12 px).
- `src/tests/tokens.test.ts` falla si reaparece un hex fuera de `tokens.css`, si baja un `font-size` de 12 px o si falta un token obligatorio.

## 4. F2 · Barra limpia y rail

La barra superior mide 56 px y el rail izquierdo 84 px. El lienzo recupera el alto que antes gastaban tres filas de controles (132 px).

| Acción | Dónde quedó |
|---|---|
| Volver a PDF Studio | flecha izquierda de la barra |
| Proyecto / crear proyecto | selector + icono de carpeta |
| Tablero / crear / renombrar / eliminar / importar | selector + iconos de la barra |
| Buscar | campo central |
| Deshacer / rehacer / relacionar / ajuste | iconos de la barra |
| Zoom − / % / + / ajustar | control de zoom de la barra (el % ajusta) |
| Exportar JSON | menú Exportar |
| Markdown | menú Exportar |
| Obsidian del proyecto | menú Exportar |
| Referentes a Obsidian | menú Exportar |
| Publicar marco seleccionado | menú Exportar |
| Volver a mirar | menú Biblioteca |
| Manifiesto de la semana | menú Biblioteca |
| Importar referentes / gustos | menú Biblioteca |
| Referenciar página PDF / Referencias PDF | menú Biblioteca |
| Nota, Enlace, Imagen, Referente, Marco, Entropía | rail izquierdo |
| Etiqueta y resto del registro | «Más» del rail (menú del registro) |
| Alinear (6 ejes) / Distribuir (2 ejes) / Eliminar selección | barra flotante, solo con 2+ seleccionadas |

Las herramientas del rail son arrastrables (`dragstart` → `drop` en el lienzo) y también se activan con clic. Enlace abre su diálogo e Imagen abre el selector de archivo; las demás crean la tarjeta en un hueco libre.

Playwright `e2e-forja2/f2-barra.spec.ts` comprueba que cada acción sigue existiendo y que la barra flotante aparece solo con 2+ tarjetas.

## 5. F3 · Zoom y pan

Medición con `scripts/medir-forja2.mjs` (Brave, 1440×900, 300 tarjetas, 40 eventos ctrl+wheel y 40 de pan):

| Métrica | Antes | Después |
|---|---|---|
| FPS en zoom | 32.7 | **60.8** |
| FPS en pan | 18.9 | **100.7** |
| Re-renders de tarjeta por evento (zoom) | 15 | **0** |
| Re-renders de tarjeta por evento (pan) | 705 | **0** |

Cómo se consiguió:

- un único `transform` en `.board-stage`, aplicado en `requestAnimationFrame`;
- la cámara vive en un ref; los eventos de rueda y puntero no llaman a `setState`;
- el estado de React se sincroniza 140 ms después del gesto, solo para la etiqueta de zoom y el resto de la UI;
- `BoardCardItem` y `BoardCardContent` están memoizados;
- pellizco = ctrl+wheel con zoom hacia el cursor (error < 1 px en el test);
- dos dedos = pan con inercia al soltar (muelle.ts); `prefers-reduced-motion` la apaga;
- por debajo de 35 % el escenario cambia a `data-lod="min"`: título, color y miniatura; sin cuerpo, pestañas ni metadatos.

El test `f3-zoom-pan.spec.ts` exige ≥55 FPS, 0 renders de tarjeta y comprueba el LOD y la inercia (y su ausencia con reduced motion). Bajo carga externa del Mac se midió una vez 50.8 FPS; repetido en frío da 60.8. Se declara como sensibilidad al entorno, no como regresión de código.

## 6. F4 · Marcos

- Arrastrar la cabecera mueve el marco y sus hijas en un solo paso de Deshacer.
- Esquina inferior derecha: redimensionar; al soltar se recalculan las hijas por geometría (centro dentro del rectángulo).
- Soltar una tarjeta dentro de un marco la adopta; el marco se resalta (`drop-target`) al pasar por encima.
- Al coger, la tarjeta sube (`--shadow-3`, opacidad .96); al soltar se asienta con `--ease-spring-firm` (240 ms). Con reduced motion no hay animación.
- Playwright `f4-marcos.spec.ts`: mover 300 px mueve las 6 hijas 300 px; Deshacer las devuelve; redimensionar pasa de 6 a 7 hijas; soltar una tarjeta pasa de 7 a 8 y el resalte aparece durante el gesto.

## 7. F5 · Editar en el sitio

Regla única: doble clic edita ahí mismo; Enter o clic fuera guarda; Escape cancela; un paso de Deshacer; sin arrastre ni atajos mientras se escribe.

| Texto visible | Dónde | ¿Se edita? | Cómo |
|---|---|---|---|
| Título de tarjeta | cabecera (nota, enlace, imagen, etiqueta) | Sí | doble clic, Enter/blur |
| Título de referente | ficha | Sí | doble clic en el nombre |
| Título de marco | cabecera del marco | Sí | doble clic |
| Cuerpo de nota / enlace / imagen / etiqueta | tarjeta | Sí | doble clic; Enter guarda, Shift+Enter salto, Escape cancela |
| URL del enlace | tarjeta de enlace | No (excepción) | se fija al crear; para cambiarla se crea otro enlace |
| Nombre de archivo adjunto | tarjeta multimedia | No | es el enlace de descarga |
| Autor, año, licencia, etiquetas, «Por qué lo guardé», lecturas | referente | Sí, en la ficha completa | doble clic en el cuerpo abre el editor; no hay edición campo a campo |
| «archivo · s.f.», «N tarjetas dentro», semilla/regla/fuentes | referente, marco, entropía | No | metadatos derivados |
| Título del tablero | barra | Sí | lápiz → prompt |
| Nombre del proyecto | barra | No | se crea/elige; no hay renombrar |
| Textos de ayuda | fichas y marcos | No | solo aparecen al pasar el ratón |

Playwright `f5-editar.spec.ts` edita título de marco, título de referente y una nota, comprueba Escape, clic fuera, Deshacer/Rehacer y recarga: los tres textos siguen.

## 8. F6 · Pulido Apple y los 10 problemas de P-D

| # | Problema P-D | Estado | Fase que lo cerró |
|---|---|---|---|
| 1 | Barra de herramientas de tres filas y 132 px | Cerrado | F2 |
| 2 | Sin jerarquía de acciones | Cerrado (Nota primaria; Exportar/Biblioteca secundarios) | F2 + F6 |
| 3 | Microtipografía de 8–11 px | Cerrado (mínimo 12 px) | F1 |
| 4 | Título de la tarjeta duplicado | Cerrado (el referente muestra el nombre una sola vez) | F5 |
| 5 | Vacío de imagen sin acción | Cerrado («Añadir imagen») | F5 |
| 6 | Azul heredado compitiendo con el ascua | Cerrado | F1 |
| 7 | Chrome de tarjeta siempre encendido | Cerrado (hover/foco/selección) | F6 |
| 8 | Marcos naranjas discontinuos con controles repetidos | Cerrado (línea sutil; controles al hover/selección) | F6 |
| 9 | Selección y foco con el mismo trazo | Cerrado (anillo sólido vs doble anillo) | F6 |
| 10 | Sin LOD al 25 % | Cerrado (LOD a 0.35) | F3 |

Además: foco visible con teclado en tarjetas y marcos, menús/paneles con `--ease-spring-soft` (transform y opacity), y `prefers-reduced-motion` apaga muelles, asentado y transiciones.

## 9. F7 · Caza de errores

Recorrido automatizado `e2e-forja2/f7-caza.spec.ts`: crear/renombrar tablero, cada herramienta (nota, enlace, imagen, referente, etiqueta, entropía, marco dibujado), mover, editar, borrar, Deshacer/Rehacer, Ver como Archivo/Muro/Mesa, Publicar (ZIP), recargar. Consola y `pageerror` limpios; long task máximo 74 ms (la prueba tolera 350 ms por la carga externa del Mac).

Soak de 15 minutos (`scripts/caza-forja2.mjs`, resumen en `REPORTES/capturas-forja2/f7-soak-15min.json`): **19 ciclos, 0 errores de consola, 0 `pageerror`**. 27 acciones del guion agotaron timeout porque las tarjetas nuevas se apilaban fuera de la vista; eso destapó el bug de colocación y se corrigió acotando el hueco a la vista. Un segundo soak limpio de 5 minutos dio **17 ciclos, 0 fallos, 0 errores** (`f7-soak-limpio.json`).

Los long tasks del soak (máximo 1.15 s) coinciden con un `load average` de 17 en el Mac por procesos ajenos (AnyDesk, Claude, WindowServer). En la prueba F7 aislada el máximo fue **74 ms**; en una pasada con el Mac saturado se midió **251 ms**, no reproducible en frío. La prueba deja 350 ms de cabeza para no confundir carga ajena con regresión. No se declara el soak como medida de rendimiento de la app; sí como evidencia de que 19 ciclos seguidos no produjeron errores de consola ni pérdida de datos.

### Errores encontrados y arreglados en F7

| Gravedad | Error | Arreglo |
|---|---|---|
| Grave | El botón Enlace del rail creaba una tarjeta vacía en vez de abrir el diálogo de URL | Enlace abre el diálogo; Imagen abre el selector |
| Grave | Entropía armaba el modo «dibujar marco» y pedía arrastrar, en vez de crear su marco | Solo Marco entra en modo dibujo; Entropía crea su tarjeta |
| Grave | Las tarjetas nuevas caían todas en el centro, apiladas | Búsqueda de hueco libre en diagonal |
| Grave | `pointer-events:none` al arrastrar se comía el `pointerup` y el clic: seleccionar dejaba de funcionar | Se quitó; el destino del drop se calcula por geometría |
| Medio | El aviso emergente empujaba el lienzo y desviaba el zoom hacia el cursor | El toast pasa a overlay fijo |
| Medio | El doble clic en el título no editaba por la captura de puntero del arrastre | La captura se toma solo al superar 3 px de movimiento |

### Pendiente / conocido

| Gravedad | Tema | Nota |
|---|---|---|
| Baja | URL del enlace no editable en el sitio | Excepción declarada; se recrea el enlace |
| Baja | Renombrar proyecto | No existe; solo crear/elegir |
| Baja | Tema claro sin prueba visual | Tokens definidos, no validados en pantalla |
| Baja | FPS bajo carga externa | 50.8 una vez con el Mac ocupado; 60.8 en frío |
| Baja | Publish con vista Libre | Avisa y no publica; es correcto pero conviene explicarlo mejor |

## 10. Capturas antes/después

`REPORTES/capturas-forja2/`:

- `f0-antes.png` / `f0-despues.png` (F0 no cambia UI; se conserva la referencia)
- `f1-antes.png` / `f1-despues.png`
- `f2-antes.png` / `f2-despues.png`
- `f3-antes.png` / `f3-despues.png` y `f3-despues-lod.png` (25 %, LOD)
- `f4-antes.png` / `f4-despues.png`
- `f5-antes.png` / `f5-despues.png`
- `f6-antes.png` / `f6-despues.png`
- `f7-antes.png` / `f7-despues.png`

## 11. Verificación real

| Comprobación | Resultado |
|---|---|
| `npx tsc -b` | limpio |
| `npx vitest run` | 28 archivos, 158 tests |
| `npx oxlint` | 0 errores (warnings preexistentes de `set-state-in-effect`) |
| `npx vite build` | correcto |
| `npx playwright test -c playwright.forja2.config.ts` | 10 tests, 10 pasan |
| `git status` | solo cambios de la campaña + artefactos no versionados previos |

## 12. Evidencia y límites

- **E1:** valores de Sala Oscura con archivo:línea; FPS medidos en este Mac con Brave; tests Playwright reales; `tsc/vitest/oxlint/build` ejecutados.
- **H1:** que la física se sienta «Apple» y que el LOD de 0.35 sea el umbral correcto para Bruno. No hay prueba con usuarios.
- **No verificado:** tema claro en pantalla, VoiceOver, trackpad físico (Playwright simula rueda y puntero), Safari/WebKit nativo y rendimiento en la app de escritorio empaquetada.
- El soak de 15 minutos se ejecutó con backend PDF simulado; el tablero es local y no depende del motor.

## 13. Lo que queda para que Bruno pruebe a mano

1. **Trackpad real** en la app de escritorio (WKWebView): pellizco, dos dedos y la inercia al soltar. Playwright simula rueda y puntero, no el gesto físico.
2. **Tema claro**: activar `data-theme="light"` y revisar contraste y papel de tarjetas en pantalla; los tokens están, pero no se probó visualmente.
3. **Publicar en carpeta real** (diálogo del sistema) además del ZIP que sí se probó.
4. **Teclado y VoiceOver**: recorrer la barra, el rail, las tarjetas y los diálogos; el foco ya se ve, falta la experiencia con lector de pantalla.
5. **Dos decisiones de producto**: si el nombre del proyecto debe poder renombrarse y si la URL de un enlace debe editarse en el sitio o solo al crearlo.

---

**Fase F7:** 100 % (recorrido + soak + informe).
**Campaña Forja 2:** 100 % (8/8 fases, con los cuatro checks y Playwright en cada una).
**Producto usable del sistema nuevo:** 92 % (base: 10 problemas P-D cerrados; quedan renombrar proyecto, URL de enlace editable y prueba visual del tema claro).

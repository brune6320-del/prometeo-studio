# PROMETEO Studio · Sistema de diseño «Forja 2»

> Category: Creative Tools / Visual Board
> Referencia de tono: Apple Human Interface Guidelines, Monument Grotesk + Diatype Mono (ireneguerra.xyz), Milanote.
> Estado: especificación P-D (2026-10-24). **No implementada en la app en este encargo**; este documento es la fuente de verdad para implementarla.

## 1. Tesis visual

Prometeo es un **taller de archivo**, no un panel de administración. La interfaz debe desaparecer y dejar que el papel, las imágenes y las relaciones ocupen el primer plano.

Cinco reglas que mandan sobre el resto:

1. **El lienzo manda, el chrome se aparta.** Herramientas en grafito, contenido en papel cálido. Ningún adorno compite con una tarjeta o una imagen.
2. **Un solo acento: ascua.** El naranja de marca solo señala acción primaria, foco o selección. Todo lo demás es neutro. El azul heredado (`#315c7c`) se retira.
3. **Densidad con aire.** Retícula de 4 pt, controles de 32 px, una sola fila de herramientas. Si un control no cabe, va a «Más», no a una tercera fila.
4. **Dos temperaturas.** Grafito cálido para el chrome; papel cálido para el contenido. Nada de blanco puro sobre negro puro.
5. **El estado se ve sin explicarlo.** Hover, pulsado, seleccionado, arrastrando, foco y deshabilitado tienen una firma distinta. El color nunca es la única señal.

**Baseline aburrido:** el sistema actual ya acierta en lo esencial (grafito cálido, un acento, tarjetas de papel, foco visible). «Forja 2» no cambia la identidad: corrige jerarquía, escala tipográfica, estados y densidad.

## 2. Color

### 2.1 Tema oscuro (por defecto)

| Token | Valor | Uso |
|---|---|---|
| `--surface-0` | `#0f0f11` | Lienzo de la app, fondo del tablero |
| `--surface-1` | `#151518` | Paneles, cabecera, barra de herramientas |
| `--surface-2` | `#1c1c20` | Controles, campos, tarjetas de chrome |
| `--surface-3` | `#24242a` | Hover de controles, elemento elevado |
| `--surface-paper` | `#f7f3ea` | Tarjeta de contenido (papel) |
| `--surface-paper-alt` | `#f1e3c4` / `#dfe9dc` / `#f1dedb` | Variantes arena / salvia / rosa |
| `--line-subtle` | `#2c2c33` | Separadores decorativos |
| `--line-control` | `#6e6e7b` | Borde de control (3.38:1 sobre `--surface-2`) |
| `--fg-1` | `#ededf2` | Texto principal (16.41:1 sobre `--surface-0`) |
| `--fg-2` | `#b9b9c4` | Texto secundario (9.37:1 sobre `--surface-1`) |
| `--fg-3` | `#a0a0ac` | Metadatos (7.05:1 sobre `--surface-1`) |
| `--paper-ink` | `#24221f` | Texto sobre papel (14.33:1 sobre `--surface-paper`) |
| `--paper-muted` | `#6b675f` | Metadatos sobre papel (5.08:1) |
| `--accent` | `#ff8a52` | Ascua: acción primaria, selección, foco |
| `--accent-text` | `#ff9a6a` | Texto de acento sobre oscuro |
| `--accent-soft` | `rgba(255,138,82,0.14)` | Fondo de estado activo/seleccionado |
| `--on-accent` | `#1b0e07` | Texto sobre ascua |
| `--link` | `#ffb38f` | Enlaces (siempre con subrayado) |

### 2.2 Tema claro

| Token | Valor | Uso |
|---|---|---|
| `--surface-0` | `#f3efe7` | Lienzo |
| `--surface-1` | `#fbf9f4` | Paneles |
| `--surface-2` | `#fffdf8` | Controles y tarjetas |
| `--surface-3` | `#f0ebe2` | Hover |
| `--line-subtle` | `#e4dfd5` | Separadores |
| `--line-control` | `#8a857b` | Borde de control (3.61:1 sobre `--surface-2`) |
| `--fg-1` | `#1c1b19` | Texto principal (16.93:1 sobre `--surface-2`) |
| `--fg-2` | `#55524c` | Texto secundario (7.66:1) |
| `--fg-3` | `#746f66` | Metadatos (4.91:1) |
| `--accent` | `#b8491c` | Ascua en claro (5.15:1 sobre `--surface-2`) |
| `--accent-text` | `#a63f17` | Texto de acento (6.18:1) |
| `--accent-soft` | `rgba(184,73,28,0.10)` | Fondo activo |
| `--on-accent` | `#fffdf8` | Texto sobre ascua |
| `--link` | `#a63f17` | Enlaces |

### 2.3 Semánticos (reservados al estado del documento)

| Token | Oscuro | Claro | Uso |
|---|---|---|---|
| `--st-staged` | `#86b4ff` | `#2f5f9e` | Preparado |
| `--st-verified` | `#4fd69c` | `#1e6f4e` | Verificado |
| `--st-reject` | `#f2b84b` | `#8a5a0a` | No aplicable con seguridad |
| `--st-failed` | `#ff7b7b` | `#a12a2a` | Fallo |
| `--st-ocr` | `#bea4ff` | `#5b3fa6` | OCR |

Contrastes medidos con script sRGB/WCAG (E1). Ningún semántico sustituye al ascua: el ascua es interacción; los semánticos son estado del documento.

### 2.4 Papel de las tarjetas

| Token | Valor | Uso |
|---|---|---|
| `--card-paper` | `#f7f3ea` | Tarjeta base |
| `--card-sand` | `#f1e3c4` | Variante cálida |
| `--card-sage` | `#dfe9dc` | Variante fría |
| `--card-rose` | `#f1dedb` | Variante rosada |
| `--card-rule` | `color-mix(in oklab, var(--paper-ink) 18%, transparent)` | Regla superior de 2 px |

Las cuatro variantes existen para **clasificar**, no para decorar. Una biblioteca puede usar una sola variante; el arcoíris de tarjetas no es un sistema.

## 3. Tipografía

### 3.1 Familias y licencias

- **Interfaz y títulos:** `-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", "Helvetica Neue", sans-serif`. En macOS se usa SF Pro del sistema, sin empaquetar.
- **Monoespaciada:** `"JetBrains Mono", "IBM Plex Mono", ui-monospace, "SF Mono", monospace`. JetBrains Mono e IBM Plex Mono son OFL y se pueden empaquetar.
- **Referencia de tono:** ireneguerra.xyz usa `Monument Grotesk Variable` y `Diatype Mono Variable` autoalojadas (E1, comprobado en su CSS). **Son comerciales; no se copian ni se empaquetan.** Se usan solo como referencia métrica y de carácter.
- **Regla:** si una fuente no tiene licencia verificada, no entra en el bundle. El fallback del sistema es parte del diseño, no un accidente.

### 3.2 Escala

| Rol | Token (usar con `font: var(--type-…)`) | Tamaño / línea | Peso | Tracking | Uso |
|---|---|---|---|---|---|
| Display | `--type-display` | 32 / 36 | 650 | -0.02em | Portada, título de proyecto |
| Título | `--type-title` | 22 / 28 | 650 | -0.01em | Cabecera de panel, nombre de tablero |
| Encabezado | `--type-heading` | 17 / 24 | 650 | -0.005em | Título de tarjeta, sección |
| Cuerpo | `--type-body` | 15 / 24 | 400 | 0 | Texto de lectura, formularios |
| Etiqueta | `--type-label` | 13 / 18 | 600 | 0.005em | Botones, campos, navegación |
| Leyenda | `--type-caption` | 12 / 16 | 500 | 0.01em | Metadatos, ayudas, contadores |
| Mono | `--type-mono` | 12 / 18 | 450 | 0 | Fechas, IDs, zoom, código |

**Mínimo absoluto: 12 px.** Se elimina el texto de 8–11 px. Las etiquetas en mayúsculas solo se permiten en metadatos cortos (`--type-caption`, `letter-spacing: 0.06em`), nunca en párrafos ni en botones.

Números tabulares (`font-variant-numeric: tabular-nums`) en contadores, zoom, fechas y listas.

Longitud de medida: 62–72 caracteres. En tarjetas de 320 px, 38–44 caracteres por línea.

## 4. Espaciado y retícula

Base **4 pt**. No se usan valores intermedios arbitrarios.

| Token | Valor | Uso |
|---|---|---|
| `--space-0` | 0 | — |
| `--space-1` | 4 | Separación icono-texto mínima |
| `--space-2` | 8 | Gap entre controles, padding interno de chips |
| `--space-3` | 12 | Padding de tarjeta, gap de lista |
| `--space-4` | 16 | Padding de panel, gap de sección |
| `--space-5` | 20 | Separación de bloques |
| `--space-6` | 24 | Gap entre secciones |
| `--space-8` | 32 | Margen de lienzo |
| `--space-10` | 40 | Separación de capítulos |
| `--space-12` | 48 | Aire de portada / fit del tablero |
| `--space-16` | 64 | Solo portadas y estados vacíos |

**Recetas fijas:**

- Cabecera: `56 px` de alto, padding `0 16 px`, gap `16 px`.
- Barra de herramientas: `44 px` de alto, **una sola fila**, scroll horizontal si hace falta; el resto va a «Más».
- Control: `32 px`; control pequeño: `28 px`; control grande: `40 px`; zona táctil mínima: `44 px`.
- Tarjeta: padding `12 px`, gap interno `8 px`, radio `10 px`.
- Panel: padding `16 px`, separación entre grupos `24 px`.

## 5. Radios

| Token | Valor | Uso |
|---|---|---|
| `--radius-xs` | 4 px | Chips, marcas diminutas |
| `--radius-sm` | 6 px | Badges, inputs compactos |
| `--radius-md` | 8 px | Botones, selects, campos |
| `--radius-lg` | 10 px | Tarjetas |
| `--radius-xl` | 12 px | Paneles, marcos |
| `--radius-2xl` | 16 px | Diálogos, hojas |
| `--radius-pill` | 999 px | Estados, pills, avatares |

No se usa `7 px` ni `9 px`: eran valores de transición del sistema viejo.

## 6. Sombras y elevación

La separación se resuelve primero con superficie y borde; la sombra solo cuando hay elevación real.

| Nivel | Token | Oscuro | Claro | Uso |
|---|---|---|---|---|
| 0 | `--shadow-0` | none | none | Lienzo, paneles planos |
| 1 | `--shadow-1` | `0 1px 2px rgba(0,0,0,.24)` | `0 1px 2px rgba(28,27,25,.08)` | Tarjeta en reposo, campo |
| 2 | `--shadow-2` | `0 8px 24px rgba(0,0,0,.32), 0 2px 6px rgba(0,0,0,.24)` | `0 8px 24px rgba(28,27,25,.12), 0 2px 6px rgba(28,27,25,.08)` | Hover, popover, menú |
| 3 | `--shadow-3` | `0 24px 64px rgba(0,0,0,.45), 0 6px 16px rgba(0,0,0,.28)` | `0 24px 64px rgba(28,27,25,.18), 0 6px 16px rgba(28,27,25,.10)` | Diálogo, tarjeta arrastrada |
| Papel | `--shadow-paper` | `0 1px 2px rgba(0,0,0,.18), 0 12px 32px rgba(0,0,0,.28)` | `0 1px 2px rgba(28,27,25,.10), 0 12px 32px rgba(28,27,25,.14)` | Tarjeta de contenido sobre el lienzo |

Prohibido: halos de color, `box-shadow` de 0 0 0 6px sin función, y sombras distintas para cada tarjeta.

## 7. Estados

| Estado | Token | Regla |
|---|---|---|
| Reposo | `--state-rest` | Superficie base, borde `--line-subtle` o `--line-control` |
| Hover | `--state-hover` | Overlay `rgba(255,255,255,.05)` en oscuro / `rgba(28,27,25,.04)` en claro, 120 ms |
| Pulsado | `--state-pressed` | Overlay `.08` + `translateY(1px)`, 80 ms. Nunca escala |
| Seleccionado | `--state-selected-ring` | `0 0 0 2px var(--accent)` + fondo `--accent-soft` |
| Arrastrando | `--state-drag` | `--shadow-3`, opacidad `0.96`, `cursor: grabbing`, transición 0 ms |
| Destino de drop | `--state-drop` | Borde `1.5px dashed var(--accent)` + fondo `--accent-soft` |
| Foco | `--state-focus-ring` | `0 0 0 2px var(--surface-0), 0 0 0 4px var(--accent)`, offset 2 px |
| Deshabilitado | `--state-disabled` | Opacidad `0.42`; el texto sigue legible; sin hover |
| Cargando | `--state-loading` | Skeleton `--surface-2`, pulso de opacidad 0.6→1, 1.2 s |

**Selección ≠ foco.** La selección es persistente y usa relleno + anillo; el foco es temporal y usa doble anillo. Nunca se usa el mismo trazo para ambos.

## 8. Iconos

- Set: **Lucide** (ya instalado), trazo `1.75 px`, esquinas redondeadas.
- Tamaños: `--icon-sm: 16px` (herramientas), `--icon-md: 18px` (navegación), `--icon-lg: 20px` (cabecera).
- Separación icono-texto: `8 px` (`--space-2`).
- Botón solo-icono: `32 × 32 px`, `aria-label` obligatorio, tooltip con el atajo.
- Un icono por acción. No se mezclan iconos rellenos y de línea.
- Prohibido usar emoji como icono funcional o como sustituto de un estado.

## 9. Movimiento

| Token | Valor | Uso |
|---|---|---|
| `--duration-instant` | 0 ms | Arrastre, pan, zoom directo |
| `--duration-fast` | 120 ms | Hover, foco, selección |
| `--duration-base` | 180 ms | Apertura de panel, toast, cambio de vista |
| `--duration-slow` | 280 ms | Diálogo, hoja, transición de marco |
| `--ease-standard` | `cubic-bezier(.2,0,.2,1)` | Por defecto |
| `--ease-out` | `cubic-bezier(.16,1,.3,1)` | Entradas |
| `--ease-in` | `cubic-bezier(.4,0,1,1)` | Salidas |
| `--ease-emphasis` | `cubic-bezier(.2,.8,.2,1)` | Acento puntual, sin rebote |

Reglas:

1. Solo `transform` y `opacity`. Nunca `top`, `left`, `width` o `height`.
2. Sin rebotes, sin elásticos, sin animaciones infinitas decorativas.
3. El arrastre y el pan son **inmediatos** (0 ms). La inercia, si existe, no debe retrasar el puntero.
4. `prefers-reduced-motion: reduce` → duración `1 ms` y sin desplazamientos.
5. La skill de física (`prometeo-fisica`) **no existe todavía** en el repo; cuando se cree, esta sección debe enlazarla y heredar sus curvas. Mientras tanto, mandan estos tokens.

## 10. Tablero tipo Milanote

### 10.1 Lienzo

| Token | Valor | Uso |
|---|---|---|
| `--board-grid` | 24 px | Retícula visible y snap |
| `--board-snap` | 6 px | Umbral de imán |
| `--board-zoom-min` | 0.25 | Zoom mínimo |
| `--board-zoom-max` | 2 | Zoom máximo |
| `--board-fit-padding` | 48 px | Aire al ajustar todo |
| `--board-lod-zoom` | 0.6 | Por debajo, se oculta el cuerpo y se muestra título + media |
| `--board-card-w` | 320 px | Ancho base de tarjeta |
| `--board-card-media-ratio` | `4 / 3` | Media primero, sin placeholders gigantes |
| `--board-card-pad` | 12 px | Padding interno |
| `--board-card-title` | `var(--type-heading)` | Único rol de título dentro de la tarjeta |
| `--board-empty-h` | 96 px | Vacío de media con acción, nunca un bloque gigante |
| `--board-toolbar-h` | 44 px | Una sola fila |
| `--board-chrome-opacity` | 0 en reposo / 0.65 en hover / 1 en foco | Grip, borrar y colores |
| `--board-frame-line` | `--line-subtle` | Marco en reposo; ascua solo al seleccionar |
| `--board-frame-fill` | `transparent` | Sin velo naranja permanente |

**LOD (nivel de detalle):** a menos de `0.6`, la tarjeta muestra solo título, miniatura y color. El cuerpo, las etiquetas y las lecturas se ocultan. A `0.25` la biblioteca debe seguir siendo reconocible por miniaturas y títulos, no por texto de 9 px.

### 10.2 Jerarquía del tablero

1. **Cabecera (56 px):** volver, proyecto, tablero, estado de guardado. Nada más.
2. **Barra de herramientas (44 px):** «Añadir» primario; «Nueva nota», «Enlace», «Multimedia» secundarios; el resto en «Más».
3. **Lienzo:** marcos y tarjetas. Los marcos no repiten «Ver como» y «Publicar» en cada uno: aparecen al hover o al seleccionar.
4. **Pie (28 px):** contador, zoom, atajos. Sin duplicar el estado de guardado.

### 10.3 Tarjeta

- El título se escribe **una sola vez**. El input del encabezado y el `h3` interior no pueden mostrar el mismo texto a la vez.
- La edición del título ocurre en el sitio, al doble clic. En reposo, el título es texto, no un input disfrazado.
- La media va primero y ocupa el ancho completo. Si no hay imagen, se muestra un vacío de `--board-card-media-ratio` con una acción («Añadir imagen»), no un «Sin imagen» de 74 px.
- Las acciones de la tarjeta (grip, borrar, colores) viven en `--board-chrome-opacity: 0` hasta hover/foco/selección.
- El color de tarjeta se elige desde un control de 4 muestras de 16 px, no desde 4 botones permanentes de 20 px.

## 11. Contraste y accesibilidad

- Texto normal: **≥ 4.5:1**. Texto grande (≥ 24 px o 19 px bold): **≥ 3:1**.
- Bordes de control y foco: **≥ 3:1**.
- Nunca usar color como única señal: añadir icono, subrayado, borde o texto.
- Foco visible en todo lo interactivo, incluido el lienzo y las tarjetas.
- Zona táctil mínima: 44 × 44 px en superficies táctiles; 32 × 32 px con puntero.
- Respetar `prefers-reduced-motion`, `prefers-contrast` y el tamaño de texto del sistema.
- Las tarjetas de papel usan `--paper-ink` y `--paper-muted`; no heredan el texto claro del chrome.

## 12. Voz y microcopy

- Sentence case. Mayúsculas solo en metadatos cortos.
- Verbos directos: «Añadir imagen», «Guardar copia», «Volver a mirar».
- El estado se dice una vez: «Guardado», no «Guardado» + «Sin cambios» + badge.
- Los errores dicen qué pasó y qué hacer; no culpan al usuario.
- Nada de jerga interna en la interfaz de usuario (`STAGED`, `HONEST_REJECT` solo en modo técnico).

## 13. Tokens CSS

```css
:root {
  color-scheme: dark;

  --surface-0: #0f0f11;
  --surface-1: #151518;
  --surface-2: #1c1c20;
  --surface-3: #24242a;
  --surface-paper: #f7f3ea;
  --surface-paper-alt: #f1e3c4;
  --line-subtle: #2c2c33;
  --line-control: #6e6e7b;
  --fg-1: #ededf2;
  --fg-2: #b9b9c4;
  --fg-3: #a0a0ac;
  --paper-ink: #24221f;
  --paper-muted: #6b675f;
  --accent: #ff8a52;
  --accent-text: #ff9a6a;
  --accent-soft: rgba(255, 138, 82, 0.14);
  --on-accent: #1b0e07;
  --link: #ffb38f;

  --st-staged: #86b4ff;
  --st-verified: #4fd69c;
  --st-reject: #f2b84b;
  --st-failed: #ff7b7b;
  --st-ocr: #bea4ff;

  --font-ui: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", "Helvetica Neue", sans-serif;
  --font-mono: "JetBrains Mono", "IBM Plex Mono", ui-monospace, "SF Mono", monospace;
  --type-display: 650 32px/36px var(--font-ui);
  --type-title: 650 22px/28px var(--font-ui);
  --type-heading: 650 17px/24px var(--font-ui);
  --type-body: 400 15px/24px var(--font-ui);
  --type-label: 600 13px/18px var(--font-ui);
  --type-caption: 500 12px/16px var(--font-ui);
  --type-mono: 450 12px/18px var(--font-mono);
  --tracking-label: 0.06em;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 10px;
  --radius-xl: 12px;
  --radius-2xl: 16px;
  --radius-pill: 999px;

  --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.24);
  --shadow-2: 0 8px 24px rgba(0, 0, 0, 0.32), 0 2px 6px rgba(0, 0, 0, 0.24);
  --shadow-3: 0 24px 64px rgba(0, 0, 0, 0.45), 0 6px 16px rgba(0, 0, 0, 0.28);
  --shadow-paper: 0 1px 2px rgba(0, 0, 0, 0.18), 0 12px 32px rgba(0, 0, 0, 0.28);

  --state-hover: rgba(255, 255, 255, 0.05);
  --state-pressed: rgba(255, 255, 255, 0.08);
  --state-selected-ring: 0 0 0 2px var(--accent);
  --state-focus-ring: 0 0 0 2px var(--surface-0), 0 0 0 4px var(--accent);
  --state-drop: 1.5px dashed var(--accent);
  --state-disabled: 0.42;

  --icon-sm: 16px;
  --icon-md: 18px;
  --icon-lg: 20px;
  --icon-gap: 8px;

  --duration-instant: 0ms;
  --duration-fast: 120ms;
  --duration-base: 180ms;
  --duration-slow: 280ms;
  --ease-standard: cubic-bezier(0.2, 0, 0.2, 1);
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-emphasis: cubic-bezier(0.2, 0.8, 0.2, 1);

  --header-h: 56px;
  --control-h: 32px;
  --control-h-sm: 28px;
  --control-h-lg: 40px;
  --touch-target: 44px;

  --board-grid: 24px;
  --board-snap: 6px;
  --board-zoom-min: 0.25;
  --board-zoom-max: 2;
  --board-fit-padding: 48px;
  --board-lod-zoom: 0.6;
  --board-card-w: 320px;
  --board-card-media-ratio: 4 / 3;
  --board-card-pad: 12px;
  --board-card-title: var(--type-heading);
  --board-empty-h: 96px;
  --board-toolbar-h: 44px;
  --board-chrome-opacity: 0;
  --board-frame-line: var(--line-subtle);
  --board-frame-fill: transparent;

  /* Alias de migración: el código viejo sigue leyendo estos nombres. */
  --bg-0: var(--surface-0);
  --bg-1: var(--surface-1);
  --bg-2: var(--surface-2);
  --bg-3: var(--surface-3);
  --bg-canvas: var(--surface-0);
  --line: var(--line-subtle);
  --line-strong: var(--line-control);
  --text-1: var(--fg-1);
  --text-2: var(--fg-2);
  --text-3: var(--fg-3);
  --ember: var(--accent);
  --ember-text: var(--accent-text);
  --ember-soft: var(--accent-soft);
  --on-ember: var(--on-accent);
  --font-sans: var(--font-ui);
}

[data-theme='light'] {
  color-scheme: light;

  --surface-0: #f3efe7;
  --surface-1: #fbf9f4;
  --surface-2: #fffdf8;
  --surface-3: #f0ebe2;
  --line-subtle: #e4dfd5;
  --line-control: #8a857b;
  --fg-1: #1c1b19;
  --fg-2: #55524c;
  --fg-3: #746f66;
  --accent: #b8491c;
  --accent-text: #a63f17;
  --accent-soft: rgba(184, 73, 28, 0.1);
  --on-accent: #fffdf8;
  --link: #a63f17;

  --st-staged: #2f5f9e;
  --st-verified: #1e6f4e;
  --st-reject: #8a5a0a;
  --st-failed: #a12a2a;
  --st-ocr: #5b3fa6;

  --shadow-1: 0 1px 2px rgba(28, 27, 25, 0.08);
  --shadow-2: 0 8px 24px rgba(28, 27, 25, 0.12), 0 2px 6px rgba(28, 27, 25, 0.08);
  --shadow-3: 0 24px 64px rgba(28, 27, 25, 0.18), 0 6px 16px rgba(28, 27, 25, 0.1);
  --shadow-paper: 0 1px 2px rgba(28, 27, 25, 0.1), 0 12px 32px rgba(28, 27, 25, 0.14);

  --state-hover: rgba(28, 27, 25, 0.04);
  --state-pressed: rgba(28, 27, 25, 0.07);
  --state-focus-ring: 0 0 0 2px var(--surface-2), 0 0 0 4px var(--accent);
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --duration-fast: 1ms;
    --duration-base: 1ms;
    --duration-slow: 1ms;
  }
}
```

## 14. Cómo lo usan los agentes

Orden de lectura: **este DESIGN.md → skill de la tarea → código existente**.

| Necesidad | Skill copiada | Cuándo |
|---|---|---|
| Construir o refinar interfaz | `.agents/skills/od-frontend-design/` | Pantallas, componentes, estados, jerarquía |
| Movimiento e interacción | `.agents/skills/od-emilkowalski-motion/` | Microinteracciones, transiciones, reduced motion |
| Tipografía y restraint | `.agents/skills/od-minimalist-skill/` | Escala, pesos, aire, paleta monocroma |
| Crítica y pulido | `.agents/skills/od-impeccable-design-polish/` | Auditoría visual, antes/después, anti-slop |
| Reglas del tablero | `.agents/skills/prometeo-tablero/` | Modelo, vistas, guardado, historial |

Reglas de convivencia:

1. Si el código contradice este documento, gana este documento hasta que se implemente; el agente debe decir qué cambió.
2. Si una skill contradice este documento, gana este documento.
3. Ningún agente implementa el tema claro sin probar contraste en ambos temas.
4. Ningún agente añade una fuente sin licencia verificada.

## 15. Deuda declarada

- **No implementado:** este encargo no toca código de app. Los tokens existen solo en este documento.
- **Tema claro:** especificado y medido, sin implementar ni probar en pantalla.
- **Fuentes:** Monument Grotesk y Diatype Mono son comerciales; no se han comprado ni empaquetado. La app usa SF Pro del sistema y caerá a JetBrains Mono / IBM Plex Mono.
- **Física:** `prometeo-fisica` no existe en `.agents/skills/` ni en `~/Desktop/deepseek-trabajo/prometeo/skills/`. El enlace queda pendiente; no se inventa.
- **Medición:** los contrastes son cálculo sRGB/WCAG (E1), no medición con colorímetro. El LOD y las duraciones son H1 hasta que se prueben con usuarios.

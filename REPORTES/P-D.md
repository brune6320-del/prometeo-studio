# Reporte P-D · Sistema de diseño de Prometeo con Open Design

| Campo | |
|---|---|
| Fase | P-D · diseño |
| Rama | `studio/collage` |
| Base | `2deb6e4` (`studio: semilla de referentes verificada (R-2)`) |
| Alcance | **No se tocó código de la app.** Solo skills, documentación y capturas. |
| Evidencia | E1 en clon, licencias, inventario, capturas, CSS medido y contrastes calculados. H1 en la eficacia de los tokens (no implementados). |

## 1. Open Design: clon y licencia

- Ruta: `~/Projects/open-design`
- Repo: https://github.com/nexu-io/open-design
- Commit: `9724c44142ea0afaee3d207f37901b31c66a44ad` (2026-10-24 13:46 UTC, clon `--depth 1`)
- Licencia comprobada en `LICENSE`: **Apache License 2.0**. El `README.md` y el badge del repo también declaran Apache-2.0.
- Inventario completo: [`REPORTES/P-D-inventario.md`](P-D-inventario.md)
  - **169 skills** (carpetas con `SKILL.md`).
  - **152 sistemas de diseño** con `DESIGN.md` (153 carpetas; `_schema` no es un sistema).
  - Referencias directas para este encargo: `design-systems/apple/DESIGN.md` y `design-systems/application/DESIGN.md`.

## 2. Skills elegidas (4)

| Categoría | Skill | Copia en Prometeo | Licencia | Por qué |
|---|---|---|---|---|
| Interfaz | `frontend-design` | `.agents/skills/od-frontend-design/` | Apache-2.0 | Dirección visual, jerarquía, tipografía, estados reales y código de producción. |
| Movimiento / interacción | `emilkowalski-motion` | `.agents/skills/od-emilkowalski-motion/` | Apache-2.0 (repo) | 140–220 ms, solo `transform`/`opacity`, sin bucles decorativos, `prefers-reduced-motion`. |
| Tipografía | `minimalist-skill` | `.agents/skills/od-minimalist-skill/` | MIT (© 2026 Leonxlnx) | Arquitectura tipográfica, restraint, monocromo cálido, iconografía y micro-animación. |
| Crítica | `impeccable-design-polish` | `.agents/skills/od-impeccable-design-polish/` | Apache-2.0 (repo) | Modos Audit / Critique / Polish, anti-slop, jerarquía, type scale y accesibilidad. |

Cada carpeta lleva `PROCEDENCIA.md` con repo, commit, fecha, licencia, upstream declarado y SHA-256 de `SKILL.md`.

**Descartadas a propósito:** `apple-hig`, `design-review` y `design-md` son **fichas de catálogo** en Open Design: su `SKILL.md` solo remite a un repo externo y no contiene flujo ejecutable. Copiarlas habría dado cuatro carpetas bonitas y ninguna crítica real. `web-design-guidelines` (MIT) era la alternativa para auditoría técnica, pero se quedó fuera del límite de 4; su checklist de contraste y accesibilidad está resumido en `DESIGN.md`.

## 3. `docs/STUDIO/DESIGN.md`

Documento de 468 líneas y 15 secciones, en el formato de Open Design (prosa canónica + tokens + reglas para agentes).

Decisiones principales:

- **«Forja 2»**: se conserva la identidad grafito cálido + ascua; se corrige jerarquía, escala, densidad y estados.
- **Un solo acento**: ascua para interacción; los azules heredados (`#315c7c`) se retiran.
- **Dos temas**: oscuro por defecto y claro `[data-theme="light"]`, con contrastes WCAG medidos.
- **Tipografía mínima de 12 px**; se eliminan los textos de 8–11 px.
- **Retícula de 4 pt**, controles de 32 px, cabecera de 56 px, barra de herramientas de 44 px y una sola fila.
- **Estados separados**: hover, pulsado, seleccionado (anillo + relleno), foco (doble anillo), arrastrando, drop, deshabilitado, cargando.
- **Tablero**: LOD a `0.6`, tarjeta de 320 px, media 4:3, chrome solo en hover/foco/selección, marcos discretos.
- **Movimiento**: 0/120/180/280 ms, sin rebote, `prefers-reduced-motion`.

**Fuentes:** ireneguerra.xyz usa `Monument Grotesk Variable` y `Diatype Mono Variable` autoalojadas (E1, visto en su CSS). Son comerciales: **no se copian ni se empaquetan**. Prometeo usa SF Pro del sistema y cae a Inter / JetBrains Mono / IBM Plex Mono (OFL) si hace falta.

**`prometeo-fisica`:** no existe ni en `.agents/skills/` ni en `~/Desktop/deepseek-trabajo/prometeo/skills/`. No se inventó el enlace; `DESIGN.md` deja la sección de movimiento preparada para heredar sus curvas cuando exista.

## 4. Crítica visual de la app actual

Método: `npm run dev` en `studio/frontend` (Vite, puerto 5199) y Playwright con Brave headless (`/Applications/Brave Browser.app`) a 1440×900 y `deviceScaleFactor: 2`. No se descargó Chromium. Capturas:

1. [`REPORTES/capturas-P-D/01-biblioteca.png`](capturas-P-D/01-biblioteca.png) — Biblioteca completa (ajuste al 25 %).
2. [`REPORTES/capturas-P-D/02-referente.png`](capturas-P-D/02-referente.png) — ficha de referente a 93 %, con una tarjeta seleccionada.
3. [`REPORTES/capturas-P-D/03-barra.png`](capturas-P-D/03-barra.png) — barra superior y tres filas de herramientas.

La captura 02 conserva el aviso «El motor PDF se está iniciando». Es incidental (el backend arranca en paralelo) y no forma parte del diseño del tablero.

### Lo que ya funciona

- El par grafito cálido / papel cálido tiene carácter y no se parece a un dashboard genérico.
- El foco visible en ascua es claro y consistente.
- Las tarjetas de papel se leen bien cuando están a escala.
- El estado vacío del tablero («Tu espacio de ideas está listo») es honesto y tiene una acción.

### Los 10 problemas más graves

1. **La barra de herramientas ocupa tres filas y 132 px de alto.**
   A 1440 px, más de 30 controles se envuelven en tres filas; el lienzo pierde un tercio de la pantalla antes de empezar. No hay scroll horizontal ni menú «Más»: todo compite a la vez.  
   **Tokens:** `--board-toolbar-h: 44px`, `--control-h: 32px`, `--space-2: 8px`.

2. **No hay jerarquía de acciones.**
   «Añadir», «Nueva nota», «Exportar JSON», «Obsidian Markdown» y «Eliminar selección» tienen el mismo borde, fondo y tamaño. El único naranja es «Añadir», pero el resto sigue pareciendo primario; «Eliminar selección» deshabilitado se lee como activo.  
   **Tokens:** `--accent`, `--surface-2`, `--fg-3`, `--state-disabled: 0.42`.

3. **Microtipografía de 8–11 px y mayúsculas por todas partes.**
   `POR QUÉ LO GUARDÉ` (8–9 px), `media 11 · s.f.` (10 px), `Guardado` (11 px), pestañas (9 px) y herramientas (11 px). En una app de archivo, los metadatos son contenido, no letra pequeña.  
   **Tokens:** `--type-caption: 500 12px/16px`, `--fg-3`, `--tracking-label: 0.06em`.

4. **El título de la tarjeta aparece dos veces.**
   En la ficha: «Letterform Archive» en el input del encabezado y otra vez como `h3` inmediatamente debajo. Ocupa espacio, duplica la jerarquía y hace dudar de cuál se edita.  
   **Tokens:** `--type-heading`, `--board-card-title` (un solo rol y un solo sitio; input solo en edición).

5. **El vacío de imagen domina la ficha y no ofrece una acción.**
   Un bloque `Sin imagen` de un tercio de la tarjeta, con borde discontinuo y texto gris, ocupa el lugar de la imagen sin decir qué hacer. En una biblioteca visual, la media es el argumento principal.  
   **Tokens:** `--board-card-media-ratio: 4 / 3`, `--board-empty-h: 96px`, `--surface-paper-alt`, `--radius-lg: 10px`.

6. **El azul heredado compite con el ascua.**
   Las pestañas activas (`#315c7c`) y los enlaces «Fuente» usan un azul que no pertenece a la marca. Hay dos acentos en la misma tarjeta: naranja en la selección, azul en la pestaña y en el enlace.  
   **Tokens:** `--accent`, `--link`, `--accent-soft`; se elimina el azul de Interfaz.

7. **El chrome de la tarjeta está siempre encendido.**
   Grip, aspa de borrar y cuatro muestras de color visibles en todas las tarjetas, incluso a 25 %. Añaden ruido y hacen que la tarjeta parezca un formulario.  
   **Tokens:** `--board-chrome-opacity: 0` en reposo, `0.65` en hover, `1` en foco/selección; `--state-hover`.

8. **Los marcos son naranjas, discontinuos y repiten controles.**
   Cada marco tiene borde naranja punteado, «Ver como», «Publicar» y un aspa. Tres marcos repiten el mismo chrome tres veces y compiten con las tarjetas.  
   **Tokens:** `--board-frame-line: var(--line-subtle)`, `--board-frame-fill: transparent`, `--board-chrome-opacity`; controles solo al hover/selección.

9. **Selección y foco usan el mismo trazo.**
   La tarjeta seleccionada y cualquier elemento enfocado llevan un contorno ascua de 2 px. El usuario no puede distinguir «esto está seleccionado» de «el teclado está aquí».  
   **Tokens:** `--state-selected-ring` (anillo + `--accent-soft`) y `--state-focus-ring` (doble anillo con offset de 2 px).

10. **No hay LOD: al 25 % todo el texto se dibuja, pero no se lee.**
    En la vista de Biblioteca, las tarjetas miden 81 px de ancho y siguen pintando título, pestañas, metadatos y «Por qué lo guardé» a 8–10 px. El ajuste muestra la estructura, no la biblioteca.  
    **Tokens:** `--board-lod-zoom: 0.6`, `--board-fit-padding: 48px`, `--type-caption`; por debajo de 0.6, título + media + color, nada de cuerpo.

## 5. Copia a `~/Desktop/deepseek-trabajo/prometeo/skills/`

- `DESIGN.md` → `~/Desktop/deepseek-trabajo/prometeo/skills/DESIGN.md`
- `od-frontend-design/`, `od-emilkowalski-motion/`, `od-minimalist-skill/`, `od-impeccable-design-polish/` → misma ruta.

Verificado con `diff -q` y `diff -rq`: copia idéntica al repo.

## 6. Verificación real

| Comprobación | Resultado |
|---|---|
| `git -C ~/Projects/open-design rev-parse HEAD` | `9724c44142ea0afaee3d207f37901b31c66a44ad` |
| `head -20 ~/Projects/open-design/LICENSE` | Apache License 2.0 |
| Skills inventariadas | 169 |
| Sistemas con `DESIGN.md` | 152 |
| `shasum -a 256` de los 4 `SKILL.md` | registrado en cada `PROCEDENCIA.md` |
| `git diff --stat -- studio` | vacío: **no se tocó código versionado de la app**. `git status` solo muestra `studio/backend/__pycache__/` y `studio/workspace/`, generados al arrancar el backend antes de este encargo. |
| `diff -q docs/STUDIO/DESIGN.md ~/Desktop/.../DESIGN.md` | sin diferencias |
| `diff -rq .agents/skills/od-* ~/Desktop/.../od-*` | sin diferencias |
| Capturas | 3 PNG, 1440×900 @2x |
| Contraste | cálculo sRGB/WCAG con script; pares principales entre 4.91:1 y 16.93:1 |

No se ejecutaron `tsc`, `vitest`, `oxlint` ni `vite build` porque **no se modificó código**. El servidor de desarrollo se usó solo para capturar; se dejó corriendo en el puerto 5199 y puede cerrarse con `pkill -f "vite --port 5199"`.

## 7. Lo que queda sin verificar

- **Eficacia de los tokens (H1):** no están implementados; no hay antes/después de la app.
- **Tema claro:** especificado y medido, pero no existe en la app ni se probó en pantalla.
- **Fuentes:** Monument Grotesk y Diatype Mono son comerciales y no están licenciadas ni empaquetadas. Las sustitutas OFL no se han probado renderizadas.
- **`prometeo-fisica`:** no existe; el enlace queda pendiente.
- **Accesibilidad real:** no se probó con VoiceOver, teclado completo ni `prefers-reduced-motion` en dispositivo.
- **Capturas:** la ficha conserva el aviso de arranque del motor PDF; conviene repetirla con el backend ya listo.

## 8. Archivos

- `.agents/skills/od-frontend-design/` (+ `PROCEDENCIA.md`)
- `.agents/skills/od-emilkowalski-motion/` (+ `PROCEDENCIA.md`)
- `.agents/skills/od-minimalist-skill/` (+ `PROCEDENCIA.md`)
- `.agents/skills/od-impeccable-design-polish/` (+ `PROCEDENCIA.md`)
- `docs/STUDIO/DESIGN.md`
- `REPORTES/P-D.md`
- `REPORTES/P-D-inventario.md`
- `REPORTES/capturas-P-D/01-biblioteca.png`
- `REPORTES/capturas-P-D/02-referente.png`
- `REPORTES/capturas-P-D/03-barra.png`

Commit: `diseño: sistema de diseño con Open Design (P-D)`. Sin push.

---

**Fase P-D:** 100 % (5/5 entregables: clon+licencia, skills, DESIGN.md, crítica, copia a Desktop).
**Campaña studio/collage:** 89 % (17/19: 16 reportes H/R/V + P-D; base: 18 encargos de `campana-2-entropia` + P-D; faltan REA-1 y V-6).
**Producto usable del sistema nuevo:** 0 % (solo especificación; 0 tokens en código).

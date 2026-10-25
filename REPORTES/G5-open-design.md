# G5 · Open Design y open-codesign

| Campo | |
|---|---|
| Rama | `studio/collage` |
| Fecha | 2026-10-25 |
| Repos estudiados | `~/Projects/open-design` · commit `9724c44` (Apache-2.0) |
| | `~/Projects/open-codesign` · commit `4cf3393` (MIT) |
| Licencias | Verificadas en `LICENSE` y `NOTICE` de cada repo. Detalle y procedencia en `PROCEDENCIA.md`. |

## 1. Lo que se estudió (E1: archivos leídos, no marketing)

### open-design (Apache-2.0)

- **Catálogo de 151 sistemas de diseño** en `design-systems/`. Cada paquete es una carpeta con `manifest.json` + `DESIGN.md` + `tokens.css`; los ricos añaden `USAGE.md`, `components.html`, `preview/` y derivados.
- El **manifiesto es la fuente de descubrimiento**: `schemaVersion`, `id` igual al slug, `name`, `category`, `description`, `source` y rutas declaradas (`files.design`, `files.tokens`). El daemon escanea el catálogo en cada petición; no hay base de datos que actualizar.
- Precedencia de metadatos: `metadata.json` de usuario → manifiesto → H1/`> Category:` del Markdown → carpeta. Un formato legado sigue funcionando.
- **Skills** en `skills/`: `SKILL.md` con frontmatter tipo Claude Code (`name`, `description`, `triggers`) y extensiones `od:` (modo, superficie, categoría, preview, ejemplo, requisitos de sistema de diseño y craft). El cuerpo es el flujo de trabajo.
- **Dos registros separados**: skills funcionales (`/api/skills`) y plantillas de render (`/api/design-templates`). Los recursos se indexan primero y el cuerpo completo se carga solo cuando el agente lo pide (divulgación progresiva).
- El sistema de diseño activo se **compone en el prompt** junto con la skill y las referencias de craft.

### open-codesign (MIT)

- **Skills** con `SKILL.md` y frontmatter v1; un parser propio de YAML resuelve escalares, secuencias y bloques. `loadSkillsFromDir` recorre carpetas, prioriza skills de usuario y deduplica por `name`.
- **Design skills** distintas: módulos JSX completos en `templates/design-skills/` con una pista `// when_to_use:` al inicio. El agente los abre desde el sistema de archivos y los adapta; no son componentes instalados.
- **De prompt a prototipo**: preflight compacto (solo bloquea hechos no inferibles) → contexto de diseño con *brief* estructurado y presupuesto de caracteres → prompt de sistema por secciones en Markdown (`identity`, `workflow`, `output-rules`, `design-methodology`, `pre-flight`, `safety`…) → bucle de agente con herramientas `skill`, `scaffold`, `preview`, `tweaks`, `done`. `preview` es la comprobación visual/runtime y `done` la puerta final que devuelve errores reparables. El modelo ve índices de recursos; los cuerpos se cargan bajo demanda.
- El estado del proyecto vive en el espacio de trabajo (archivos + `DESIGN.md` + memoria), no en un formato propietario.

## 2. Qué se aplica a Prometeo

### a) «+ Más» como biblioteca navegable

Hoy es una lista plana de 10 herramientas. Pasa a ser un panel con:

- **Buscador** por nombre, descripción y palabras clave.
- **Categorías** (Todas, Escribir, Medios, Estructura, Referencias, Collage) como filtros visibles.
- **Lista + vista previa**: al elegir una herramienta se ve su icono, nombre, categoría, descripción, para qué sirve y un botón «Añadir al tablero». Doble clic también añade.
- Navegación con ↑/↓ y Enter; foco inicial en el buscador; estado vacío claro.
- La lista se deriva del **registro de herramientas**, no de una copia: una herramienta nueva aparece sola. La metadata de catálogo vive en `board/tools/library.ts` y se valida contra el registro.

### b) Sistema de diseño por tablero

- Se guarda `sistema: 'forja' | 'irene'` en `BoardDocument` (compatible con tableros viejos: sin campo = Forja 2).
- Selector «Sistema» en la cabecera del tablero.
- `data-design-system` en el elemento raíz mientras el tablero está abierto: alcanza también a los portales (pliego, caja de luz, diálogos).
- **Forja 2**: los tokens actuales.
- **Archivo Irene**: sistema propio inspirado en la referencia, no una copia: papel blanco, tinta casi negra, gris de etiqueta, mono pequeña, radios mínimos, sombras casi nulas, retícula más fina y líneas punteadas. Se implementa solo con tokens; ningún componente nuevo.
- El cambio se guarda, se deshace con el historial del tablero y sobrevive a recargar.

## 3. Lo que NO se copia

- No se copian textos, imágenes, marca, sistemas de diseño ni skills de ninguno de los dos repos.
- No se copia el parser YAML, el runtime de agentes, el sandbox ni el pipeline de modelos.
- Si en el futuro se copia código, solo será MIT/Apache y quedará anotado en `PROCEDENCIA.md` con archivo, commit y licencia. En esta fase no se copia código literal: se reimplementan ideas con código propio.

## 4. Archivos previstos

- Nuevo `PROCEDENCIA.md` en la raíz del repo.
- Nuevo `studio/frontend/src/board/tools/library.ts` (catálogo y filtro puros).
- `studio/frontend/src/board/tools/menu.tsx`: panel con búsqueda, categorías y vista previa.
- Nuevo `studio/frontend/src/board/diseno.ts`: catálogo `forja`/`irene` y normalización.
- `studio/frontend/src/board/model.ts`: campo `sistema` en `BoardDocument`, `createBoard` y `normalizeBoard`.
- `studio/frontend/src/styles/tokens.css`: bloque `:root[data-design-system='irene']`.
- `studio/frontend/src/components/BoardWorkspace.tsx`: selector, efecto de atributo y guardado.
- `studio/frontend/src/components/board.css`: estilos del panel y del sistema Irene.
- Tests: `src/tests/library.test.ts`, ampliación de `tokens.test.ts`/`boardModel.test.ts`, E2E `e2e-forja3/g5-biblioteca.spec.ts`.

## 5. Verificación prevista

1. `npx tsc -b`
2. `npx vitest run`
3. `npx oxlint`
4. `npx vite build`
5. `npx playwright test -c playwright.forja3.config.ts g5-biblioteca.spec.ts`
6. Capturas `g5-antes-mas.png`, `g5-despues-mas.png`, `g5-despues-irene.png`.

## 6. Límites que se dirán en el cierre

- El sistema Irene cambia tokens, no la estructura de cada herramienta; algunos componentes conservan geometría propia.
- La biblioteca no instala herramientas externas ni lee skills del disco: cataloga el registro local.
- No se copió código de los repos; `PROCEDENCIA.md` lo declara con commits y licencias.
- La vista previa de cada herramienta es descriptiva (icono + texto), no un iframe con una demo viva.

# Procedencia · G5 Open Design y open-codesign

Este documento registra qué se estudió de cada repositorio, con qué licencia y
qué código se reutilizó. Regla de la campaña: solo se copia código MIT o
Apache-2.0, y toda copia queda aquí con archivo, commit y licencia.

Fecha de revisión: 2026-10-25.

## 1. open-design

| Campo | Valor |
|---|---|
| Origen | https://github.com/nexu-io/open-design |
| Ruta local | `~/Projects/open-design` |
| Commit revisado | `9724c44142ea0afaee3d207f37901b31c66a44ad` |
| Licencia | Apache License 2.0 (`LICENSE`) |
| Copyright | Los autores de OpenDesign, según `LICENSE` y `CONTRIBUTING.md` |

**Qué se estudió**

- `design-systems/`: 151 paquetes con `manifest.json`, `DESIGN.md` y `tokens.css`; manifiesto como fuente de descubrimiento y precedencia de metadatos.
- `design-systems/_schema/`: contrato del manifiesto y de los tokens.
- `skills/`: `SKILL.md` con frontmatter Claude Code y extensiones `od:` (modo, superficie, categoría, preview, requisitos de sistema de diseño).
- `plugins/` y `docs/skills-protocol.md`, `docs/design-systems.md`: separación entre skills funcionales, plantillas de render y sistemas de diseño; divulgación progresiva.

**Qué se copió**

Nada. No se copió código, texto, imagen, sistema de diseño ni skill de este
repositorio. Las ideas se reimplementaron en código propio de Prometeo:
`src/board/tools/library.ts`, `src/board/diseno.ts`, el panel de biblioteca y el
bloque `[data-design-system='irene']` de `src/styles/tokens.css`.

## 2. open-codesign

| Campo | Valor |
|---|---|
| Origen | https://github.com/OpenCoworkAI/open-codesign |
| Ruta local | `~/Projects/open-codesign` |
| Commit revisado | `4cf33932edc5f687e3cf7190261ebbb02c898d08` |
| Licencia | MIT (`LICENSE`) |
| Copyright | Copyright (c) 2026 OpenCoworkAI Contributors |
| Avisos adicionales | `NOTICE` cita pi-ai, Electron, pptxgenjs, dom-to-pptx y esbuild, todos MIT |

**Qué se estudió**

- `packages/core/src/skills/`: frontmatter v1, parser YAML acotado, carga por directorio y prioridad de skills de usuario.
- `packages/core/src/design-skills/`: snippets JSX con pista `// when_to_use:` que el agente abre y adapta.
- `packages/core/src/prompts/`: prompt de sistema por secciones Markdown, composición determinista y divulgación progresiva.
- `packages/core/src/design-context.ts`, `agent.ts`, `tools/` y `docs/VISION.md`: brief estructurado, presupuesto de contexto, herramientas `skill`, `scaffold`, `preview`, `tweaks`, `done` y puerta de verificación.

**Qué se copió**

Nada. No se copió código, prompt, skill, plantilla JSX ni texto. La biblioteca
de herramientas y el selector de sistema de diseño son implementaciones propias
de Prometeo.

## 3. Código nuevo de Prometeo en esta fase

| Archivo | Autoría | Inspiración |
|---|---|---|
| `studio/frontend/src/board/tools/library.ts` | Prometeo | Catálogo navegable y filtros; el registro sigue siendo la fuente de herramientas |
| `studio/frontend/src/board/tools/menu.tsx` | Prometeo | Búsqueda + categorías + vista previa |
| `studio/frontend/src/board/diseno.ts` | Prometeo | Sistemas de diseño por tablero |
| `studio/frontend/src/styles/tokens.css` (bloque `irene`) | Prometeo | Tono del Lienzo Archivo documentado en `docs/STUDIO/04-LIENZO-ARCHIVO.md` |
| `studio/frontend/src/components/BoardWorkspace.tsx` (selector y atributo) | Prometeo | Persistencia por tablero |

## 4. Cómo añadir una copia en el futuro

1. Comprobar que la licencia es MIT o Apache-2.0 y que el archivo lo declara.
2. Copiar el aviso de copyright completo.
3. Añadir aquí: repositorio, commit, ruta original, ruta destino y licencia.
4. Si es Apache-2.0, conservar también el `NOTICE` que corresponda.

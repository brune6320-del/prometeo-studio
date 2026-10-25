# G7 · Detalles

| Campo | |
|---|---|
| Rama | `studio/collage` |
| Fecha | 2026-10-25 |
| Base | G6 cerrada en `4c335d6` |
| Alcance | Renombrar, URL, atajos, plantillas y gestos |

## 1. Qué se hizo

### Renombrar proyecto con doble clic

- Doble clic en el selector de proyecto del tablero abre un campo en el sitio.
- `Enter` o salir del campo guarda; `Esc` cancela. El nombre se limpia y se limita a 120 caracteres.
- Se persiste en el registro del proyecto (IndexedDB) y sobrevive a recargar. La operación conserva tableros, gustos, referencias y plantillas.

### Editar la URL de un enlace con doble clic

- La URL de una tarjeta de enlace se muestra siempre (también cuando hay vista previa) y se edita con doble clic.
- Se valida antes de guardar: solo `http://` o `https://`. Una dirección inválida muestra un aviso en la propia tarjeta y no sustituye la anterior.
- El enlace se abre desde una flecha aparte, para que el doble clic no navegue mientras se edita.

### Panel «?»

- Botón `?` en la barra del tablero y atajo `?` (o `⇧ /`).
- Agrupa los atajos reales en Lienzo, Tarjetas y Vistas: arrastrar el fondo, `Espacio` + arrastrar, rueda/dos dedos, `⌘/Ctrl` + rueda, `N`, doble clic para renombrar o editar URL, `Alt` + arrastrar, `⇧` + clic, deshacer/rehacer, pliego, flechas y `Esc`.
- `Esc` cierra el panel.

### Plantillas fuera de `localStorage`

- Las plantillas guardadas ya no viven en la clave global `prometeo-studio-plantillas-v1`.
- Al cargar un proyecto, las plantillas antiguas se migran a `project.plantillas` en IndexedDB y la clave global se borra; el aviso dice cuántas se movieron y a qué proyecto.
- Guardar y borrar plantillas opera sobre el proyecto activo y sobrevive a recargar. Las cuatro plantillas incluidas siguen siendo locales y no se escriben en el proyecto.
- Compatibilidad: un proyecto antiguo sin `plantillas` se normaliza a `[]`; un registro futuro se sigue rechazando sin reinterpretarlo.

### Rectángulo sin `⇧` y pan con `Espacio`

- **Arrastrar el fondo** ahora selecciona con rectángulo, sin modificador.
- **`Espacio` + arrastrar** mueve el lienzo (también sobre tarjetas y marcos), con cursor `grab`/`grabbing`.
- **Rueda o dos dedos** sigue moviendo el lienzo; `⇧` + arrastrar añade al rectángulo en vez de sustituir la selección.
- Un paneo ya no borra la selección: el clic posterior al arrastre se suprime.
- Se actualizó el test de G1 que usaba el arrastre simple como paneo; ahora usa `Espacio` + arrastrar.

### Cabecera a 1280

Al añadir el botón `?`, la barra del tablero se quedaba sin sitio y el buscador tapaba los botones de crear/importar/eliminar. Por debajo de 1380 px la cabecera **envuelve en dos filas** en vez de recortar controles; a 1440 sigue en una fila. No se ocultó ninguna acción.

## 2. Archivos

- `src/components/BoardWorkspace.tsx`: renombrar proyecto, panel de atajos, migración de plantillas, `Espacio` + pan, rectángulo simple, aviso de altura.
- `src/components/InlineEdit.tsx`: `UrlEnSitio` con validación y error en la tarjeta.
- `src/board/tools/link.tsx`: URL editable y apertura separada.
- `src/board/plantillas.ts`: creador puro, normalizador, lectura/borrado del formato antiguo.
- `src/board/projectModel.ts` y `projectStorage.ts`: `plantillas` dentro del proyecto, guardar/borrar/migrar/renombrar.
- `src/components/board.css`, `src/index.css`: URL, renombrado, atajos, cursores, cabecera que envuelve.
- Tests: `src/tests/plantillas.test.ts`, `src/tests/projectModel.test.ts`, `e2e-forja3/g7-detalles.spec.ts` (6).

## 3. Verificación

| Comprobación | Resultado |
|---|---|
| `npx tsc -b` | limpio |
| `npx vitest run` | 34 archivos, 195 tests |
| `npx oxlint` | 0 errores; sin warnings nuevos |
| `npx vite build` | correcto |
| `npx playwright test -c playwright.forja3.config.ts` | 29/29 (G0–G7) |
| `playwright.config.ts g6-pdf.spec.ts` | 3/3, sin regresión |

Tests E2E de G7:

1. Doble clic en el proyecto lo renombra y el nombre persiste tras recargar (comprobado también en IndexedDB).
2. Doble clic en la URL la cambia, rechaza `javascript:` con aviso y conserva la anterior; persiste tras recargar.
3. `?` y el botón abren el panel; `Esc` y «Entendido» lo cierran.
4. Arrastrar el fondo selecciona una tarjeta; `Espacio` + arrastrar mueve la cámara más de 100 px y conserva la selección.
5. Una plantilla sembrada en `localStorage` se migra al proyecto, la clave global desaparece, se guarda otra plantilla y ambas siguen tras recargar.
6. Captura del tablero con nota, enlace editable y marco.

Capturas: `g7-despues.png`, `g7-despues-atajos.png`.

## 4. Límites

- El renombrado de proyecto se dispara con doble clic sobre el `<select>`; en algunos navegadores el primer clic puede abrir además el desplegable nativo. El campo aparece igualmente y el nombre se guarda.
- La migración de plantillas va al **proyecto activo** en el momento de abrir el tablero. Si había plantillas globales de varios proyectos, no se puede saber a cuál pertenecían; se documenta en el aviso.
- Las plantillas se guardan dentro del registro del proyecto, no como archivos sueltos; un proyecto muy grande puede acercarse al límite local de IndexedDB.
- La selección con rectángulo no usa umbral de dirección: cualquier arrastre de fondo mayor a 5 px selecciona. Un clic sin movimiento sigue deseleccionando.
- La cabecera envuelve a dos filas por debajo de 1380 px; no se rediseñó en un menú compacto para no esconder acciones que ya existían.

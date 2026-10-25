# Forja 3 · G3 · Paridad Milanote

| Campo | |
|---|---|
| Fecha | 2026-10-25 |
| Rama | `studio/collage` |
| Alcance | Las 10 funciones de `G0-milanote.md` §3 |
| Captura | `REPORTES/capturas-forja3/g3-despues.png` |
| Evidencia | **E1** en todo lo ejecutado; **SPEC** solo donde se cita el contrato de `G0`. |

## 1. Las 10, una por una

| # | Función | Cómo quedó | Dónde |
|---:|---|---|---|
| 1 | Conectores que siguen a las tarjetas | Tirador en el borde derecho de cada tarjeta; se arrastra hasta otra tarjeta. Ancla en el lado que mira al otro (no centro→centro), curva Bézier y etiqueta con doble clic sobre la curva. Al mover una tarjeta, la curva se recalcula en el mismo render. | `board/conectores.ts`, `BoardWorkspace.tsx`, `BoardCardItem.tsx` |
| 2 | Selección múltiple con rectángulo | `⇧` + arrastrar el fondo dibuja el rectángulo y suma las tarjetas cuyo centro cae dentro. Se conserva el arrastre del fondo para pan (G1). No selecciona hijos ocultos de columnas. | `BoardWorkspace.tsx` |
| 3 | Alt/Opción + arrastrar duplica | La copia nace en el primer movimiento, no en el clic. Remapea ids, hijos de marco/columna y relaciones internas. El original se queda. | `model.duplicateCards`, `moveCardDrag` |
| 4 | Columnas contenedoras | Herramienta `columna`: recibe tarjetas al soltarlas encima, las ordena por altura y se pliega. Las tarjetas siguen viviendo en el tablero por id. | `board/columnas.ts`, `BoardColumn.tsx`, `tools/columna.tsx` |
| 5 | Listas de tareas | Herramienta `tareas`: casilla, texto editable, Enter crea otra, Tab/⇧Tab da sangría y borrar quita la fila. Exporta a Markdown con `- [ ]`. | `board/tareas.ts`, `tools/tareas.tsx` |
| 6 | Pegar URL con vista previa | El pegado de una URL crea tarjeta de enlace y pide los metadatos al backend local. Nuevo `GET /api/url-preview`: solo `og:title`/`og:description`/`og:image`, `<title>` y `<meta description>`; timeout de 6 s, 512 KB máximo, solo http/https, bloqueo de hosts privados/localhost y comprobación también tras redirección. Sin claves en el frontend. | `studio/backend/app.py`, `api/client.ts`, `board/vistaPrevia.ts`, `tools/link.tsx` |
| 7 | Notas con formato mínimo | Título, negrita, cursiva, lista, cita y código en línea/bloque, con barra de formato y `⌘/Ctrl + Enter` para guardar. El texto sigue guardándose como Markdown plano. | `components/MarkdownLite.tsx`, `tools/note.tsx` |
| 8 | Tablero dentro de tablero | Herramienta `tablero`: guarda solo el id del tablero destino, muestra su título y lo abre con botón o doble clic (cambia de tablero y de proyecto si hace falta). | `tools/tablero.tsx`, `BoardWorkspace.tsx` |
| 9 | Bloquear tarjeta | `locked` en el modelo. Bloqueada no se mueve, no entra en arrastre múltiple, no se borra y el botón de borrar queda deshabilitado. Se desbloquea desde el candado. También aplica a imagen/vídeo libres y columnas. | `model.ts`, `BoardCardItem.tsx`, `BoardFreeMedia.tsx` |
| 10 | Plantillas de tablero | Cuatro plantillas incluidas (En blanco, Moodboard, Proyecto, Estudio) y guardado del tablero actual como plantilla local. Al aplicar, todos los ids se remapean. | `board/plantillas.ts`, diálogo en `BoardWorkspace.tsx` |

## 2. Deuda de la fase

- **Rectángulo:** exige `⇧` porque el arrastre simple del fondo sigue siendo pan desde G1. Si Bruno quiere rectángulo con arrastre simple, hay que mover el pan a Espacio+arrastrar (fila 15 de G0, G7).
- **URL preview:** el bloqueo SSRF resuelve el host y vuelve a comprobar la URL final, pero no fija la IP durante la conexión. Un DNS rebinding muy rápido podría colarse; para el uso local se declara **H1** y queda como límite, no como garantía SPEC.
- **Columnas:** no se redimensionan a mano ni aceptan orden manual distinto del eje Y; el orden es por altura, como en la ayuda pública.
- **Conectores:** la etiqueta se edita con doble clic, no hay selector de color/grosor en la interfaz (el modelo ya guarda `tone`).
- **Plantillas:** las guardadas viven en `localStorage`; no viajan con el proyecto ni se exportan.
- **Medios:** sigue el límite de 12 MB por data URL de G2.

## 3. Comprobaciones

Ejecutadas dentro de `studio/frontend`:

| Comprobación | Resultado |
|---|---|
| `npx tsc -b` | limpio |
| `npx vitest run` | 30 archivos, 176 tests |
| `npx oxlint` | 0 errores; warnings preexistentes y de pureza/refs declarados |
| `npx vite build` | correcto |
| `npx playwright test -c playwright.forja3.config.ts` | 16 tests, 16 pasan (G0, G1, G2 y los 10 de G3) |

`studio/backend/app.py` compila con `python3 -m py_compile`. El endpoint se probó directamente con el Python empaquetado:

- `http://127.0.0.1:…` → `URL_NOT_PUBLIC`.
- `ftp://…` → `URL_INVALID`.
- `https://example.com/a?b=1#x` → normaliza a `https://example.com/a?b=1`.
- `https://example.com/` → devuelve `titulo: "Example Domain"` (**E1**, red real).

## 4. Captura

`REPORTES/capturas-forja3/g3-despues.png` muestra en un solo tablero: nota con formato, conector con etiqueta, enlace con vista previa, lista de tareas, columna con tarjeta dentro, tarjeta bloqueada y tablero anidado.

# Forja 3 · G0 · Inventario Milanote

| Campo | |
|---|---|
| Fecha | 2026-10-25 |
| Fuente | Centro de ayuda público de Milanote (`help.milanote.com`) y comportamiento visible del producto. |
| Límite | **Sin ingeniería inversa** de la app, sin copiar assets ni código. Solo páginas públicas de ayuda. |
| Evidencia | **E4** para lo que dice la ayuda; **E1** para lo que ya hace Prometeo (código leído); **H1** donde la ayuda no detalla el gesto. |
| Basura que se arregla | Imagen/video metido en una nota; trackpad que deja de responder; falta de vida; paridad Milanote. |

## 1. Cómo se leyó

Artículos usados (todos públicos):

- [Images](https://help.milanote.com/en/articles/359381-images) · arrastrar desde el Finder, biblioteca, Cmd+V implícito en pegar, caption, redimensionar, bloquear.
- [Videos](https://help.milanote.com/en/articles/10478926-videos) · subir, embeber, autoplay/loop, miniatura.
- [Links](https://help.milanote.com/en/articles/1722065-links) · tarjeta con imagen de vista previa, URL y descripción.
- [Lines](https://help.milanote.com/en/articles/111391-lines) · conector desde el tirador de la tarjeta, curvas, etiqueta, color/grosor.
- [Columns](https://help.milanote.com/en/articles/10478526-columns) · columna como contenedor ordenado, plegable, redimensionable.
- [To-Do Lists](https://help.milanote.com/en/articles/10486983-to-do-lists) · tareas, fechas, indentado con Tab.
- [Nesting boards](https://help.milanote.com/en/articles/9860073-nesting-boards) · tablero dentro de tablero y migas.
- [Text Formatting](https://help.milanote.com/en/articles/4675110-text-formatting) · estilos, listas, código, cita, color de texto.
- [Duplicating content](https://help.milanote.com/en/articles/111397-duplicating-content) · Alt/Opción + arrastrar.
- [Locking an item](https://help.milanote.com/en/articles/4357447-locking-an-item-to-your-board) · bloquear posición y borrado.
- [Keyboard shortcuts](https://help.milanote.com/en/articles/111393-keyboard-shortcuts) · menú `/`, doble clic para nota, Espacio+arrastrar, ⌘F, ⌘Enter.
- [Search](https://help.milanote.com/en/articles/1116205-search) · busca en todos los tableros, orden por visto/modificado.
- [Comments](https://help.milanote.com/en/articles/10684379-comments) · tarjeta de comentario, hilo, mención, reacción.
- [Custom templates](https://help.milanote.com/en/articles/1945249-custom-templates) · convertir tablero en plantilla y usarlo como copia.
- [What kind of files](https://help.milanote.com/en/articles/1159010-what-kind-of-files-can-i-upload) · lista de formatos y límites.

La selección con rectángulo y el pegado con Cmd+V no tienen artículo propio; se documentan por el comportamiento estándar del producto (**H1**), no por ingeniería inversa.

## 2. Tabla de paridad

Orden = cola de trabajo. «Prometeo» se comprobó en el código de `studio/frontend/src/`, no de memoria.

| # | Función de Milanote | ¿Prometeo la tiene? | Evidencia en Prometeo | Prioridad |
|---:|---|---|---|---|
| 1 | Imágenes y videos libres, sin marco de nota | **A medias** | `board/tools/media.tsx` pinta todo dentro de `.board-card`: cabecera de título, borde, fila de colores, video con `controls` y ancho fijo de 290 px (`createCard`). | **G2** |
| 2 | Arrastrar archivos desde el Finder | **No** | El `onDrop` del lienzo solo acepta `application/x-prometeo-tool` (`BoardWorkspace.tsx:639`); los archivos entran por `<input type="file">`. | **G2** |
| 3 | Flechas/conectores entre tarjetas, que siguen al mover | **A medias** | Hay relaciones y `<line>` con marcador (`BoardWorkspace.tsx:1944`), pero solo centro→centro; no hay tirador en la tarjeta, ancla, curva ni etiqueta. | **G3** |
| 4 | Selección múltiple con rectángulo | **No** | Solo selección con clic, ⇧ y ⌘/Ctrl (`BoardWorkspace.tsx:1143`). El arrastre sobre el fondo hace pan. | **G3** |
| 5 | Duplicar con Alt/Opción + arrastrar | **No** | `startCardDrag` trata Alt como ningún modificador; no hay copia. | **G3** |
| 6 | Columnas contenedoras, ordenadas y plegables | **No** | No existe herramienta `columna` en el registro (`board/tools/registry.ts`). | **G3** |
| 7 | Listas de tareas con casilla | **No** | No hay herramienta `tarea`; el cuerpo de nota es texto plano. | **G3** |
| 8 | Pegar URL y ver vista previa (imagen/título/descripción) | **A medias** | El pegado solo añade una URL de imagen a un Referente (`BoardWorkspace.tsx:1676`). No crea tarjeta de enlace con metadatos ni vista previa. | **G3** |
| 9 | Notas con formato (títulos, negrita, listas, código, cita) | **No** | `CuerpoTexto` usa `TextoEnSitio`; guarda y muestra texto plano. | **G3** |
| 10 | Tablero dentro de tablero como tarjeta | **No** | Hay varios tableros por proyecto, pero no un tablero anidado como objeto del lienzo. | **G3** |
| 11 | Bloquear tarjeta (posición y borrado) | **No** | No hay campo de bloqueo ni acción en el modelo (`board/model.ts`). | **G3** |
| 12 | Plantillas de tablero | **No** | No hay plantillas; crear tablero siempre da uno vacío. | **G3** |
| 13 | Comentarios | **No** | No hay herramienta de comentario ni hilos. | G4+ / fuera de las 10 |
| 14 | Búsqueda en todos los tableros, con resultados | **A medias** | La barra filtra y atenúa tarjetas del tablero activo (`BoardWorkspace.tsx:1765`); no busca en otros tableros ni muestra lista de resultados. | G7+ |
| 15 | Atajos de teclado completos y panel `/` | **A medias** | Existen ⌘Z/⇧⌘Z y `N`; no hay Espacio+arrastrar, ⌘F, ⌘Enter ni panel de atajos. | **G7** |
| 16 | Colores de tarjeta | **Sí** | Cuatro muestras persistidas en `BoardCard.color` (`BoardCardItem.tsx:88`). | — |
| 17 | Buscar/ordenar (visto/modificado) | **No** | No hay orden ni historial de vistos. | G7+ |
| 18 | Etiquetas de color y filtros | **No** | Existe una herramienta «Etiqueta» propia, pero no el sistema de labels de Milanote. | G7+ |

## 3. Las 10 de G3

G2 ya cierra las filas 1 y 2 (medios libres y drop del Finder) y la parte de imagen de Cmd+V. Por eso la cola de G3 son las **10 primeras faltantes después de G2**:

1. Conectores que siguen a las tarjetas (tirador, ancla y actualización al mover).
2. Selección múltiple con rectángulo.
3. Alt/Opción + arrastrar duplica.
4. Columnas contenedoras.
5. Listas de tareas.
6. Pegar URL con vista previa por el backend local, sin claves en el frontend.
7. Notas con formato mínimo (título, negrita, lista, código, cita).
8. Tablero dentro de tablero como tarjeta.
9. Bloquear tarjeta.
10. Plantillas de tablero.

Las filas 13–18 quedan fuera de estas 10 y se declaran deuda en `FORJA3.md` si no se alcanzan.

## 4. Lo que Bruno pidió y a qué fila va

| Lo que dijo Bruno | Fila | Fase |
|---|---|---|
| «Al tablero le faltan cosas de Milanote» | 3–12 | G3 |
| «El trackpad no está bien acoplado y a veces deja de reaccionar» | no es una fila de Milanote: es gesto y captura de puntero | G1 |
| «No tiene vida» | no es una fila: es física de hover, arrastre, inercia, imán | G1 |
| «Un video sale metido pequeño en una nota» | 1 | G2 |
| «Que todo se inspire en sus videos, no solo arreglar» | tono Irene Guerra + vida | G1, G4 |

## 5. Límites de este inventario

- No se abrió la app de Milanote ni se inspeccionó su DOM, su red o su código. La columna «Milanote» es la ayuda pública + lo que Bruno describe al usarlo.
- La ayuda no publica medidas de columnas, radios ni sombras; el tono visual se toma de `docs/STUDIO/DESIGN.md`, no de Milanote.
- «A medias» siempre significa que existe una pieza de Prometeo que se parece, pero no cumple el gesto completo. No se ha contado como «sí» ninguna función que solo se parezca en el nombre.

## 6. Verificación de fase

G0 no toca código. Captura de referencia: `REPORTES/capturas-forja3/g0-antes.png` (tablero tal como está al empezar Forja 3). Las cuatro comprobaciones se ejecutan igualmente antes de cerrar la fase para no arrastrar un rojo previo.

| Comprobación | Resultado |
|---|---|
| `npx tsc -b` | limpio |
| `npx vitest run` | 28 archivos, 158 tests |
| `npx oxlint` | 0 errores (warnings preexistentes) |
| `npx vite build` | correcto |
| Playwright | `g0-inventario.spec.ts`, 1 test, pasa |

# A-1 · Auditoría de oficio de Prometeo Studio

Fecha: 25-oct-2026 · Rama: `studio/collage` · Sin push.
Alcance: tablero, tarjetas, PDF, biblioteca/proyectos, historial, teclado/accesibilidad y gestos.
Método: lectura del código + app corriendo (vite + motor PDF local) + 14 pruebas Playwright temporales (15 observaciones).
No se modificó código de la app. El único cambio de producto es este informe y la skill `prometeo-auditor`.

> `prometeo-lienzo-saber` no existe todavía en `.agents/skills/`. Se leyó `prometeo-lienzo` y los principios de este informe se proponen para la skill que nazca con ese nombre.

---

## 0. Veredicto en una frase

Prometeo tiene una base poco común —modelo único, autoguardado real, borrado con deshacer, PDF que nunca toca el original y un trackpad 1:1—, pero todavía no tiene el **oficio mínimo de una herramienta de lienzo**: seleccionar mal, no poder sacar una tarjeta de un marco, no poder redimensionar una nota, no tener árbol de objetos, no poder borrar un proyecto, no poder paneo en iPad y no poder editar tipografía en PDF no son «detalles»: son las cosas que cualquier persona da por hechas antes de confiar su trabajo.

La auditoría deja **15 huecos en el Top 15**: 5 rompen, 8 frustran y 2 pulen. Ninguno exige reescribir la app; casi todos son contratos de interacción que faltan.

---

## 1. Qué se miró y qué se probó

### Código
- `studio/frontend/src/board/` (modelo, cámara, geometría, marcos, columnas, historial, guardado, portapapeles, atajos).
- `studio/frontend/src/components/BoardWorkspace.tsx` (3.599 líneas), `BoardCardItem`, `BoardColumn`, `BoardFreeMedia`, `InlineEdit`, `Viewport`, `Inspector`, `Toolbar`, `SearchModal`, `Outliner`.
- `studio/backend/` y `studio/frontend/src/hooks/useTransaction.ts` para el contrato PDF.
- `studio/frontend/src/components/board.css`, `index.css` y `styles/tokens.css` para foco, contraste y tamaño de objetivos.
- Reportes previos T-1 (trackpad) y T-2 (selección/borrado) como línea base.

### App corriendo
Motor PDF local (`studio-desktop/resources/runtime/bin/python3`), vite en `127.0.0.1:5173`, Brave con Playwright. Las pruebas sembraron IndexedDB para que cada caso fuese determinista.

| Prueba temporal | Resultado observado |
|---|---|
| Marquesina sin ⇧ sobre una tarjeta con otra ya seleccionada | **2 seleccionadas**: suma, no reemplaza |
| ⇧ + clic sobre una tarjeta ya seleccionada | **1 seleccionada**: no la quita |
| Arrastrar un hijo de un marco al vacío | El marco conserva `hijos: ["n1"]` |
| Enter sobre un marco y una columna enfocados | **No seleccionan** (`false` / `false`) |
| Tirador del marco con ArrowRight | Ancho **420 px → 420 px** |
| Copiar tarjeta y leer el portapapeles del sistema | Solo `prometeo-studio/tarjetas:<uuid>` |
| Pegar texto plano en el lienzo | **Sigue habiendo 1 tarjeta** |
| Buscar «alfa» en el tablero | 1 atenuada, **0 resultados navegables** |
| Abrir el diálogo de atajos | Foco **fuera** del diálogo y sigue fuera tras Tab |
| Seleccionar todo | `aria-selected` **null**; contador sin `aria-live` |
| Crear nota, esperar «Guardado» y recargar | 2 tarjetas persisten; **Deshacer deshabilitado** |
| Borrar tablero y esperar 5,6 s | El id desaparece; **0 controles de papelera** |
| Tab dentro del texto de una tarea | El foco **sigue dentro** del campo |
| PDF `case_a`: imagen, overlays y controles | `user-select: none`; overlays sin texto; **sin controles de fuente/tamaño/color ni añadir texto/imagen** |
| Zoom del lienzo: 30 clics en Acercar; luego `⌘0` y `⌘-` | **240 %**; los atajos no hacen nada |

Limitaciones declaradas: no se probó hardware iPad real ni VoiceOver; las conclusiones táctiles salen del código de punteros y de la semántica de `pointerdown`. El contraste se calculó con la fórmula WCAG sobre los tokens, no con un medidor de pantalla.

---

## 2. Referentes: qué da por hecho el oficio

Solo comportamiento visible y listas oficiales de atajos. No se descompiló ni se rasó ningún producto.

| Herramienta | Gesto de oficio que se da por hecho | Prometeo hoy |
|---|---|---|
| **Figma** | Redimensionar cualquier capa o selección; agrupar/desagrupar (`⌘G` / `⌘⇧G`); panel de capas; alinear/distribuir; zoom hasta miles por ciento; menú contextual; `⇧1` ajustar, `⇧0` 100 % | Notas/columnas no se redimensionan; no hay grupo/desagrupar; no hay panel de capas; zoom máximo 240 %; sin menú contextual |
| **Canva** | Asas en todos los objetos; agrupar; capas; autoguardado; plantillas; uso táctil en iPad | Plantillas y autoguardado sí; asas solo en medios y marco; táctil incompleto |
| **Illustrator** | Herramientas con tecla (`V`, `A`…); grupos; capas; mesas de trabajo; alinear; `⌘0` ajustar, `⌘1` 100 % | No hay teclas de herramienta; no hay grupos; los marcos no son mesas de trabajo; zoom sin atajos |
| **InDesign** | Marcos de texto, estilos de carácter/párrafo, páginas, vínculos, exportación | El PDF no tiene estilos, ni fuentes editables, ni páginas que se reordenen |
| **Acrobat** | Seleccionar y copiar texto; editar texto e imagen; añadir texto/imagen; organizar páginas; exportar | Solo sustitución de texto por nodo, con verificación; nada de lo demás |
| **Fusion 360** | Árbol de componentes, restricciones, deshacer, navegación de vista | Lienzo libre sin árbol ni restricciones; el deshacer es por tablero y en memoria |
| **Keynote / Freeform** | Lienzo infinito, redimensionar/rotar, alinear, capas, gestos de iPad | Lienzo infinito sí; rotar no; gestos de iPad incompletos |
| **Milanote** | Tableros, arrastrar tarjetas, columnas, buscar, papelera, móvil | Columnas sí; búsqueda solo atenúa; no hay papelera; móvil sin paneo |
| **Are.na** | Canales/bloques, conectar, buscar, archivo | Referentes y conectores sí; no hay búsqueda global de biblioteca |
| **Procreate** | Capas; deshacer con dos dedos, rehacer con tres; transformar; selección | Sin gestos de deshacer/rehacer; sin panel de capas |

Conclusión de la comparación: Prometeo compite en **atmósfera** (papel, collage, archivo, entropía) pero no todavía en **gramática de manipulación**. Las herramientas de oficio coinciden en cinco contratos: seleccionar, agrupar, redimensionar, deshacer y encontrar. Prometeo falla total o parcialmente en los cinco.

---

## 3. Inventario de oficio por zona

Leyenda: ✅ existe · ◐ a medias · ✗ no existe.

### 3.1 Tablero / lienzo

| Oficio que se da por hecho | Estado | Evidencia |
|---|---|---|
| Clic selecciona | ✅ | `BoardCardItem.tsx:104-106`, `BoardWorkspace.tsx:1819-1831` |
| ⇧ + clic añade **y quita** de la selección | ◐ | `BoardWorkspace.tsx:1294-1296, 1827-1828`: solo añade; la ayuda promete «añadir o quitar» (`atajos.ts:145`) |
| Marquesina reemplaza; ⇧ + marquesina añade | ✗ | `BoardWorkspace.tsx:1120-1141` siempre hace `[...current, ...dentro]`; `1244-1260` no consulta ⇧ |
| `⌘/Ctrl + A` selecciona lo visible | ✅ | `atajos.ts:132`, `seleccion.ts:10-12` |
| `Supr` borra al instante y `⌘Z` devuelve | ✅ | `BoardWorkspace.tsx:2560-2586`, `atajos.ts:137`; T-2 |
| Arrastrar una o varias tarjetas | ✅ | `BoardWorkspace.tsx:1278-1462` |
| Mover con flechas 1/10 px y una ráfaga = un deshacer | ✅ | `atajos.ts:145-152`, `seleccion.ts:139-144` |
| Redimensionar cualquier tarjeta | ✗ | No hay asas en `BoardCardItem`; el ancho de papel se acota a 440 al cargar (`model.ts:192-194`) |
| Redimensionar imagen/vídeo desde 4 esquinas, ⇧ proporción | ✅ | `BoardWorkspace.tsx:1603-1661`, `BoardFreeMedia.tsx:186-198` |
| Redimensionar marco desde cualquier borde y con teclado | ◐ | Solo esquina SE (`BoardWorkspace.tsx:1521-1601, 3338-3341`); el tirador es un `button` sin `onClick` ni teclas |
| Agrupar una selección en un marco | ◐ | Se puede dibujar un marco alrededor y adopta por geometría (`createFrameFromRect`, `BoardWorkspace.tsx:982-1013`); no hay `⌘G` ni acción «Agrupar» desde la selección, y no hay desagrupar |
| Desagrupar / sacar una tarjeta de un marco | ✗ | `endCardDrag` solo limpia y adopta si hay marco destino (`BoardWorkspace.tsx:1464-1494`); al vacío no desvincula. Confirmado en la app |
| Mover el marco mueve a sus hijos | ✅ | `frames.ts:116-123`, `seleccion.ts:16-40` |
| Alinear y distribuir | ✅ | `geometry.ts:20-104`, barra en `BoardWorkspace.tsx:3445-3455` |
| Alinear contra el marco o el lienzo | ✗ | `alignCards` usa solo los límites de la selección (`geometry.ts:25-36`) |
| Capas / orden de pintado | ◐ | Atajos `[` `]` y `⌘[` `⌘]` (`atajos.ts:156-159`), pero no hay panel de capas ni orden visible |
| Bloquear tarjeta, columna y medio | ◐ | Tarjeta `BoardCardItem.tsx:114-120`; columna `BoardColumn.tsx:79-86`; medio `BoardFreeMedia.tsx:160-170`; **el marco no tiene candado** |
| Zoom y paneo | ◐ | Rueda/pellizco/espacio (`BoardWorkspace.tsx:1006-1080`, T-1); zoom 25–240 % (`camera.ts:20-22`), sin atajos |
| Guías y magnetismo | ◐ | `imanDeCaja` alinea con tarjetas y rejilla (`iman.ts:14-107`); el botón Magnet solo activa el snap duro (`BoardWorkspace.tsx:1378, 3045`), las guías están siempre |
| Menú contextual (clic derecho / pulsación larga) | ✗ | En escritorio se desactiva el menú del WebView (`App.tsx:210-216`); no hay menú propio |
| Panel de objetos / capas / outliner del tablero | ✗ | El único árbol es el `Outliner` del PDF; el tablero solo pinta tarjetas |
| Rotar una tarjeta o un medio | ✗ | No hay campo de rotación en `BoardCard` (`model.ts:13-27`); la inclinación es solo un efecto de arrastre |

### 3.2 Tarjetas

| Oficio que se da por hecho | Estado | Evidencia |
|---|---|---|
| Crear nota, enlace, imagen, tareas, columna, marco con la barra o `N` | ✅ | `BoardWorkspace.tsx:3137-3160`, `atajos.ts:188` |
| Arrastrar una herramienta al lienzo | ✅ | `BoardWorkspace.tsx:936-970` |
| Editar título y cuerpo en el sitio | ✅ | `InlineEdit.tsx:13-110` |
| Nota con formato (título, negrita, cursiva, lista, cita, código) | ✅ | `note.tsx:5-120` |
| Tipografía de tarjeta (fuente, tamaño, color, alineación) | ✗ | No hay controles; solo 6 marcas Markdown y 4 colores de papel (`BoardCardItem.tsx:132-137`) |
| Editar título/cuerpo de una imagen o vídeo | ✗ | `BoardFreeMedia` pinta la leyenda pero no la edita (`BoardFreeMedia.tsx:158-161`) |
| Redimensionar nota/columna | ✗ | Sin asas; el ancho se acota al cargar (`model.ts:192-194`) |
| Recortar, rotar, reemplazar o poner alt a una imagen | ✗ | `BoardMedia` no tiene esos campos (`model.ts:8-12`); no hay UI |
| Soltar archivos | ✅ | `dropTool`, `BoardWorkspace.tsx:946-955`; tope 12 MB (`model.ts:57`) |
| Pegar imagen del sistema | ✅ | `handlePaste`, `BoardWorkspace.tsx:2833-2858` |
| Pegar texto plano como nota | ✗ | `handlePaste` solo atiende imagen, URL segura o marca interna (`BoardWorkspace.tsx:2833-2891`); probado |
| Copiar tarjetas de forma interoperable | ◐ | El portapapeles del sistema solo lleva una marca (`portapapeles.ts:60-75`); el contenido vive en memoria |
| Pegar junto al cursor, no en el centro | ✗ | La imagen pegada cae en el centro del viewport (`BoardWorkspace.tsx:2845-2849`) |
| Enlace con URL editable y vista previa | ✅ | `link.tsx`, `InlineEdit.tsx:170-263` |
| Columna: soltar dentro, plegar, contar | ✅ | `endCardDrag` (`BoardWorkspace.tsx:1470-1494`), `BoardColumn.tsx:51-103` |
| Columna: reordenar sus hijos | ✗ | Los hijos se ordenan por `y` y se pintan como lista no arrastrable (`BoardColumn.tsx:48-50, 100-112`) |
| Tareas: añadir, marcar, sangrar, borrar | ✅ | `tareas.tsx:18-76` |
| Tareas: teclado predecible | ✗ | `Tab` cambia la sangría y no sale del campo (`tareas.tsx:45-48`); probado |
| Marco: vistas Libre/Archivo/Muro/Mesa y publicar | ✅ | `BoardWorkspace.tsx:3288-3330` |
| Marco: candado | ✗ | No hay botón de bloqueo en la cabecera del marco (`BoardWorkspace.tsx:3284-3310`) |
| Tablero anidado | ✅ | `tablero.tsx`, `BoardWorkspace.tsx:2061-2072` |
| Estado vacío con una acción clara | ✅ | `BoardWorkspace.tsx:3409-3414` |
| Soltar un archivo dentro de un marco y que se vuelva hijo | ✗ | `addMedia` no consulta marcos; `addToolCard` coloca por coordenadas (`BoardWorkspace.tsx:2244-2275`) |

### 3.3 Documentos / editor PDF

| Oficio que se da por hecho | Estado | Evidencia |
|---|---|---|
| Abrir PDF por selector y ejemplos | ✅ | `Toolbar.tsx:100-120`, `App.tsx:317-330` |
| Abrir PDF arrastrándolo a la ventana | ✗ | No hay `onDrop` en `App.tsx` ni en `Welcome` |
| Pasar páginas y buscar (`⌘F`) | ✅ | `Viewport.tsx:155-180`, `SearchModal.tsx` |
| Seleccionar texto con el ratón y copiarlo | ✗ | La página es una imagen; los overlays son `div` de clic (`Viewport.tsx:97-116`) y la imagen tiene `user-select: none` (`index.css:661`) |
| Editar una palabra o un span | ◐ | Sustitución de texto por nodo, con vista previa y verificación (`Inspector.tsx:152-208`); el nodo es un span del DocGraph |
| Cambiar fuente, tamaño o color | ✗ | Fuente y tamaño son lectura (`Inspector.tsx:140-145`); no hay controles |
| Añadir texto o imagen | ✗ | La barra solo tiene vista, marcos, OCR y zoom (`Viewport.tsx:184-228`) |
| Organizar páginas (rotar, reordenar, borrar, extraer) | ✗ | No hay acciones de página |
| Exportar | ◐ | Solo la copia verificada (`App.tsx:168-190`); no hay opciones de exportación ni otros formatos |
| Zoom y lectura | ◐ | 50–250 % (`Viewport.tsx:35`), una página a la vez, sin scroll continuo ni atajos |
| Deshacer/rehacer en la edición | ◐ | Se pueden quitar operaciones preparadas (`TransactionTray`), pero no hay deshacer/rehacer del staging |
| Original inmutable y copia verificada | ✅ | Motor PDF, SHA-256 y `verify_and_export`; el punto más fuerte del producto |
| OCR con seguridad explícita y vista previa | ✅ | `Inspector.tsx:220-330`, backend raster |
| Accesibilidad de los overlays | ✗ | El contenedor es `aria-hidden="true"` y los nodos solo responden a clic (`Viewport.tsx:97-116`); el `Outliner` es la alternativa |
| Documento pesado | ◐ | Render por página y avisos de páginas grandes (`session.py:52-68`); no hay modo lectura continua |

### 3.4 Biblioteca y proyectos

| Oficio que se da por hecho | Estado | Evidencia |
|---|---|---|
| Crear proyecto | ✅ | `BoardWorkspace.tsx:1948-1975` |
| Cambiar de proyecto | ✅ | `BoardWorkspace.tsx:1929-1946` |
| Renombrar proyecto | ◐ | Solo doble clic sobre el `<select>` (`BoardWorkspace.tsx:2977-2983`); no hay botón, ni `F2`, ni ruta de teclado |
| Borrar proyecto | ✗ | No existe `deleteProject` en `projectStorage.ts` (exports 263-546) ni control en la barra (`BoardWorkspace.tsx:3023-3028`) |
| Crear tablero | ✅ | `BoardWorkspace.tsx:3025` |
| Renombrar tablero | ◐ | `window.prompt` (`BoardWorkspace.tsx:3023`), en tensión con T-2 y con el escritorio sin menú contextual |
| Borrar tablero | ◐ | Inmediato + aviso de 5 s (`BoardWorkspace.tsx:2144-2195`, `1738-1745`); después no hay papelera |
| Mover un tablero a otro proyecto | ✗ | `assignBoardToProject` solo se llama al crear/importar/restaurar (`BoardWorkspace.tsx:1921, 1960, 2086, 2290, 2315`) |
| Duplicar tablero | ✗ | Solo exportar/importar JSON o Markdown |
| Buscar en el tablero | ◐ | Atenúa las no coincidencias (`BoardWorkspace.tsx:2922-2925`); no hay lista, contador ni salto |
| Buscar en todos los tableros/proyectos/biblioteca | ✗ | No hay índice global; la búsqueda PDF es otra cosa (`SearchModal.tsx`) |
| Ordenar tarjetas, tableros o referentes | ✗ | No hay control de orden; el historial de un referente se ordena internamente (`referente.tsx:50-54`) |
| Importar la biblioteca de referentes | ✅ | `importReferentes`, `BoardWorkspace.tsx:2303-2325`; crea/actualiza «Biblioteca» sin duplicados |
| Explorar/filtrar la biblioteca como colección | ◐ | Solo hay filtros dentro de un referente (`referente.tsx:50-54`); no hay vista de biblioteca |
| Papelera | ✗ | No aparece en el código ni en la barra; el borrado de tablero/referencia es definitivo a los 5 s |
| Estados vacíos y errores de almacenamiento | ✅ | `board-alert`, exportación de rescate (`BoardWorkspace.tsx:3093-3100`) |
| Mover tarjetas entre tableros | ◐ | Copiar/pegar interno puede cruzar tableros, pero no hay «Mover a…» ni selección de destino |

### 3.5 Historial y seguridad

| Oficio que se da por hecho | Estado | Evidencia |
|---|---|---|
| Deshacer/rehacer por tablero | ✅ | `BoardWorkspace.tsx:1751-1775`; `history.ts:15-69`; 100 pasos |
| Un gesto = un paso de deshacer | ✅ | T-2; coalescencia de flechas (`seleccion.ts:139-144`) |
| Deshacer sobrevive a recargar o cerrar | ✗ | El historial vive en `useState`; probado: tras recargar, Deshacer está deshabilitado |
| Deshacer en PDF | ◐ | Quitar una operación preparada sí; no hay pila de deshacer/rehacer del staging |
| Deshacer en proyectos/biblioteca | ✗ | Crear/renombrar proyecto, borrar plantilla o importar gustos no tienen undo |
| Autoguardado del tablero | ✅ | Cola serial con debounce de 400 ms (`saveQueue.ts:12, 93-121`); probado con recarga |
| Estado «Guardado» solo cuando el almacén confirma | ✅ | `saveQueue.ts:69-90`, `BoardWorkspace.tsx:3029-3031` |
| Error de guardado conserva la copia y ofrece rescate | ✅ | `saveQueue.ts:45-67`, `BoardWorkspace.tsx:3093-3100` |
| Cerrar pestaña con cambios pendientes | ◐ | `beforeunload` avisa (`useUnsavedGuard.ts:57-64`), pero no fuerza `flushBoardWrites`; el host nativo sí ofrece guardar |
| Restaurar sesión PDF tras recargar | ✅ | `useDocumentSession` + aviso «Sesión recuperada» (`App.tsx:270-277`) |
| Borrado de tarjetas con red de seguridad | ✅ | 100 pasos de historial + aviso de 5 s |
| Borrado de tablero/referencia con red de seguridad | ◐ | Solo el aviso de 5 s; al expirar, no hay historial ni papelera. Probado |
| Trabajo en dos ventanas | ✗ | No hay sincronización entre pestañas; IndexedDB cierra la conexión en `versionchange` (`storage.ts:33`) |

### 3.6 Teclado y accesibilidad

| Oficio que se da por hecho | Estado | Evidencia |
|---|---|---|
| Tabla única de atajos y panel `?` | ✅ | `atajos.ts:130-192`; el panel se genera de la misma tabla (`BoardWorkspace.tsx:3474-3493`) |
| Atajos de edición completos | ◐ | Hay seleccionar, borrar, duplicar, copiar, cortar, pegar, mover, ordenar y deshacer; faltan grupo, herramientas, zoom, búsqueda y guardar |
| Foco visible | ✅ | `index.css:48-56`; estados de foco en tarjetas, marcos y columnas |
| Tarjetas seleccionables con Enter/Espacio | ✅ | `BoardCardItem.tsx:116-122` |
| Marcos y columnas seleccionables con teclado | ✗ | Tienen `tabIndex={0}` (`BoardWorkspace.tsx:3268`, `BoardColumn.tsx:57`) pero no `onKeyDown`; probado |
| Selección múltiple sin ratón | ◐ | `⌘A` sí; no hay ⇧+flechas ni alternativa al ⇧+clic |
| Redimensionar con teclado | ✗ | Asas solo de puntero; el `button` del marco no responde a teclas; probado |
| Diálogos con foco atrapado y restaurado | ✗ | No hay `inert`, `focus trap` ni restauración; el de atajos abre con el foco fuera y Tab sigue fuera. Probado |
| `Tab` nunca queda atrapado | ✗ | En tareas, `Tab` cambia la sangría y no sale (`tareas.tsx:45-48`); probado |
| Estado de selección anunciado | ✗ | Sin `aria-selected` ni contador en `aria-live`; probado |
| Orden de lectura del lienzo | ◐ | Es el orden del array, no el espacial; no hay vista de lista del tablero |
| Contraste AA | ◐ | La mayoría cumple; `--paper-muted-2` sobre papel da **3,65:1** a 12 px en Forja (`tokens.css:27`, `board.css:2791`) |
| Objetivos táctiles ≥ 24 px | ✗ | Muestras de color de 10×10 (`board.css:804-810`); controles de 20–22 px (`board.css:765-771`) |
| Movimiento reducido | ✅ | `index.css:984-991` y reglas del tablero |
| Nombres accesibles en controles | ✅ | `e2e/a11y.spec.ts`; la mayoría de botones tienen `aria-label` |
| Overlays PDF accesibles | ✗ | `aria-hidden="true"` + clic sin foco (`Viewport.tsx:97-116`); el `Outliner` compensa parcialmente |
| Anuncios de guardado/borrado | ✅ | `aria-live` en guardado y `role="status"` en avisos |

### 3.7 Gestos de trackpad e iPad

| Oficio que se da por hecho | Estado | Evidencia |
|---|---|---|
| Dos dedos panean 1:1, sin inercia añadida | ✅ | T-1; `handleWheel` (`BoardWorkspace.tsx:1006-1024`) |
| Pellizco acerca hacia el punto bajo el cursor | ✅ | `ctrl+wheel` y `gesturestart/change/end` (`BoardWorkspace.tsx:1015-1080`) |
| Un dedo en el fondo selecciona; dos dedos panean | ✗ | Un dedo en el fondo inicia marquesina (`BoardWorkspace.tsx:1244-1260`); no hay paneo táctil |
| Pinch táctil en tablets no-Safari | ◐ | Solo eventos `gesture*` de WebKit; no hay pinch por `pointer` |
| Pulsación larga / clic derecho con acciones | ✗ | Sin menú contextual propio; en escritorio se desactiva el del WebView (`App.tsx:210-216`) |
| Deshacer/rehacer con gestos | ✗ | No hay dos/tres dedos; solo teclado/botones |
| Arrastrar tarjetas con el dedo | ✅ | Eventos de puntero en tarjeta, marco, columna y medio |
| Controles visibles al tocar | ◐ | Aparecen con `.selected`/`:focus-within`; los objetivos siguen siendo pequeños |
| Archivos desde la app Archivos de iPad | ◐ | Depende del `drop` HTML; no hay ruta táctil explícita |

---

## 4. Escenarios: persona × momento × estado

La matriz completa se recorre por zonas; estas son las celdas que más revelan. Entre 3 y 5 por zona.

| Zona | Persona / momento / estado | Qué espera | Qué pasa de verdad |
|---|---|---|---|
| 1 · Lienzo | Bruno con prisa, primer minuto, tablero vacío | Crear una nota y escribir sin buscar nada | La barra y el estado vacío lo consiguen; `N` abre la biblioteca |
| 1 · Lienzo | Bruno con prisa, 500 tarjetas, después de borrar sin querer | Deshacer y seguir | `⌘Z` devuelve las 500; el aviso de 5 s también. Bien |
| 1 · Lienzo | Bruno con prisa, borra un tablero entero | Recuperarlo mañana | A los 5 s ya no hay nada: no hay papelera ni historial de tableros |
| 1 · Lienzo | Alguien nuevo, primer minuto | Que arrastrar el fondo mueva el lienzo o, al menos, que se vea el modo mano | Arrastrar el fondo dibuja una marquesina; el paneo solo se descubre con «Espacio + arrastra» o rueda |
| 1 · Lienzo | Experto en Figma, primer minuto | `⌘G`, `⇧1`, `+/-`, asas en todo, panel de capas | `⌘G` no agrupa; el zoom se queda en 240 %; las notas no tienen asas; no hay panel de capas |
| 2 · Tarjetas | Alguien nuevo, pega un texto copiado de otra app | Que nazca una nota con ese texto | No pasa nada: el pegado de texto plano se ignora |
| 2 · Tarjetas | Alguien con una imagen, quiere ponerle nombre y pie | Doble clic en la leyenda | La leyenda se pinta pero no se edita; no hay título, cuerpo, recorte ni alt |
| 2 · Tarjetas | Alguien suelta un archivo sobre un marco | Que el archivo entre en el marco | El archivo cae por coordenadas y no se vuelve hijo del marco |
| 3 · PDF | Usuario de Acrobat, primer minuto | Seleccionar una frase y copiarla | La página es una imagen: no hay selección de texto; los overlays son de clic |
| 3 · PDF | Usuario de Acrobat, quiere cambiar una fuente | Cambiar fuente, tamaño o color | Fuente y tamaño son solo lectura; no hay controles de color |
| 3 · PDF | Documento escaneado, quiere editar una palabra | Editar con seguridad o un «no» claro | OCR y verificación de fondo funcionan; si no es seguro, lo explica y no toca el original. Bien |
| 4 · Biblioteca | Biblioteca con 300 referentes | Buscar, ordenar, mover a un tablero | Solo se busca dentro del tablero activo y se atenúa; no hay orden ni vista de biblioteca |
| 4 · Biblioteca | Quiere mover un tablero a otro proyecto | Menú «Mover a…» | No existe; solo se asigna al crear o importar |
| 4 · Biblioteca | Quiere borrar un proyecto que ya no usa | Borrarlo con una red de seguridad | No hay borrar proyecto; renombrar exige doble clic en un `<select>` |
| 5 · Historial | Al volver al día siguiente | Encontrar el tablero, el estado y el historial | Tablero y estado sí; el historial de deshacer no |
| 5 · Historial | Edita y cierra la pestaña en el mismo segundo | Que el cambio esté al reabrir | El navegador avisa, pero no fuerza el volcado; el host nativo sí ofrece guardar |
| 5 · Historial | Borra 150 tarjetas de una en una | Poder volver atrás | El historial conserva 100 pasos; más allá, se pierde |
| 6 · Teclado | Solo teclado, tablero con marcos | Tabular hasta un marco, Enter para seleccionarlo, flechas para moverlo | Enter no lo selecciona; para mover hay que usar el ratón |
| 6 · Teclado | Solo teclado, lista de tareas | Tabular entre tareas | `Tab` cambia la sangría y atrapa el foco |
| 6 · Teclado | Solo teclado, diálogo de atajos | Foco dentro y Escape para volver al mismo sitio | El foco se queda detrás; Tab sigue detrás; Escape cierra |
| 7 · Gestos | iPad, tablero lleno | Pellizcar, panear, seleccionar, arrastrar | Arrastrar funciona; panear no; el pellizco depende de Safari; los controles son pequeños |
| 7 · Gestos | Mac con trackpad, tablero lleno | Que el lienzo siga al dedo y pare cuando paran los dedos | T-1: 1:1, sin inercia añadida; el pellizco va al punto bajo el cursor. Bien |
| 7 · Gestos | Clic derecho sobre una tarjeta | Duplicar, bloquear, traer al frente, borrar | No hay menú contextual propio; en escritorio se desactiva el del WebView |
| General | Sin red | Trabajar local; los enlaces no rompen | El tablero es local; la vista previa de enlaces falla con aviso; el PDF degrada sin bloquear el tablero |
| General | Sin clave de IA | Que el ritual no finja | El manifiesto cae a 12 líneas vacías y lo dice; «Volver a mirar» avisa |
| General | Documento pesado | Leer y editar sin perder el hilo | Render por página, avisos de tamaño y OCR seguro; no hay scroll continuo |
| General | Después de un error de guardado | Saber qué se perdió y rescatarlo | Aviso, reintento y exportación de rescate; el estado «Guardado» es honesto |

---

## 5. Debates

### D1 · ¿La marquesina reemplaza o suma?

**Tesis.** Figma, Illustrator y Keynote: arrastrar un rectángulo sobre el vacío define una selección nueva; ⇧ añade; ⌥/Alt resta. Es un contrato tan viejo que nadie lo lee en la ayuda.

**Antítesis.** Sumar siempre es más seguro: nunca se pierde una selección hecha con esfuerzo, y en un lienzo de collage seleccionar de nuevo es barato. El fallo de Prometeo no es sumar, sino que la ayuda diga otra cosa.

**Síntesis.** La marquesina sin modificador **reemplaza**; ⇧ suma; ⌥ resta. La selección es una frase que se está escribiendo, no un historial. Prueba: clic A, marquesina sobre B, solo B seleccionada; ⇧ + marquesina sobre A, A y B.

### D2 · ¿Un marco es un contenedor o una lente?

**Tesis.** En Figma un frame contiene; en Milanote un board contiene; en Freeform un grupo contiene. Si un marco contiene, debe poder sacar una tarjeta arrastrándola fuera y desagrupar con `⌘⇧G`.

**Antítesis.** El marco de Prometeo también es una lente: la misma tarjeta se ve como Archivo, Muro o Mesa sin moverse. Tratarlo como contenedor rígido mataría esa virtud. Además, el vacío japonés y el collage toleran pertenencias ambiguas.

**Síntesis.** Un marco es **las dos cosas, pero con contrato explícito**: como lente, cambiar de vista no toca posiciones; como contenedor, arrastrar fuera desvincula y `⌘G`/`⌘⇧G` agrupan/desagrupan. La pertenencia nunca es un efecto invisible del último arrastre. Prueba: sacar un hijo al vacío deja `hijos` sin su id; `⌘G` sobre dos tarjetas crea un marco con ambas; `⌘⇧G` las deja libres y en su sitio.

### D3 · ¿Borrar sin diálogo exige papelera?

**Tesis.** T-2 acertó: borrar es inmediato y se arregla con deshacer. Pero Figma conserva historial de versiones, Illustrator tiene deshacer persistente en el documento y los sistemas operativos tienen papelera. La red no puede durar 5 segundos.

**Antítesis.** Una papelera es una metáfora de escritorio que ensucia un estudio visual; Milanote la tiene, pero el espíritu de Prometeo es el gesto limpio. Además, el 99 % de los borrados se arregla con `⌘Z`.

**Síntesis.** No hace falta una papelera visible: hace falta **memoria**. El borrado sigue siendo inmediato; el tablero y la referencia borrados entran en un historial persistente de 30 días, recuperable desde «Archivo» o desde el mismo aviso. Las tarjetas conservan los 100 pasos. Prueba: borrar tablero, recargar, recuperarlo; borrar 150 tarjetas en un gesto devuelve las 150; borrar 150 de una en una conserva los 100 últimos pasos.

### D4 · ¿Todo se redimensiona o el papel tiene un ancho?

**Tesis.** Figma, Canva, Keynote y Freeform: cualquier objeto tiene asas. La gente espera arrastrar la esquina de una nota y que la nota cambie.

**Antítesis.** Milanote y los post-it tienen un ancho cómodo de lectura; redimensionar una nota libre rompe la retícula y convierte el collage en un editor de diapositivas. El ancho de papel de Prometeo es una decisión estética, no un olvido.

**Síntesis.** La nota puede cambiar de **ancho**, no de alto: el alto sigue al contenido y el ancho se acota a una banda legible. Columnas y marcos tienen asas completas (no solo SE). Una selección múltiple comparte un solo gesto de ancho. Prueba: arrastrar el asa SE de una nota cambia el ancho y el alto se recalcula; `⇧` mantiene proporción solo donde hay proporción (medios); el ancho no baja de 210 ni sube de 640.

### D5 · ¿Un dedo selecciona o panea?

**Tesis.** Figma en iPad: un dedo selecciona y dibuja marquesina; dos dedos panean; pellizco acerca. Es el estándar táctil de los lienzos.

**Antítesis.** En una pizarra de collage, el gesto más frecuente es mover el mundo, no seleccionar; quizá un dedo debería panear y la selección quedar para una pulsación larga o el lápiz.

**Síntesis.** Un dedo dibuja marquesina (como hoy), **dos dedos panean** y el pellizco acerca; además, un botón «Mano» visible para quien no conoce el gesto. Prueba táctil: un dedo en el fondo crea marquesina; dos dedos mueven la cámara sin seleccionar; el botón Mano también.

### D6 · ¿El teclado debe recorrer un lienzo espacial?

**Tesis.** Figma permite Tab para entrar en el lienzo, flechas para navegar entre capas y Enter para seleccionar; además tiene panel de capas. Illustrator usa `V`/`A` y el teclado para casi todo. Un lienzo profesional se usa sin ratón.

**Antítesis.** Un canvas espacial no tiene orden natural; una navegación por flechas puede ser tan impredecible como un laberinto. Para accesibilidad, una lista ordenada suele ser mejor que un espacio.

**Síntesis.** Dos caminos, no uno: **lista de objetos** (orden de capas, buscable, seleccionable) y **navegación espacial** (Tab entra, flechas van al vecino geométrico, Enter selecciona, Esc sale). Los diálogos atrapan el foco y lo devuelven. Las tareas no secuestran Tab. Prueba: con 50 tarjetas, Tab entra al lienzo; 10 flechas visitan 10 tarjetas; Tab en una tarea pasa a la siguiente; el diálogo no deja salir el foco.

### D7 · ¿Prometeo debe ser Acrobat?

**Tesis.** El usuario que abre un PDF espera seleccionar texto, cambiar una fuente, añadir una firma o una imagen, reordenar páginas y exportar. Acrobat lo hace; Prometeo dice «editor PDF».

**Antítesis.** La promesa de Prometeo es otra: editar sin poner en riesgo el original, con verificación física. Añadir edición libre rompería la garantía y convertiría el producto en un Acrobat peor. El vacío y la contención son parte del diseño.

**Síntesis.** Prometeo no finge: **declara su contrato** («sustituir texto verificable; lo demás, en Acrobat») y ofrece un puente explícito. Si añade tipografía, la añade solo cuando la verificación puede demostrar que el resultado es equivalente; si añade texto/imagen, lo hace en una capa de anotación que no toca el original. Prueba: un PDF sin texto nativo muestra «no editable» con motivo y botón «Abrir en Acrobat»; un PDF nativo permite cambiar tamaño cuando la métrica cabe y lo rechaza cuando no.

### D8 · ¿Buscar atenúa o encuentra?

**Tesis.** Milanote, Figma y Notion muestran resultados, permiten saltar y a veces filtran el lienzo. La búsqueda es una forma de navegación, no un efecto visual.

**Antítesis.** Atenuar conserva el contexto espacial y evita que el tablero «salte» mientras se escribe; en un collage, ver los alrededores importa.

**Síntesis.** Buscar **ilumina y lleva**: los no coincidentes se atenúan, pero aparece una lista de resultados con contador, Enter salta al primero y `⌘F` busca en el alcance visible (tablero, proyecto, biblioteca). Prueba: buscar «alfa» muestra 1 resultado, Enter selecciona y centra la tarjeta; cambiar de alcance encuentra una tarjeta de otro tablero.

### D9 · ¿Pegar texto debe crear una nota?

**Tesis.** Figma, Milanote, Freeform y Keynote: pegar texto crea una nota o un cuadro de texto en el cursor. Pegar una imagen la coloca; pegar una URL crea un enlace.

**Antítesis.** Un lienzo de collage puede preferir que pegar texto no ensucie; obligar a elegir herramienta evita notas accidentales. Además, el portapapeles interno necesita prioridad para no duplicar tarjetas con imágenes pesadas.

**Síntesis.** Pegar es **crear en el cursor**: texto plano → nota; URL → enlace; imagen → medio; tarjetas internas → copia. La marca interna solo se usa cuando el sistema no trae nada. Prueba: pegar «hola» crea una nota con «hola» en el punto del cursor; pegar una imagen la coloca ahí; pegar una tarjeta copiada la duplica con ids nuevos.

### D10 · ¿Un panel de capas o solo el lienzo?

**Tesis.** Figma, Illustrator, Fusion, Keynote y Procreate tienen árbol/lista de objetos. Sin él, un tablero de 500 tarjetas es un mar de papel; el z-order existe pero no se ve.

**Antítesis.** El lente de Prometeo es el collage, no el árbol de capas de Adobe; un panel así puede burocratizar el gesto y romper la atmósfera de mesa.

**Síntesis.** Un **índice del tablero**, no un panel de capas de Adobe: lista de tarjetas y marcos en orden de pintado, con búsqueda, selección múltiple, bloqueo y «traer al frente». Se abre con `Tab` o `L` y no vive permanentemente. Prueba: con 500 tarjetas, el índice lista 500, busca por título, selecciona 3 y las trae al frente; el foco vuelve al lienzo al cerrar.

### D11 · ¿Una imagen es un objeto libre o una tarjeta?

**Tesis.** En Figma una imagen es una capa con nombre, alt y máscara; en Milanote una imagen tiene título y nota; en Keynote se puede recortar y reemplazar. La imagen es contenido editable, no un fondo.

**Antítesis.** La gracia de `BoardFreeMedia` es que la imagen no parece una tarjeta: flota, no tiene borde, no compite con el papel. Darle cabecera y campos la burocratiza.

**Síntesis.** Sigue siendo un objeto libre, pero **la leyenda es editable al seleccionarla** (título, pie, alt) y el reemplazo conserva caja y posición; el recorte vive en un modo de edición, no en la tarjeta en reposo. Prueba: doble clic en la leyenda abre el título; reemplazar una imagen mantiene `x`, `y`, `width`, `height` y el `media` anterior se conserva hasta confirmar.

### D12 · ¿Una columna ordena o solo agrupa?

**Tesis.** Milanote y Notion permiten arrastrar tarjetas dentro de una columna; el orden es el contenido. Una columna que solo ordena por `y` no es una columna, es una lista de lectura.

**Antítesis.** El orden por `y` es predecible y evita un estado extra; en un lienzo espacial, la posición ya es el orden. Añadir un orden interno duplica la fuente de verdad.

**Síntesis.** La columna tiene **orden explícito** cuando se suelta dentro; si nunca se ha soltado, hereda el orden por `y`. El orden se guarda en `datos.hijos`, no en un array paralelo. Prueba: arrastrar el tercer hijo al primero cambia `hijos`; recargar conserva el orden; sacar un hijo lo quita de `hijos`.

### D13 · ¿Borrar un proyecto es borrar o archivar?

**Tesis.** Figma, Notion y Milanote permiten borrar proyectos y ofrecen papelera o restauración. Un proyecto viejo estorba en el selector.

**Antítesis.** Un proyecto contiene tableros, referencias y gustos; borrarlo es el gesto más destructivo del producto. Quizá conviene no ofrecerlo y obligar a archivar.

**Síntesis.** Se puede **archivar** (desaparece del selector, sigue recuperable) y **borrar definitivamente** solo desde Archivo, con confirmación escrita y 30 días de historial. Prueba: archivar oculta del selector sin borrar IndexedDB; borrar definitivamente exige escribir el nombre y se puede recuperar durante 30 días.

### D14 · ¿El zoom es navegación o inspección?

**Tesis.** Figma, Illustrator y Acrobat permiten acercarse mucho porque el detalle importa: kerning, píxeles, líneas de 1 pt. Un máximo de 240 % impide revisar el trabajo.

**Antítesis.** Un lienzo de collage no es un editor de precisión; el zoom alto invita a microajustes que rompen la escala del papel. El límite protege la composición.

**Síntesis.** El zoom es **inspección declarada**: 25–800 % para el tablero y 25–800 % para el PDF, con `⌘0` 100 %, `⌘+/-`, `⇧1` ajustar y `⇧2` selección. El LOD sigue protegiendo el rendimiento. Prueba: el zoom llega a 800 %, `⌘0` vuelve a 100 % y el LOD se activa por debajo del 35 %.

### D15 · ¿Cerrar confía en el autoguardado o fuerza el volcado?

**Tesis.** Figma y Notion guardan en la nube y el cierre no pierde nada; el autoguardado es un contrato, no una promesa. En local, IndexedDB tarda milisegundos, pero puede fallar.

**Antítesis.** El cierre es del sistema operativo; una app no debería secuestrarlo ni fingir que puede escribir después. El aviso del navegador es suficiente.

**Síntesis.** El cierre **fuerza el volcado** (`flushBoardWrites`) y solo entonces permite cerrar; si falla, se queda y explica. El aviso del navegador sigue como última red. Prueba: editar y cerrar en el mismo frame; al reabrir, el cambio está; si IndexedDB falla, la app no cierra y ofrece exportar.

---

## 6. Pregunta abierta

**¿Un marco es un contenedor o una lente?** La respuesta cambia todo lo demás: si es contenedor, arrastrar fuera debe desvincular y `⌘G` debe agrupar; si es lente, la pertenencia no debería depender de la geometría del último arrastre. Prometeo hoy hace las dos cosas a medias: los marcos adoptan por geometría, mueven a sus hijos y cambian de vista sin moverlos, pero no dejan salir. Nadie ha contestado aún qué pasa con una tarjeta que se ve en dos marcos, ni qué significa «deshacer» cuando el marco la adoptó sola.

Pregunta secundaria para la lista: **¿qué significa deshacer en un collage que se ordena solo?** La entropía guarda una semilla y una composición; si el usuario mueve una pieza generada, ¿deshace el gesto o la tirada?

---

## 7. Principios propuestos para `prometeo-lienzo-saber`

Cada principio lleva su prueba; si no se puede probar, no es principio, es deseo.

1. **Seleccionar no acumula sin querer.** La marquesina reemplaza; ⇧ suma; ⌥ resta; ⇧+clic alterna. *Prueba:* A seleccionada + marquesina sobre B = solo B; ⇧+clic sobre B = A y B; ⇧+clic otra vez = solo A.
2. **Lo que entra en un marco puede salir.** Arrastrar al vacío desvincula; `⌘G` agrupa; `⌘⇧G` desagrupa sin mover. *Prueba:* `hijos` antes/después; posiciones intactas al desagrupar.
3. **Todo objeto tiene asas y teclado.** Nota, columna, marco y medio se redimensionan; el mismo cambio se puede hacer sin ratón. *Prueba:* arrastre de asa y combinación de teclas producen el mismo ancho; el foco nunca queda atrapado.
4. **El teclado no se queda encerrado.** Diálogos atrapan y devuelven el foco; Tab no cambia datos; el lienzo tiene entrada y salida. *Prueba:* Tab en tarea pasa a la siguiente; Tab en diálogo no sale; Escape devuelve al disparador.
5. **Borrar es inmediato; olvidar no.** El gesto no pregunta, pero el sistema recuerda tableros, referencias y tarjetas durante 30 días o 100 pasos. *Prueba:* borrar, recargar, recuperar; el aviso de 5 s no es la única red.
6. **Pegar es crear en el cursor.** Texto, URL, imagen y tarjetas internas tienen un destino espacial claro. *Prueba:* cuatro portapapeles producen cuatro resultados en el punto del cursor.
7. **Buscar lleva a algún sitio.** Resultados, contador, salto y alcance visible; atenuar es un extra, no el resultado. *Prueba:* Enter selecciona y centra; el alcance cambia de tablero a proyecto.
8. **El lienzo se navega con el cuerpo.** Un dedo selecciona, dos panean, pellizco acerca; el botón Mano existe para quien no conoce el gesto. *Prueba:* en viewport táctil, un dedo no mueve la cámara y dos sí.
9. **El PDF declara lo que puede y no finge.** Cada PDF muestra su contrato de edición; lo que no se puede verificar se ofrece fuera, no se simula. *Prueba:* PDF escaneado = motivo + puente; PDF nativo = cambio verificado o rechazo explicado.
10. **La tarjeta es texto, imagen y título: todo se edita.** Una imagen puede renombrarse, anotarse, recortarse y reemplazarse sin perder su medio. *Prueba:* doble clic en la leyenda abre el título; reemplazar conserva posición y tamaño.
11. **Guardar se dice en pasado solo cuando el almacén confirma; cerrar fuerza el volcado.** *Prueba:* editar y cerrar en el mismo frame; al reabrir, el cambio está; el estado nunca dice «Guardado» antes de IndexedDB.
12. **Una herramienta nueva no entra sin borrado, deshacer, teclado y estado vacío.** Es la definición de terminado de `prometeo-herramientas`. *Prueba:* plantilla de checklist en la skill y un test por herramienta.

---

## 8. Top 15

Ordenado por gravedad. «Rompe» = impide una tarea básica o puede perder trabajo; «frustra» = se puede hacer, pero duele o engaña; «pule» = falta de acabado profesional.

| # | Hueco | Gravedad | Zona | Prueba propuesta |
|---|---|---|---|---|
| 1 | Borrar un tablero o una referencia PDF es definitivo cuando expira el aviso de 5 s; no hay papelera ni historial persistente. | **rompe** | 5 · Historial | Borrar tablero → recargar → recuperarlo desde Archivo; 150 tarjetas en un gesto → vuelven las 150; 150 gestos → 100 pasos |
| 2 | En iPad/táctil no se puede panear: un dedo en el fondo dibuja marquesina y no hay gesto de dos dedos. | **rompe** | 7 · Gestos | Viewport táctil: 1 dedo = marquesina; 2 dedos = cámara; botón Mano = cámara |
| 3 | Teclado incompleto y con trampas: marcos/columnas no se seleccionan con Enter, el resize es solo puntero, Tab queda atrapado en tareas y los diálogos no atrapan el foco. | **rompe** | 6 · Accesibilidad | Enter selecciona marco/columna; Tab en tarea pasa a la siguiente; diálogo atrapa y devuelve el foco |
| 4 | Un hijo no puede salir de un marco arrastrándolo al vacío; no hay grupo/desagrupar desde una selección. | **rompe** | 1 · Lienzo | Arrastrar hijo al vacío limpia `hijos`; `⌘G` agrupa 2; `⌘⇧G` desagrupa sin mover |
| 5 | El PDF no permite seleccionar/copiar texto con el ratón, cambiar fuente/tamaño/color, añadir texto/imagen ni organizar páginas. | **rompe** (frente a Acrobat) | 3 · PDF | Selección de texto copiable; control de tamaño que verifica o rechaza; capa de anotación para añadir; organizar páginas |
| 6 | La marquesina siempre suma y ⇧+clic nunca quita: la ayuda y el comportamiento no coinciden. | **frustra** | 1 · Lienzo | A + marquesina B = B; ⇧+clic B = A y B; ⇧+clic otra vez = A |
| 7 | Notas y columnas no se redimensionan; los marcos solo tienen asa SE; no hay resize de selección múltiple ni por teclado. | **frustra** | 1 · Lienzo / 2 · Tarjetas | Asa SE en nota cambia ancho; marco en 4 bordes; 3 tarjetas comparten ancho; flechas con modificador |
| 8 | No hay panel/índice de objetos ni capas visibles: con 500 tarjetas no se puede recorrer, buscar ni reordenar con orden. | **frustra** | 1 · Lienzo / 4 · Biblioteca | Índice con 500, búsqueda, selección múltiple, traer al frente; foco vuelve al lienzo |
| 9 | Buscar en el tablero solo atenúa; no hay resultados, contador, salto ni alcance de proyecto/biblioteca; tampoco orden. | **frustra** | 4 · Biblioteca | Buscar «alfa» → 1 resultado → Enter selecciona y centra; cambiar alcance encuentra otro tablero |
| 10 | Pegar texto plano no crea nada y copiar tarjetas no produce contenido interoperable. | **frustra** | 2 · Tarjetas | Pegar «hola» crea nota en cursor; copiar tarjeta y pegarla en otro contexto produce contenido legible |
| 11 | Imagen/vídeo no se pueden renombrar ni anotar; no hay recorte, reemplazo ni alt. | **frustra** | 2 · Tarjetas | Doble clic en leyenda edita título/cuerpo; reemplazar conserva caja; recorte y alt guardados |
| 12 | Las columnas no permiten reordenar sus hijos: se ordenan por `y` y la lista interior no es arrastrable. | **frustra** | 2 · Tarjetas | Arrastrar un hijo dentro de la columna cambia el orden; sacarlo lo desvincula |
| 13 | Proyectos: no se pueden borrar, no se mueve un tablero entre proyectos y renombrar depende de doble clic o `prompt`. | **frustra** | 4 · Biblioteca | Menú de proyecto con Renombrar/Borrar/Mover; `F2` renombra; borrar proyecto va a historial |
| 14 | Zoom máximo 240 % (PDF 250 %), sin `⌘0`, `⌘+`, `⌘-` ni zoom a selección. | **pule** | 1 · Lienzo / 3 · PDF | `⌘0` = 100 %, `⌘+/-` pasos, `⇧1` ajustar, `⇧2` selección; máximo ≥ 400 % |
| 15 | El cierre avisa pero no fuerza el volcado; el deshacer se pierde al recargar y el staging PDF no tiene rehacer. | **pule** | 5 · Historial | Editar y cerrar en el mismo frame → reabrir conserva; historial restaurado o declarado «sesión nueva»; rehacer en PDF |

---

## 9. Encargo A-2 propuesto

No construir nada nuevo antes de cerrar estos contratos. Orden sugerido, por dependencia:

1. **Memoria de borrado** (tablero, referencia, tarjeta): historial persistente de 30 días; el aviso de 5 s sigue, pero deja de ser la única red. Pruebas 1 y 5.
2. **Selección y marcos**: marquesina con modificadores; ⇧+clic alterna; arrastrar fuera desvincula; `⌘G`/`⌘⇧G`; marco con candado. Pruebas 4 y 6.
3. **Táctil**: dos dedos panean, pellizco, botón Mano; touch targets ≥ 24 px. Prueba 2.
4. **Teclado y foco**: marcos/columnas con Enter, resize por teclado, quitar el secuestro de Tab en tareas, trampa y restauración de foco en diálogos, `aria-selected` y contador en vivo. Prueba 3.
5. **Índice del tablero y búsqueda que lleva**: lista de objetos, búsqueda con resultados, alcance y orden. Pruebas 8 y 9.
6. **Asas y pegado**: nota/columna/marco/selección; pegar texto/imagen/URL/tarjetas en el cursor. Pruebas 7, 10 y 11.
7. **Contrato PDF**: pantalla de capacidades, selección/copia de texto, tipografía verificable, capa de anotación y puente a Acrobat. Prueba 5.
8. **Acabado**: zoom con atajos, flush al cerrar, rehacer PDF, contraste de `--paper-muted-2`, revisión VoiceOver. Pruebas 14 y 15.

---

## 10. Lo que ya está bien y no hay que tocar

- El **modelo único** y las vistas (Libre, Archivo, Muro, Mesa) son una ventaja real: una tarjeta no se duplica al cambiar de vista.
- El **autoguardado** con cola serial, estado honesto y exportación de rescate es mejor que el de muchas apps web.
- El **borrado de tarjetas** de T-2 (una pasada, un historial, 500 en 0,6 ms) es de nivel profesional.
- El **trackpad 1:1** de T-1: sin inercia añadida, sin rebote, con pellizco focal. No tocar la física.
- La **inmutabilidad del PDF** y la verificación SHA-256 son el activo más serio del producto; cualquier función nueva debe respetarlas.
- El **LOD** a menos del 35 % y el `contain` del escenario sostienen 500 tarjetas; no romperlo al añadir asas o capas.

---

## 11. Evidencia y reproducibilidad

- Las 14 pruebas temporales viven en `studio/frontend/e2e-a1/a1-audit.spec.ts` y `playwright.a1.config.ts` **solo durante esta auditoría**; no se commitean.
- Motor: `studio-desktop/resources/runtime/bin/python3`, `uvicorn studio.backend.app:app`, vite en `127.0.0.1:5173`.
- Todas las pruebas relevantes pasaron con Brave. Las que fallaron al principio lo hicieron por suposiciones del propio test (un selector demasiado amplio y un render que aún no había terminado); se corrigieron y volvieron a pasar.
- Las líneas citadas son del árbol de trabajo en `studio/collage` en la fecha de la auditoría; si el código cambia, la prueba debe cambiar con él.

---

*Auditoría A-1 · 25-oct-2026 · Sin cambios de código de la app · Sin push.*

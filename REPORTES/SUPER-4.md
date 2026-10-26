# SUPER-4 · Tacto y ahorro

Fecha: 26-oct-2026 · Rama `studio/collage` · Sin push.
Base: T-3 (`85f2fa0`), después de Forja 4 (`e9fa572`).
Commits: `c1fbad0` (I0–I1) · `16db804` (I2–I7) · cierre (este reporte, pruebas y capturas).

---

## 0. Lo que cambió, en una frase

El visor de PDF ya no puede quedarse en blanco sin decirlo; se edita en el sitio
sin crear un archivo por palabra; las tarjetas se mueven desde cualquier parte,
se unen desde el borde y se ajustan con un engranaje; la biblioteca añade al
primer clic; las guías son casi invisibles y cada tablero se configura; y un
Referente acepta cualquier archivo o una URL que se desarma en piezas de collage.

La regla que ordena todo queda escrita en la skill como **regla 21 · Cultura de
ahorro**: la acción más frecuente cuesta un gesto; ningún «Confirmar/Añadir» si
el gesto ya dijo la intención.

---

## 1. I0 · El visor en blanco

### Qué se encontró

No se pudo reproducir el blanco exacto de la captura de Bruno con
«Abrir un ejemplo… → CONTRATO» en 1440×900 ni en 1000×800: el visor pintaba la
página. Sí se encontraron **tres caminos reales** que dejaban la zona del visor
sin contenido visible:

1. **Imagen vacía o rota sin mensaje.** El `<img>` no tenía `onError`; si el
   motor devolvía una imagen ilegible, quedaba el papel blanco y nada más.
2. **Página más ancha que el visor.** Por debajo de ~1180 px, a 100 % la página
   de 595 pt no cabía; la franja visible podía ser solo el margen.
3. **Panel inferior sin tope.** El panel «Cambios» podía crecer hasta 560 px y
   empujar la página fuera de la vista, sobre todo en ventanas de 600–700 px.

### Arreglo

- `PageImage` muestra «La página no se pintó», el motivo y «Volver a dibujar»;
  `data-painted` deja prueba de que la imagen tiene píxeles.
- Ajuste al ancho una vez por página cuando la página supera el visor.
- El panel inferior se limita a 42 % del alto (y deja siempre ≥ 260 px de
  espacio para el documento).
- La prueba nueva (`e2e-super4/s0-visor.spec.ts`) dibuja la imagen en un canvas y
  falla si no hay tinta. Antes la prueba usaba un SVG totalmente blanco: no podía
  distinguir «pintada» de «en blanco».

Capturas: `capturas-super4/I0-despues-visor-1440.png`,
`I0-despues-visor-1000.png`. La captura original de Bruno no está archivada en el
repo; se cita como reporte verbal.

---

## 2. I1 · Editar el PDF en el sitio, sin una copia por palabra

- **Una sesión de trabajo.** Las ediciones se preparan en memoria
  (`stage_edit`) y se pintan en el visor en el mismo commit de React. El overlay
  editado tapa el texto viejo con papel y muestra el nuevo; en la prueba, teclear
  y ver el cambio tarda < 100 ms.
- **Doble clic en la línea** del visor abre un campo dentro del propio overlay,
  con el texto seleccionado. Intro o clic fuera acepta; Esc cancela.
- **Verificación en segundo plano.** Nuevo `POST /api/sessions/{id}/preflight`:
  hace la misma verificación física que la exportación (stage → export temporal
  → Verifier2), pero borra el temporal y no publica ni cambia el estado de la
  transacción. La bandeja muestra «Comprobación previa aprobada» o el motivo.
- **Un archivo solo al exportar.** La bandeja sigue siendo historial; hay un
  botón «Exportar copia» siempre visible en la barra inferior. El original nunca
  se toca: su SHA-256 se comprueba en cada paso.
- **Prueba de archivos** (`tests/studio/test_super4_pdf.py`): diez ediciones
  seguidas no añaden ni un archivo; exportar crea exactamente un PDF verificado;
  el original conserva su SHA-256.

Captura: `I1-despues-edicion-en-sitio.png`.

### Lo que se tomó y lo que devuelve Prometeo

Se toma la edición en el sitio de un editor de texto y la idea de «toca solo lo
que cambia» (regla 11, EditTrans). Lo que no tiene el original: el cambio vive en
una sesión verificable, con comprobación previa en segundo plano, historial y
SHA-256 del original intacto.

---

## 3. I2 · Mover desde cualquier parte y mover muchas

- `pointerdown` en el cuerpo de la tarjeta inicia el arrastre con umbral de 4 px;
  el clic sin movimiento sigue seleccionando y el doble clic entra a escribir.
- El texto en reposo no captura el arrastre (`user-select: none`); al editar, el
  textarea se queda con el gesto.
- **⌘/Ctrl + arrastrar** toma lo que hay debajo aunque sea un campo en edición o
  un hijo de un marco (captura en fase de captura, como Figma).
- Arrastrar una tarjeta seleccionada mueve toda la selección.
- Se quitaron dos dependencias que re-renderizaban las 500 tarjetas en cada
  flecha (`startWidthResize`, `endWidthResize`): ahora leen la tabla viva por
  ref. El tablero de 500 tarjetas baja de ~1 000 renders por flecha a 2.

Capturas: `I2-antes-cuerpo-no-mueve.png` (Forja 4: arrastrar el cuerpo no
mueve), `I2-despues-mover-seleccion.png`.

---

## 4. I3 · Unir con un gesto

- A 12 px del borde aparecen cuatro puntos de unión; entran con un pulso de
  120 ms (1 → 1,15 → 1) y respetan `prefers-reduced-motion`.
- Arrastrar desde un punto hasta otra tarjeta crea una relación; la tarjeta
  destino se ilumina. Soltar en el vacío no crea nada.
- Los puntos solo se montan cuando el puntero está cerca: en reposo no añaden
  nodos al DOM de las 500 tarjetas.
- `⌘Z` deshace la relación como un paso de historial.

Capturas: `I3-antes-boton-relacionar.png` (Forja 4: botón pequeño junto al
título), `I3-antes-arrastrar-punto.png`, `I3-despues-union.png`.

### Lo tomado y lo nuevo

De Figma/Miro se toma el gesto de tirar de un puerto; de Canva, la facilidad de
descubrirlo sin manual. Prometeo lo devuelve sin panel de conector previo: el
punto nace del borde y la relación se deshace con el mismo Cmd+Z que todo lo
demás.

---

## 5. I4 · Ajustes de cada tarjeta

- Al seleccionar aparece un engranaje en la esquina (notas, medios, marcos y
  columnas).
- El panel edita **en vivo**, sin botón Aplicar: color, tipografía, tamaño de
  texto, color de texto, borde (grosor/estilo), sombra, opacidad, bloqueo,
  «convertir en…» (nota, columna, marco).
- Para medios añade recorte (X, Y, zoom) y texto alternativo.
- Con varias seleccionadas el mismo engranaje aplica a todas.
- Cada cambio usa una clave de coalescencia para no llenar el historial con
  cada píxel del range.

Capturas: `I4-antes-sin-engranaje.png`, `I4-despues-ajustes.png`.

### Lo tomado y lo nuevo

De Figma/Illustrator se toma el panel de objeto pegado al objeto; de Canva, que
no haya que «aplicar». Prometeo lo devuelve con conversión de tipo en el mismo
sitio y con deshacer por gesto, sin capas ni inspector separado.

---

## 6. I5 · «N» añade al primer clic

- `N` abre la biblioteca con el foco en la búsqueda y guarda el punto del cursor.
- Un clic en una herramienta la añade ya, en ese punto; no hay paso «Añadir al
  tablero».
- Imagen/vídeo/archivo abren el selector de archivos directamente; Enlace abre
  su diálogo; Marco/Columna/Nota nacen en el cursor.
- La descripción de la herramienta sigue visible al pasar el puntero, como
  quería Bruno, pero no es un paso.
- Arrastrar una herramienta de la biblioteca al lienzo la suelta donde se
  suelta.
- Tabla contada con Playwright (`e2e-super4/s5-biblioteca.spec.ts`). «Antes» es
  el comportamiento de Forja 4 medido sobre `85f2fa0`:

| Tarea (después de pulsar N) | Antes · clics | Después · clics | Qué se quitó |
|---|---:|---:|---|
| Nota | 2 | **1** | seleccionar + «Añadir al tablero» |
| Imagen | 2 (+ archivo) | **1** (+ archivo) | seleccionar + «Añadir»; ahora abre el selector |
| Enlace | 2 | **2** | primer clic ya abre el diálogo; se escribe la URL y se confirma |
| Columna | 2 | **1** | seleccionar + «Añadir» |
| Marco | 2 gestos (seleccionar + dibujar) | **1** | el marco nace en el cursor |

La cuenta no sube en ninguna tarea y baja en cuatro de cinco.

Capturas: `I5-antes-biblioteca-con-anadir.png`, `I5-despues-un-clic.png`.

### Lo tomado y lo nuevo

De Milanote/Freeform se toma la paleta que añade al primer gesto; de Fukasawa,
que el objeto no pida confirmación. Prometeo devuelve además la explicación
contextual sin convertirla en un paso y el arrastre que respeta el punto exacto.

---

## 7. I6 · Guías invisibles y tablero configurable

- Por defecto las guías son de 1 px y opacidad 0,25, solo mientras se arrastra y
  solo cuando hay un ajuste real. Se pueden poner visibles o apagadas.
- El imán se puede apagar; sin él no hay ajuste a otras tarjetas ni a la
  retícula.
- Panel «Este tablero»: guías, imán, retícula, color y textura del fondo, cursor
  (normal, cruz, mano) y densidad de controles. Todo se guarda **por tablero**
  en `board.ajustes` y sobrevive a recargar.
- Las guías ya no se calculan contra la retícula dos veces: la retícula se aplica
  arriba y el imán solo compara con otras tarjetas. Una alineación exacta también
  muestra la guía (antes se ocultaba si el desplazamiento era 0).

Capturas: `I6-antes-sin-panel.png`, `I6-despues-guia-sutil.png`,
`I6-despues-tablero.png`.

### Lo tomado y lo nuevo

De Figma/Sketch se toma el snap y las guías; de las herramientas de dibujo, el
fondo y la retícula. Prometeo devuelve un tablero que puede ser casi mudo: las
guías no decoran, solo confirman un ajuste; y cada tablero tiene su carácter sin
tocar la configuración global.

---

## 8. I7 · Referentes que se desarman en collage

- Un Referente acepta **cualquier adjunto** (PDF, imagen, vídeo, audio, archivo)
  desde el editor, al pegar o al soltar. Se guarda copia local acotada a 12 MB.
- Pegar o soltar una URL en un Referente guarda la vista previa (título,
  descripción, imagen social) y deja la tarjeta **bloqueada** como original fijo;
  ofrece «Desarmar».
- «Desarmar» llama al backend local:
  - descarga el HTML sin ejecutar su JavaScript, con timeout, límite de tamaño y
    guardia SSRF;
  - consulta `robots.txt` y, si bloquea, avisa y no descarga;
  - extrae imágenes, titulares, textos, paleta y familias tipográficas;
  - **descarga las imágenes a la carpeta del proyecto**
    (`workspace/instances/…/referentes/<hash>/`) y devuelve también su `data:`
    para que el tablero siga siendo portable;
  - guarda `fuente` (URL de origen) en cada pieza y `desarmadoDe` para poder
    reemplazar piezas anteriores sin duplicarlas.
- El original queda bloqueado; las piezas —imagen, nota de titular, nota de
  texto, color y tipografía— se colocan a izquierda y derecha como material
  editable.

Capturas: `I7-antes-referente-sin-adjuntos.png`, `I7-despues-desarmar.png`.
Prueba de backend: `tests/studio/test_super4_referentes.py` (parser, captura
mínima y endpoint con fuente en cada pieza).

### Lo tomado y lo nuevo

De Are.na/Pinterest se toma guardar el original como ancla; de los talleres de
collage, cortar el material en piezas. Prometeo devuelve algo que ninguno hace:
la página se convierte en materia prima editable **sin ejecutar su código** y
cada pieza conserva la URL de origen, mientras el original queda fijo y
bloqueado.

---

## 9. Verificación

| Comprobación | Resultado |
|---|---|
| `npx tsc -b` | limpio |
| `npx vitest run` | **238/238**, 41 archivos |
| `npx oxlint` | **0 errores**; 52 avisos (ninguno bloqueante; la mayoría vienen de hooks y refs del tablero) |
| `npx vite build` | correcto (507 ms) |
| `npx playwright test -c playwright.super4.config.ts` | **15/15** |
| `npx playwright test -c playwright.l1.config.ts` | **12/12** |
| `npx playwright test -c playwright.l2.config.ts` | **4/4** |
| `npx playwright test -c playwright.forja4.config.ts --grep-invert "T-3 · autosave"` | **28/28** |
| T-3 autosave (rendimiento, 500 tarjetas) | **falla por entorno**, también en la base |
| `python -m unittest tests.studio.test_super4_pdf …test_super4_referentes …test_g6_pdf …test_h8_document` | **11/11** |

### T-3 · por qué no está verde

La prueba de longtasks > 200 ms con 500 tarjetas falla en esta sesión **también
sobre la base `85f2fa0`, sin estos cambios**: se midieron 741 ms y, en una
segunda pasada en reposo, 239 ms. Con SUPER-4 el peor caso bajó a ~596 ms
(medido en el mismo equipo), pero el umbral sigue por debajo del ruido de esta
máquina. No se tocó el umbral ni la prueba para hacerla pasar. El resto de
Forja 4 (28 pruebas) está verde y L1/L2 también.

---

## 10. NO VERIFICADO / límites

- **El blanco exacto de la captura de Bruno no se reprodujo.** Se cerraron los
  tres caminos que podían producirlo y la prueba de píxeles impide una regresión
  silenciosa. No se probó la app Tauri empaquetada en esta sesión, solo el
  navegador (Brave) a 1440 y 1000 px.
- **La «captura» de una URL es la imagen social (`og:image`)** o, si no hay, una
  tarjeta SVG con título y dominio. No es una captura de pantalla renderizada:
  el backend no ejecuta un navegador headless. Queda dicho en la interfaz como
  vista previa, no como foto.
- **I7 no ejecuta JavaScript ajeno.** Páginas que construyen su contenido en el
  cliente (SPA) pueden devolver pocas piezas; se avisa con lo que haya.
- **robots.txt** se respeta con el agente de Prometeo; no se añadió gestión de
  cookies, muros de pago ni autenticación.
- **Recorte de medios:** el panel mueve el recorte existente (`datos.recorte`),
  pero no rota ni reencuadra con asas nuevas.
- **Edición PDF en el sitio:** el texto nuevo se pinta sobre el papel con la
  tipografía de la interfaz; la copia verificada es la que manda y puede recortar
  o ajustar la métrica. No se re-rasteriza la página en el visor en cada tecla.
- **Verificación previa:** usa la misma autoridad física que la exportación y
  borra su temporal; si la sesión tiene mezcla raster/vector, la comprobación
  previa se rechaza con el motivo (igual que la exportación).
- **T-3** queda como deuda de entorno/rendimiento, con evidencia de que la base
  también falla; no se declara verde.

---

## 11. Filosofía: qué se tomó, de quién, y qué devuelve Prometeo

No se copió la interfaz de Canva, Figma, Adobe o Autodesk. Se tomaron gestos y
leyes:

| Se tomó | De quién | Lo que Prometeo devuelve que el original no tiene |
|---|---|---|
| Mover desde el cuerpo y en grupo | Figma, Illustrator, Fusion 360 | Un tablero que además es documento verificable y guarda cada gesto en su historial local |
| ⌘/Ctrl + arrastrar para entrar en lo que hay debajo | Figma | Lo mismo sobre un PDF real, no sobre una maqueta |
| Puertos de conexión al borde | Figma, Miro, Whimsical | Puntos que solo existen cuando hacen falta y un conector que se deshace con Cmd+Z |
| Panel de objeto sin «Aplicar» | Figma, Canva | Conversión de tipo y estilo en el mismo lugar, con el original intacto |
| Paleta que añade al primer gesto | Milanote, Freeform | Explicación al pasar el puntero, sin paso intermedio |
| Guías que solo confirman | Figma, Sketch | Guías casi invisibles por defecto y configurables por tablero |
| Original fijo + material cortado | Are.na, collage analógico | Desarme de una página en piezas con procedencia, sin ejecutar su JS |

La prueba de la regla 21 no es una opinión: los clics por tarea están contados en
Playwright y la tabla de §6 no sube en ninguna tarea. La siguiente vez que una
interacción pida un botón «Añadir» o «Confirmar», la regla la rechaza.

---

## 12. Archivos principales

- `studio/frontend/src/components/Viewport.tsx` · visor, edición en el sitio,
  imagen no pintada, ajuste al ancho.
- `studio/frontend/src/App.tsx` · texto optimista, exportar siempre visible,
  tope del panel inferior, props estables del tablero.
- `studio/backend/session.py` · `preflight()` con temporal borrado.
- `studio/frontend/src/hooks/useTransaction.ts` · comprobación previa en segundo
  plano por cambio.
- `studio/frontend/src/components/BoardCardItem.tsx`,
  `BoardFreeMedia.tsx`, `BoardColumn.tsx`, `BoardWorkspace.tsx` · mover, unir,
  engranaje, biblioteca, ajustes por tablero.
- `studio/frontend/src/board/model.ts` · `estilo` de tarjeta y `ajustes` de
  tablero normalizados.
- `studio/frontend/src/board/tools/referente.tsx` y
  `studio/frontend/src/board/referentes/model.ts` · adjuntos y desarme.
- `studio/backend/app.py` · `/api/referentes/desarmar`, parser sin JS, robots,
  imágenes al proyecto.
- `studio/frontend/e2e-super4/` · 15 pruebas de I0–I7.
- `tests/studio/test_super4_pdf.py`, `test_super4_referentes.py` · archivos y
  desarme con el Python empaquetado.

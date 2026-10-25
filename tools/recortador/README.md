# D-1 · Recortador de referentes

SAM 2.1 Hiera Small local, CPU por defecto o MPS explícito. Python 3.11,
una inferencia a la vez mediante bloqueo de fichero, dos hilos Torch, prioridad
`nice 15`, sin compilar kernels CUDA. Todo queda en esta carpeta.

## Instalación y CLI

```sh
sh tools/recortador/instalar.sh
nice -n 15 tools/recortador/.venv/bin/python -B tools/recortador/recortador.py foto.png \
  --prompts indicaciones.json --salida tools/recortador/salidas/ejemplo
nice -n 15 tools/recortador/.venv/bin/python -B tools/recortador/recortador.py foto.png \
  --rejilla 8 --salida tools/recortador/salidas/propuestas
```

La instalación requiere red una vez. La inferencia no descarga nada. Los pesos
se verifican antes de cargarlos y quedan ignorados por Git, igual que entornos,
imágenes, PDF y salidas. Una carpeta de salida existente se rechaza.

```json
{"coordenadas":"imagen_px","piezas":[
  {"nombre":"silla","tipo":"objeto","caja":[20,30,210,300]},
  {"nombre":"lámpara","puntos":[[300,120],[250,20]],"etiquetas":[1,0]}
]}
```

Una pieza acepta caja, puntos o ambos. `1` incluye y `0` excluye. Cajas `xyxy`
con extremo final exclusivo. Coordenadas de la imagen orientada por EXIF.
El modelo devuelve la máscara y su IoU predicha: no es probabilidad ni garantía.
La rejilla usa 2–16 puntos por lado, uno cada vez, puntuación mínima 0,8,
área mínima 64 px, descarta máscaras de más del 90 % de imagen o que cubran más
de la mitad de una franja exterior del 2 % (posible fondo) y elimina
repeticiones con IoU > 0,85. Este filtro conservador puede omitir objetos que ocupen
todo el borde: selecciónalos explícitamente. Son propuestas para revisar, no
reconocimiento semántico.

## Documentos y planos

```sh
nice -n 15 tools/recortador/.venv/bin/python -B tools/recortador/recortador.py plano.pdf \
  --pagina 1 --ppp 150 --tesela 1 --prompts bloques.json \
  --salida tools/recortador/salidas/plano-1
```

PDF se rasteriza con PyMuPDF a 150–300 ppp. Una página mayor que 2048 px se divide
en teselas de hasta 2048 × 2048; `--tesela` selecciona una (desde 1, por filas), y
la salida indica `total_teselas`. Repite la operación para las restantes. Para
un bloque que cruza una unión usa `--region-pagina x0 y0 x1 y1` en puntos de página,
siempre que esa región quepa en 2048 px a los ppp elegidos. Nunca se reduce el DPI
silenciosamente. Las fotos de más de 2048 px se rechazan antes de decodificarlas.

El JSON puede usar `coordenadas: "pagina_pt"` para PDF. Las cajas exportadas
incluyen `caja` en píxeles de tesela y `caja_pagina` en puntos (1/72 pulgada), origen
superior izquierdo de la página visible y rotada; se conserva la matriz de
desrotación de PyMuPDF para consumidores que necesitan coordenadas sin rotar.
`--documento` aplica la misma política de bloques a imágenes de páginas ya rasterizadas;
en ese caso las coordenadas de página son píxeles, pues no se inventa un DPI.

En fotos el alfa sigue la silueta SAM y respeta el alfa original. En documentos
se conserva el rectángulo del bloque, incluido el papel entre letras o celdas:
si hay caja del usuario, esa caja manda (`bloque_caja_usuario`); con puntos o
rejilla se usa la envolvente SAM (`bloque_envolvente_sam`). Se conserva por separado
la caja y área SAM. El tipo texto/tabla/cota/simbolo/leyenda/cajetin es una etiqueta
del usuario, nunca una clasificación atribuida al modelo.

## Salidas y Mesa de luz

- `pieza-001.png`…: RGBA, alfa, caja ajustada al contenido exportado.
- `piezas.json`: caja, área, puntuación, prompt, política de alfa, SHA256 original,
  SHA256 del raster RGB y del PNG, página/tesela/ppp, modelo y procedencia.
- `tablero.json`: exportación `prometeo-studio-board` v1, PNG embebidos y un marco
  con `vista: mesa`; se importa como un tablero de Prometeo.

No había un archivo llamado `tablero.json` en la base `d6d3558`, pero sí el contrato
`BoardExport` en `studio/frontend/src/board/model.ts` y `FrameData` en `frames.ts`.
`tablero.py` es el adaptador a esos contratos. No escribe en el estado de Studio.

## Modelo y licencia

[Meta declara Apache-2.0 para los pesos](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/README.md#license).
[Licencia fijada al código utilizado](https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/LICENSE).

Pesos oficiales: `sam2.1_hiera_small.pt`, descargados de
<https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt>.
SHA256 calculado: `6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38`.
Código SAM fijado a `2b90b9f5ceec907a1c18123530e92e794ad901a4`.
El manifiesto `modelo.json` y el descargador fijan estos valores. La huella es
una medición de la descarga, no una firma publicada por Meta.
PyMuPDF tiene su licencia propia AGPL/comercial; la licencia Apache de SAM no
se extiende a esa dependencia. Véase <https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright>.

Se buscaron referencias PRAGMA en `~/Documents` y `~/Projects`: se localizaron
la cronología SAM y un adaptador de reproducción offline, pero no se identificó
con certeza el runner de 26 cajas. Este recortador usa directamente la API oficial.

## Página local

```sh
nice -n 15 tools/recortador/.venv/bin/python -B tools/recortador/servidor.py
```

Abre <http://127.0.0.1:8765>. Carga un archivo, haz clic o arrastra una caja,
guarda cada selección y pulsa «Recortar selecciones». «Proponer sin clics» usa
la rejilla. La misma pantalla permite cambiar página, ppp y tesela de un PDF,
revisar las piezas sobre damero y descargar PNG, `piezas.json` y `tablero.json`.
Hay una alternativa con JSON para introducir coordenadas sin ratón.
El servidor se limita a loopback, comprueba origen y token, procesa las solicitudes
secuencialmente y no expone rutas arbitrarias del disco. `Ctrl-C` lo detiene.
Los archivos cargados se eliminan al cerrar; los resultados permanecen en `salidas/`.

## Pruebas reproducibles sin red externa

Con las dependencias y los pesos ya instalados:

```sh
nice -n 15 tools/recortador/.venv/bin/python -B -m unittest discover \
  -s tools/recortador -p 'test_*.py' -v
RECORTADOR_DISPOSITIVO=mps nice -n 15 tools/recortador/.venv/bin/python -B \
  -m unittest discover -s tools/recortador -p 'test_sam.py' -v
node tools/recortador/test_tablero.cjs ruta/tablero.json
```

`test_recortador.py` comprueba contratos, alfa, rechazos, bloqueo de inferencias,
limpieza tras fallos, PDF a 150/300 ppp, rotación, regiones y HTTP de loopback.
`test_sam.py` ejecuta SAM real con `socket.connect` bloqueado: tres imágenes
(rectángulo, círculo y triángulo), una página sintética con dos bloques de texto
dibujado y una tabla, y rejilla 4×4. No sustituye SAM por máscaras precalculadas.
Exige error de área ≤5 % y también IoU ≥0,95 en las tres formas. Para el documento,
la verdad de referencia es el rectángulo del bloque indicado, no sus píxeles de tinta.
Las máscaras SAM quedan registradas como área/caja/puntuación separadas.

`test_tablero.cjs` transpila en memoria el normalizador **real** de esta rama de
Studio y exige igualdad exacta tras normalizar el tablero. Necesita TypeScript
ya instalado en `studio/frontend/node_modules`, o un segundo argumento con la
ruta de un `typescript.js` existente. No instala ni escribe fuera del recortador.

Los ficheros `evidencia-cpu.json` y `evidencia-mps.json` son mediciones sintéticas,
no pruebas de exactitud sobre fotos reales. Guardan versiones, casos, tiempo y
pico RSS del proceso en macOS. El RSS de MPS no mide toda la memoria del driver
Metal ni el consumo total del sistema. La máquina de prueba tiene 8 GiB de RAM.

MPS con Torch 2.5.1 no implementa `aten::upsample_bicubic2d.out`: el motor habilita
`PYTORCH_ENABLE_MPS_FALLBACK=1` antes de importar Torch, y registra
`mps_fallback_cpu: true`. Es MPS con operaciones auxiliares en CPU, no MPS puro.
Si integras la clase en otro proceso, establece esa variable **antes** de importar
Torch. CPU sigue siendo el valor por defecto; no se fuerza a cambiar de dispositivo
si MPS falta o falla.

## Alcance pendiente

NO VERIFICADO: exactitud en fotos reales, documentos escaneados o planos reales;
clasificación semántica automática de bloques (no implementada); importación
interactiva en la aplicación completa Prometeo (sí probado su normalizador real);
ejecución en la segunda Mac y MPS puro. Los tipos de bloque son indicaciones del
usuario. Los bloques que tocan el borde de una tesela se señalan para revisarlos.

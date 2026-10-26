# Índice visual de referentes

Embeddings locales con **SigLIP base patch16 224**, en CPU o MPS. No se entrena el modelo. Ejecuta los comandos con `nice -n 15` y lotes de 1–2 en una Mac de 8 GB.

## Procedencia del modelo

- Repositorio de pesos: [google/siglip-base-patch16-224](https://huggingface.co/google/siglip-base-patch16-224), revisión `264b4cf2be2e3805db80dd7f84df43989a4b76e0`.
- Licencia declarada para modelo y pesos: **Apache-2.0** en el repositorio del modelo. Código de `transformers`: **Apache-2.0**.
- `model.safetensors`: SHA-256 **publicado** `2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8`; `modelo.py` lo recalcula sobre la descarga y rechaza cualquier discrepancia.
- Fuentes: [ficha del modelo](https://huggingface.co/google/siglip-base-patch16-224/tree/main), [archivo y SHA-256](https://huggingface.co/google/siglip-base-patch16-224/blob/264b4cf2be2e3805db80dd7f84df43989a4b76e0/model.safetensors), [código de SigLIP](https://github.com/huggingface/transformers/blob/main/src/transformers/models/siglip/modeling_siglip.py).

La revisión histórica de pesos no contiene README. La declaración Apache-2.0 se comprobó en la ficha oficial, revisión `7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed`; se conserva la procedencia en `evidencias/licencia_modelo.json`. El SHA publicado de los pesos históricos se comprobó por separado y se recalcula al cargar el modelo.

Los pesos se guardan en `tools/indice/.cache/hf/`, ignorado por Git. Tampoco se versionan imágenes ni índices generados.

## Instalación

Desde `tools/indice/`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

La primera ejecución necesita conexión para descargar los pesos. `requirements.txt` incluye OpenCV para video y PyMuPDF para PDF. Las versiones fijadas son las verificadas aquí con Python 3.9.6 en macOS ARM.

## Indexar

```sh
nice -n 15 .venv/bin/python indexar.py /ruta/a/referentes --salida salidas/mi-indice --lote 2 --dispositivo cpu
```

Se recorren imágenes de forma recursiva; si hay videos, se muestrea un fotograma cada 5 segundos, hasta 24 por archivo. `--cada-segundos` y `--max-fotogramas` cambian esos límites. El directorio de salida contiene `vectores.npz` (vectores normalizados, IDs y SHA-256 de archivos fuente) e `indice.json` (rutas relativas, SHA-256, huella visual, tiempos de fotogramas, modelo y revisión). La carpeta de origen se lee sin modificarla.

También se rasteriza cada página PDF con PyMuPDF, una por vez, con el lado mayor limitado a 1024 px (`--pdf-lado-max`, 224–2048). Cada página conserva número de página (desde 1), SHA-256 del PDF y hash de píxeles. Los PDF cifrados que necesitan contraseña se rechazan. No se guardan las rasterizaciones.

Si existe `tools/recortador/`, se incluyen sus medios recursivamente. `--recortes /ruta/a/piezas` permite indicar otra salida y `--sin-recortes` desactiva esta entrada. Se evitan raíces solapadas, enlaces simbólicos, carpetas ocultas y el directorio de salida. `raices`, `origen` y `ruta_fuente` permiten resolver las rutas de cada entrada; `recortador/` prefija las rutas de la segunda raíz. En la revisión base no existe el recortador: la integración se prueba con piezas sintéticas.

PyMuPDF 1.26.5 soporta el Python 3.9 de esta Mac. Su licencia es AGPL-3.0 o comercial, distinta de la licencia de SigLIP: [distribución oficial y licencia](https://pypi.org/project/PyMuPDF/1.26.5/). La instalación queda en `.venv`, dentro de `tools/indice/`.

## Buscar

```sh
nice -n 15 .venv/bin/python buscar.py parecidos salidas/mi-indice --imagen /ruta/a/consulta.jpg -n 12
nice -n 15 .venv/bin/python buscar.py parecidos salidas/mi-indice --fila 0 -n 12
nice -n 15 .venv/bin/python buscar.py duplicados salidas/mi-indice
nice -n 15 .venv/bin/python buscar.py grupos salidas/mi-indice -k 8
```

`--fila` reutiliza un vector indexado y excluye esa misma fila de los resultados; no carga de nuevo el modelo. `duplicados` encuentra bytes idénticos, píxeles idénticos y pares con dHash a distancia ≤6 **y** similitud de embeddings ≥0,95. Los umbrales son ajustables y las comparaciones de pares crecen cuadráticamente con el número de elementos. `grupos` usa k-means esférico determinista en NumPy; agrupa afinidad visual, no categorías semánticas garantizadas.

Los índices nuevos guardan además el SHA-256 del `.npz`; el lector lo verifica antes de cargar vectores. Esto detecta archivos alterados o una escritura interrumpida entre NPZ y JSON. Los índices previos sin este campo siguen admitidos con las comprobaciones de IDs, dimensiones y hashes de fuentes. La consulta externa verifica también la identidad del modelo. Los grupos conservan la procedencia de cada miembro.

## Medir solo con datos sintéticos

```sh
nice -n 15 .venv/bin/python medir.py --n 12 --lote 2 --dispositivo cpu
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s . -p 'test_*.py' -v
```

`medir.py` dibuja referentes artificiales en memoria y produce tres consultas por base: recorte, giro de 12° y cambio de color. Compara cada consulta contra las bases y comunica recall@1 y recall@5 global y por transformación. No acepta rutas de datos reales ni guarda las imágenes. Las pruebas usan vectores falsos para verificar el cálculo sin descargar pesos.

## Exportar etiquetas y holdout

```sh
nice -n 15 .venv/bin/python exportar.py salidas/mi-indice --gustos /ruta/a/gustos.json --salida salidas/dataset
```

`gustos.json` se abre **solo para lectura**. Si no se indica, se busca junto a la carpeta de medios o al índice. El formato actual de Studio guarda pesos en `referentes`: peso >1 se interpreta como ♥ acumulado y peso <1 como ✕ acumulado; 1 queda sin etiqueta. También se aceptan entradas explícitas `items` con `voto: "♥"/"✕"`. Solo se vinculan claves que coincidan con SHA-256, ID o ruta relativa de un elemento indexado. El manifiesto muestra las claves sin vincular; no se inventan correspondencias para `reglas`, `herramientas` o `pares`.

La búsqueda automática también revisa `gustos.json` en la raíz del repositorio. Las páginas PDF y fotogramas de un mismo archivo siempre comparten partición. El dataset conserva `pagina`, `fotograma`, `origen`, `ruta_fuente` y todas las raíces; no pierde la ubicación de piezas externas. Se validan todas las asignaciones ya congeladas, incluso fuentes retiradas, y se rechaza una salida que sobrescribiría gustos o el índice.

Se escriben `train.jsonl`, `holdout.jsonl`, `sin_etiqueta.jsonl`, `holdout.json` y `manifest.json`, sin copiar imágenes ni pesos. La asignación train/holdout depende del SHA-256 del **archivo fuente**, el porcentaje y una sal fija; `holdout.json` conserva la asignación y rechaza cambios de política. Los derivados deben declarar su procedencia mediante `piezas.json` o `--origenes mapa.json` (objeto SHA-256 del derivado → SHA-256 de su fuente original). Se resuelve el linaje transitivo; se rechazan ciclos, contradicciones y recortes de la raíz recortador sin procedencia. En la raíz general, el productor debe declarar los derivados: no se puede deducir su origen por píxeles. El holdout v2 usa `sha256_origen`; rechaza el v1, que debe conservarse en otra carpeta para auditoría. Este exportador no entrena nada.

## Verificación en esta Mac — 25/10/2026

- Peso descargado y SHA-256 recalculado: `2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8`, coincide con el publicado.
- Ocho pruebas unitarias, sin omisiones: imágenes, PDF grande acotado, video, piezas, duplicados casi exactos, integridad, etiquetas y holdout. Registro: `evidencias/pruebas.txt`.
- Verificación integral con SigLIP real y medios exclusivamente sintéticos: 8 imágenes, 2 páginas PDF y 2 fotogramas, búsqueda de 12 vecinos, duplicados, 3 grupos y exportación repetible. CPU, lote 1, nice 15, 6,89 s y pico RSS del proceso 685,64 MiB. Son medidas de esta ejecución pequeña, no una garantía de memoria para toda entrada.
- 18 consultas sintéticas, 6 bases: recall@1 **0,9444** y recall@5 **1,0**. Recorte: 0,8333/1,0; giro: 1,0/1,0; color: 1,0/1,0. Un recorte de `ref-01` queda segundo: se conserva el resultado negativo y el primer ensayo fallido. No se ajustaron modelo ni umbrales para ocultarlo.
- `pip check`: correcto. Evidencia estructurada: `evidencias/integral_cpu.json`.

Reproducir desde la raíz del repositorio (quitar `HF_HUB_OFFLINE=1` si todavía no hay caché):

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 VECLIB_MAXIMUM_THREADS=2 HF_HUB_OFFLINE=1 nice -n 15 tools/indice/.venv/bin/python tools/indice/verificar_sintetico.py
```

**NO VERIFICADO:** MPS, otra Mac, calidad con referentes reales, miles de archivos y salidas reales del recortador (no existe en esta base). No se encontró `gustos.json` real: el vínculo con IDs de tarjetas de Studio requiere una correspondencia explícita con archivos; las claves desconocidas se reportan sin inventarla. El holdout v2 agrupa por fuente original declarada; procedencias ausentes o falsas en imágenes de la raíz general no pueden detectarse visualmente. El porcentaje hash no garantiza ambos splits con datasets diminutos. No hubo entrenamiento ni medición sobre datos reales.

## Entrega al propietario

`entrega/D2-indice-visual-master.zip` contiene código y documentación en `FULL/`, evidencias y parches por commit en `RECUPERACION/`, más manifiestos SHA-256 y CRC-32. No contiene pesos, medios, entorno virtual ni cachés. `empaquetar.py` genera y verifica el ZIP desde un commit limpio; la suma del contenedor y la verificación de todos los miembros quedan en `entrega/verificacion.json`. El commit fuente del paquete se identifica dentro de él; un commit posterior incorpora únicamente el contenedor y su verificación.

## Corrección D-10 / paso 0 — 26-10-2026

Nueve pruebas pasan, incluida una con hashes de derivados que antes caían en
ambos splits y ahora comparten origen. `evidencias/origen_cpu.json` conserva
la repetición con pesos SigLIP verificados: ensayo histórico completo, 18
consultas, **0,9444 / 1,0** (igual al anterior); evaluación filtrada por
SHA-256 del origen holdout, **0,6667 / 1,0**, 3 consultas de 1 origen.
No comparar directamente tamaños de muestra distintos ni llamar a esto
generalización a fuentes de datos nuevas. Galería fija de 6 referentes;
solo las consultas se restringen al holdout, sin entrenamiento. CPU nice 15,
129,65 s incluyendo descarga inicial, 663,84 MiB RSS.
El ZIP de entrega anterior es histórico y no contiene esta corrección; usar
el código de la rama y el commit de D-10.

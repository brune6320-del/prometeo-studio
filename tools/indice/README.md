# Índice visual de referentes

Embeddings locales con **SigLIP base patch16 224**, en CPU o MPS. No se entrena el modelo. Ejecuta los comandos con `nice -n 15` y lotes de 1–2 en una Mac de 8 GB.

## Procedencia del modelo

- Repositorio de pesos: [google/siglip-base-patch16-224](https://huggingface.co/google/siglip-base-patch16-224), revisión `264b4cf2be2e3805db80dd7f84df43989a4b76e0`.
- Licencia declarada para modelo y pesos: **Apache-2.0** en el repositorio del modelo. Código de `transformers`: **Apache-2.0**.
- `model.safetensors`: SHA-256 **publicado** `2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8`; `modelo.py` lo recalcula sobre la descarga y rechaza cualquier discrepancia.
- Fuentes: [ficha del modelo](https://huggingface.co/google/siglip-base-patch16-224/tree/main), [archivo y SHA-256](https://huggingface.co/google/siglip-base-patch16-224/blob/264b4cf2be2e3805db80dd7f84df43989a4b76e0/model.safetensors), [código de SigLIP](https://github.com/huggingface/transformers/blob/main/src/transformers/models/siglip/modeling_siglip.py).

Los pesos se guardan en `tools/indice/.cache/hf/`, ignorado por Git. Tampoco se versionan imágenes ni índices generados.

## Instalación

Desde `tools/indice/`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

La primera ejecución necesita conexión para descargar los pesos. Para fotogramas de video instala además `opencv-python-headless>=4.8,<5`.

## Indexar

```sh
nice -n 15 .venv/bin/python indexar.py /ruta/a/referentes --salida salidas/mi-indice --lote 2 --dispositivo cpu
```

Se recorren imágenes de forma recursiva; si hay videos, se muestrea un fotograma cada 5 segundos, hasta 24 por archivo. `--cada-segundos` y `--max-fotogramas` cambian esos límites. El directorio de salida contiene `vectores.npz` (vectores normalizados, IDs y SHA-256 de archivos fuente) e `indice.json` (rutas relativas, SHA-256, huella visual, tiempos de fotogramas, modelo y revisión). La carpeta de origen se lee sin modificarla.

## Buscar

```sh
nice -n 15 .venv/bin/python buscar.py parecidos salidas/mi-indice --imagen /ruta/a/consulta.jpg -n 12
nice -n 15 .venv/bin/python buscar.py parecidos salidas/mi-indice --fila 0 -n 12
nice -n 15 .venv/bin/python buscar.py duplicados salidas/mi-indice
nice -n 15 .venv/bin/python buscar.py grupos salidas/mi-indice -k 8
```

`--fila` reutiliza un vector indexado y excluye esa misma fila de los resultados; no carga de nuevo el modelo. `duplicados` encuentra bytes idénticos, píxeles idénticos y pares con dHash a distancia ≤6 **y** similitud de embeddings ≥0,95. Los umbrales son ajustables y las comparaciones de pares crecen cuadráticamente con el número de elementos. `grupos` usa k-means esférico determinista en NumPy; agrupa afinidad visual, no categorías semánticas garantizadas.

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

Se escriben `train.jsonl`, `holdout.jsonl`, `sin_etiqueta.jsonl`, `holdout.json` y `manifest.json`, sin copiar imágenes ni pesos. La asignación train/holdout depende del SHA-256 del **archivo fuente**, el porcentaje y una sal fija; `holdout.json` conserva la asignación y rechaza cambios de política. Reencuadres o duplicados visuales con bytes distintos podrían caer en ambos conjuntos: revisar antes de entrenar. Este exportador no entrena nada.

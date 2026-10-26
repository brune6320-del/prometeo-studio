# Examen ciego v2 · Drive de Bruno

Este protocolo reemplaza el sellado antiguo de recortes. Codex no abre ni lista
la carpeta real. Solo recibirá `examen-sellado.json`. El examen lo ejecuta Bruno
una vez en `evaluar_examen_colab.ipynb`, después de congelar pesos y catálogo.

## 1. Prerregistro público antes del sello

`PRERREGISTRO.md` v2 está publicado desde el commit `b0de0bf`. Umbrales sin cambios:
mejora top-1 >=0,05 y top-1 >=0,80, top-5 >=0,95, MAE <=1 pt, ΔE2000 medio <=3.
La versión inicial anterior al humo se conserva en `examen/PRERREGISTRO-v1.md`.

SHA-256 de la v2, que Claude debe conservar **antes** de sellar:

`16b5a933c466c04eaa9a28e06dcb62ceb4be2c66b73e1391b1a16d546637d776`

No sustituirlo por un hash recalculado después de editar el protocolo. Los alias
de fuentes públicas y sus hashes quedan en `examen/catalogo_preexamen.json` y
`examen/protocolo.json`; no se adaptan después de mirar los PDFs.

## 2. Claude sella; Bruno conserva los PDF

Bruno deposita 10–20 PDF propios en Google Drive, carpeta `d10-examen`. Ninguno
de terceros, firmado o sellado. Claude, en el hilo del plan maestro, comprueba
la carpeta y publica **sin nombres ni contenido**:

```json
{
  "version": 1,
  "documentos": [
    {"sha256": "64 caracteres hexadecimales reales", "n_paginas": 3, "tipo": "nativo"},
    {"sha256": "otro SHA real", "n_paginas": 1, "tipo": "escaneado"}
  ]
}
```

El ejemplo abreviado no es ejecutable: son obligatorios 10–20 registros únicos.
También se acepta una lista JSON directa de esos registros. Ninguna otra clave
por documento está permitida. Claude conserva/publica el SHA-256 del JSON exacto.
Tipo `nativo`: al menos una página con texto extraíble no blanco; `escaneado`:
ninguna. Un mixto es `nativo`, con páginas sin referencia contadas después.
No filtrar documentos en función del rendimiento esperado ni adaptar el catálogo.
PDFs recomprimidos pueden tener hashes distintos: Claude/Bruno deben comprobar
que no sean versiones de documentos usados en entrenamiento.

## 3. Congelar los modelos ANTES de abrir el examen

El entrenamiento sintético (20 épocas) y afinado A (5) ocurren en otro cuaderno,
sin acceso programático a `d10-examen`. El preparador antiguo `preparar_examen.py`
solo acepta `--modo train` sobre una carpeta diferente de PDFs propios para
entrenamiento; el modo holdout persistente está deshabilitado.

Conservar SHA de pesos de ambas etapas y `galeria.json` al acabar entrenamiento,
fuera del cuaderno de examen. El checkpoint afinado debe declarar el SHA de los
mismos pesos sintéticos de partida y la unión de familias/documentos vistos.
Se rechaza cualquier origen del examen usado en entrenamiento y cualquier
familia holdout vista por gradientes. Pesos de humo de 1 época no son elegibles.

## 4. Bruno ejecuta el cuaderno de examen una sola vez

`evaluar_examen_colab.ipynb` clona código fijado por commit, monta Drive y recibe
rutas de PDF/sello/catálogo/pesos y sus SHA previamente conservados. La preparación
solo verifica hashes de bytes (no parsea PDF):

```sh
nice -n 15 python examen/preparar.py /ruta/d10-examen /ruta/examen-sellado.json --sello-sha256 SHA_PUBLICADO_POR_CLAUDE
```

Rechaza faltantes, sobrantes, duplicados de bytes, symlinks y archivos no PDF.
Si el sello está dentro de la carpeta, es el único auxiliar permitido.
El preparador no escribe archivos ni publica rutas. Ejecutarlo es opcional:
`medir_examen.py` lo llama internamente antes de abrir el primer PDF.

El evaluador carga los tres métodos, verifica los artefactos y deja en una
carpeta de control fija en Drive un marcador por conjunto de hashes. Cada PDF
se abre una sola vez; etiquetas RAWDICT y rasterización ruidosa viven en RAM.
Las tres filas usan exactamente los mismos glifos durante esa pasada. No se
guardan páginas, imágenes, texto, fuentes, ADN, recortes ni resultados individuales.
El JSON final solo contiene métricas agregadas, contadores, hashes y costes.
Los errores se imprimen como códigos constantes sin traceback o contenido.

La carpeta de control y la salida deben estar fuera de `d10-examen`. Reejecutar
el mismo conjunto se rechaza incluso con sello reordenado o salida nueva; un
fallo después de iniciar consume el intento y no publica métricas parciales.
No borrar el marcador ni cambiar la carpeta de control para volver a intentarlo.
Es prevención de repetición accidental, no un control contra un operador que
modifique deliberadamente código o Drive. Una concurrencia entre runtimes
Drive tampoco está certificada: ejecutar desde un solo cuaderno/runtime.

## 5. Interpretación y límites

Los nativos se rasterizan a 96 DPI con ruido fijado en el prerregistro. Esto es
REAL-rasterizado, no escáner físico. Se conocen el carácter y la segmentación
por A: no se evalúa OCR completo. Las familias elegibles del catálogo inicial
son Arvo y Fjalla One. Se cuentan las exclusiones y la cobertura; con menos de
dos familias evaluadas no se certifican umbrales. Familias externas al catálogo
no reciben una etiqueta inventada ni se suman como aciertos.

Un escaneado sin su nativo de referencia no tiene etiquetas reales de fuente,
tamaño o tinta. Con el sello acordado no hay emparejamientos: esas páginas se
cuentan como **NO EVALUABLE**, con métricas null. No fingir que OCR aporta esa
verdad. Cero glifos elegibles significa NO EVALUABLE, no 0% ni éxito.

Tres filas: vecino, solo sintético y afinado A, con top-1/top-5, errores pt y
ΔE2000, cobertura, GPU/tiempo/coste. Coste desconocido es null, nunca $0 supuesto.
Si el modelo no gana al vecino, se declara resultado negativo. Bruno puede
compartir únicamente JSON agregado; Codex no recibe contenido del examen.

NO VERIFICADO hasta ejecución de Bruno: Colab/Drive/GPU, calidad REAL y afinado A.
Las pruebas locales del nuevo protocolo usan exclusivamente PDFs artificiales.
El archivo `supercampana/FILOSOFIA-MAESTRO-ESTUDIANTE.md` no estaba en esta base;
se aplican la adenda y la aclaración explícita del usuario.

# D-10 · ADN tipográfico

Código aislado en `tools/adn_tipo/`, rama `studio/adn-tipografico`, base
`origin/studio/collage` en `e9fa572`. No modifica Studio ni el trabajo de DeepSeek.
El arreglo previo de D-2 vive por separado en `studio/indice-visual`, commit
`a241cd9`. Esquema de integración Forja 4: [ESQUEMA.md](ESQUEMA.md), versión 1.0.0.

## Instalación y extracción

Python 3.11 recomendado; comandos desde `tools/adn_tipo`:

```sh
nice -n 15 python3.11 -m venv .venv
nice -n 15 .venv/bin/python -m pip install -r requirements.txt
nice -n 15 .venv/bin/python nativo.py /ruta/propio.pdf --salida salidas/nativo --propio-sin-firmas-ni-sellos
```

A usa `get_text("rawdict")`, conserva caracteres/Unicode, fuente, tamaño, flags,
bbox y origen, extrae fuentes incrustadas y reconstruye carácter a carácter.
Es offline después de instalar dependencias. Escribe un ADN por página, fuentes
extraídas, PNG original/reconstruido, PDF reconstruido y diferencia por bloque.
No copia los streams de texto originales para simular una reconstrucción.
La comparación usa PyMuPDF; el fixture se revisó además con Poppler.
Los archivos fuente se leen sin modificar. Una salida existente se rechaza.

La declaración `--propio-sin-firmas-ni-sellos` es obligatoria. Se rechazan campos
de firma y anotaciones de sello; una firma rasterizada requiere revisión humana.
No ejecutar sobre documentos firmados o sellados de terceros.

Para imágenes, OCR español local y vecino como opción predeterminada:

```sh
nice -n 15 .venv/bin/python fuentes.py
nice -n 15 .venv/bin/python generar_sintetico.py --salida .cache/dataset --n 500
nice -n 15 .venv/bin/python descargar_ocr.py
nice -n 15 .venv/bin/python extraer.py /ruta/imagen.png --salida salidas/imagen --dpi 300 --galeria .cache/dataset --propio-sin-firmas-ni-sellos
nice -n 15 .venv/bin/python extraer.py /ruta/mixto.pdf --salida salidas/mixto --galeria .cache/dataset --propio-sin-firmas-ni-sellos
```

Instalar previamente el ejecutable Tesseract en el sistema. `descargar_ocr.py`
guarda únicamente español y licencia Apache-2.0 en `.cache/ocr`, fijados por
revisión y SHA; no cambia la instalación global. Se puede indicar `--tessdata`.
`extraer.py` envía páginas PDF sin texto al OCR y conserva su número de página
y hash del PDF. Las demás usan A. Las páginas con texto parcial oculto no se
clasifican automáticamente como escaneadas: revisar ese caso manualmente.
B produce un span por carácter, agrupa palabras OCR para marcar ortografía y
estima espaciado/línea base. El diccionario español solo marca: jamás corrige.
Para usar CNN, añadir `--pesos /ruta/pesos.pt`; el humo NO recomienda sustituir
el vecino por esos pesos. Sin DPI conocido no se infiere un tamaño físico.

## Datos y entrenamiento

`fuentes.lock.json`: 12 familias/14 archivos OFL de Google Fonts, revisión fija,
SHA de cada fuente y licencia. Los archivos y licencias descargados quedan en
caché o Drive. Tamaño, tinta, papel, inclinación, desenfoque, ruido y JPEG varían
con semilla fija. Etiqueta de tamaño refleja los píxeles enteros renderizados,
no un tamaño solicitado que Pillow redondeó. Colores de etiqueta son tinta
antes de escaneo; inferirlos tras compresión/ruido es precisamente la tarea.

Familias holdout iniciales: **Arvo (regular/italic) y Fjalla One**. Todos sus
estilos quedan fuera de gradientes. La identidad es SHA-256 de familia canónica
normalizada y el congelado registra también hashes de todos sus archivos.
No dividir por archivo/estilo. Generar otro dataset no sobrescribe el anterior.

El vecino usa glifos de 32×32 normalizados, con recuperación restringida al mismo
carácter. La CNN de 71.614 parámetros usa embedding, clasificación auxiliar
solo train y regresión de tamaño/Lab. Ambas recuperan contra el mismo catálogo
limpio de 12 familias; las familias holdout están en el catálogo pero nunca
entrenan la CNN. La evaluación tipográfica recibe el carácter verdadero para
separar error de OCR y error de estilo. No es un benchmark OCR de extremo a extremo.

[entrenar_colab.ipynb](entrenar_colab.ipynb) clona esta rama privada mediante
un secreto `GITHUB_TOKEN` de solo lectura, genera datos, mide vecino, entrena
20 épocas GPU, guarda en Drive pesos/métricas/commit/dependencias y muestra SHA
de pesos y holdout. Opcionalmente afina 5 épocas con `NATIVO_TRAIN`, creado con
etiquetas A y sin fuentes ni documentos del examen. Añadir tarifa USD/h de
Bruno o conservar coste desconocido. El notebook no abre el examen real.
Cada entrenamiento guarda el último checkpoint; no selecciona por holdout.

```sh
# Humo local: UNA sola época CPU, ya ejecutada. No ejecutar entrenamiento completo local.
nice -n 15 .venv/bin/python entrenar.py .cache/dataset --salida .cache/modelo --epocas 1 --dispositivo cpu
# SHA debe ser el congelado conservado antes de entrenar, no uno nuevo calculado tras alterar datos.
nice -n 15 .venv/bin/python medir.py .cache/dataset --holdout-sha256 SHA_CONGELADO --salida salidas/vecino.json
nice -n 15 .venv/bin/python medir.py .cache/dataset --holdout-sha256 SHA_CONGELADO --pesos .cache/modelo/pesos.pt --salida salidas/cnn.json
nice -n 15 .venv/bin/python comparar.py salidas/vecino.json salidas/cnn.json --salida salidas/comparacion.json
```

## Evidencia local — 26-10-2026

Prerregistro comprometido en Git (`0b0bccd`) ANTES de entrenar. 1.056 muestras
train y 288 holdout (2 familias, 12 candidatas). Una época CPU, semilla 2610,
nice 15. Resultados preservados en [resultados/](resultados/):

| Método | Top-1 | Top-5 | MAE tamaño pt | ΔE2000 medio | GPU | Entrenar / inferir | Coste |
|---|---:|---:|---:|---:|---|---|---|
| Vecino de píxeles | 0,7743 | 0,9757 | 1,3471 | 7,0172 | Ninguna | 0 / 0,414 s | entrenamiento $0; inferencia no medida |
| CNN solo sintético, 1 época | 0,0000 | 0,2153 | 4,6345 | 24,8689 | Ninguna | 3,118 / 0,753 s | no medido |
| Misma CNN afinada A | NO VERIFICADO | — | — | — | pendiente Colab | pendiente | desconocido |

**El modelo no gana al vecino en este humo.** Tampoco el vecino cumple todos
los umbrales del prerregistro. No cambiar umbrales ni repetir épocas localmente
para esconderlo. Las cifras no son resultado del examen real.

- Holdout: `e906ab30ce3e966a4e3baf1409cf91d25b7e54e4ff3880eb20911a70f7909965`.
- Pesos de humo: `215d13ff35e1803b0d8237d1500cb360a5dd3c9ace2793a5f87a28e9354c45b6` (solo caché, no Git).
- A: dos bloques del fixture propio Lato incrustada + Helvetica, diferencia de
  píxeles **0** a 144 DPI; no extrapolar a PDFs arbitrarios.
- OCR del fixture: «Árbol propio / Hola mundo», 20 caracteres, sin abstenciones
  de catálogo. Verifica recorrido y contrato, no precisión tipográfica.
- 13 pruebas: extracción, fuente incrustada/rotación, sellos/firmas, contrato,
  familia, semilla, Lab, ortografía, hashes, fugas, maestro train y PDF mixto.

D-2: nueve pruebas pasan. Viejo ensayo de 18 consultas **0,9444 / 1,0**;
repetición completa igual; nuevo holdout por origen **0,6667 / 1,0**, solo
3 consultas de un origen con galería de seis referentes. Muestras diferentes;
no atribuir la diferencia a un cambio del modelo. Evidencia en su propia rama.

## Examen real y límites pendientes

[EXAMEN-CLAUDE.md](EXAMEN-CLAUDE.md) y `preparar_examen.py` preparan la alternativa
permitida de PDFs propios rasterizados con ruido. Claude selecciona por origen,
separa familias, ejecuta A, sella con SHA y conserva el examen sin mostrárnoslo.
El preparador se probó solo con un PDF artificial para **train**, no con el examen.
No se recibieron PDFs propios de Bruno ni sello de Claude; el examen real aún
no está construido. Reportar por separado vecino, CNN sintética y afinada A.

**NO VERIFICADO:** Colab/GPU/Drive reales, afinado A, examen real de Bruno,
impresión/escáner físico, benchmark OCR, calibración de confianza, ICC/tintas
planas, escritura encima imperceptible, texto en curvas, ligaduras complejas,
matrices de texto arbitrarias, verticales/clipping y documentos grandes.
A no puede prometer peso CSS exacto a partir de flags; B estima línea base y
hueco geométrico, con tolerancias aún no medidas. B se abstiene para glifos
fuera de catálogo o demasiado grandes para la ventana. No confundir ausencia
de error en dos bloques con reconstrucción universal.

Las pruebas requieren fuentes en caché (`fuentes.py`) pero no GPU ni pesos:

```sh
nice -n 15 .venv/bin/python -m unittest discover -s . -p 'test_*.py' -v
```

Fuentes técnicas: [RAWDICT](https://pymupdf.readthedocs.io/en/latest/textpage.html),
[extracción y reconstrucción](https://pymupdf.readthedocs.io/en/latest/faq/index.html),
[repositorio Google Fonts](https://github.com/google/fonts),
[estructura y licencias GF](https://googlefonts.github.io/gf-guide/googlefonts.html).
PyMuPDF tiene licencia AGPL/comercial; no confundirla con OFL de las fuentes.

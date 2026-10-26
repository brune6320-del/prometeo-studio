# D-10 · Prerregistro v2 · 26-10-2026

Los umbrales v1 se registraron antes de entrenar (commit 0b0bccd). Esta v2
fija el protocolo REAL antes del sellado; no cambia umbrales ni entrenamiento.
La v1 se conserva íntegra en examen/PRERREGISTRO-v1.md. Semilla 2610; no ajustar umbrales por el examen.
Unidad de separación: familia canónica (nombre normalizado), SHA-256 de esa
identidad, no de cada archivo/estilo. El manifiesto de familias incluye además
los hashes de TODOS los archivos de cada familia. Hash salado, 25% holdout;
se exige al menos dos familias de examen y seis candidatas totales. Cualquier
estilo o versión de la misma familia debe usar la misma identidad canónica.
El holdout se congela por archivo inmutable y SHA-256 antes del entrenamiento.
Alterarlo exige otro experimento, nunca sobrescribirlo.

## Hipótesis y protocolo

Una cabeza cerrada no predice clases nunca vistas: usamos CNN pequeña con
embedding y recuperación de catálogo. La clasificación auxiliar se entrena
solo con familias train. Catálogo limpio de glifos de TODAS las familias,
con tamaño conocido, disponible por igual al vecino de píxeles y a la CNN.
No contiene recortes del examen ni se usa para gradientes. Cada consulta se
compara solo con el mismo carácter (OCR en producción; etiqueta conocida en
benchmark tipográfico). Top-k se calcula por familias distintas, no por estilos.
Reportar número de candidatas; top-5 no es informativo con <=5 candidatas.

Filas separadas: (1) vecino más cercano sin entrenamiento; (2) CNN solo
sintético; (3) mismos pesos afinados con etiquetas nativas A de documentos de
entrenamiento. Afinado excluye familias y documentos del examen. Exactamente
una época CPU local para humo; no sirve como certificación. Colab: 20 épocas
sintéticas y 5 de afinado, Adam 1e-3 / 1e-4, batch 64, semilla 2610.
No seleccionar checkpoint ni hiperparámetros por el holdout; última época.

Criterio de éxito, independiente para sintético y REAL: top-1 >=0,80 y mejora
absoluta >=0,05 frente al vecino; top-5 >=0,95; MAE tamaño <=1,0 pt;
media ΔE2000 <=3,0 (Lab D65/2°, sRGB). Reportar también n, error mediano,
p95, cobertura, hashes, dispositivo/GPU, segundos y coste USD (null si se
desconoce, nunca asumir gratis). Inferencia tipográfica requiere DPI conocido;
sin escala física el tamaño en puntos no es identificable.

## Maestro natural y examen ciego

A aporta Unicode, fuentes declaradas, tamaños, color sRGB interpretado y
posiciones. No garantiza peso CSS exacto, perfiles ICC, ligaduras, texto
convertido en curvas ni apariencia idéntica. No presentar estimaciones como
verdad exacta. Campos desconocidos son null y llevan advertencia.

Bruno aporta 10–20 PDFs propios SIN firmas ni sellos de terceros, en Google
Drive/d10-examen. Claude, hilo del plan maestro, publica SOLO examen-sellado.json
con SHA-256, número de páginas y tipo nativo|escaneado por PDF; sin nombres ni
contenido. Este agente solo recibe ese JSON, nunca abre la carpeta ni los PDFs.
El SHA-256 de este PRERREGISTRO se publica antes de que exista ese sello.

## Ejecución REAL única en Colab de Bruno

El notebook de examen es distinto del entrenamiento. Se ejecuta después de
congelar ambos pesos y el catálogo; verifica SHA del sello, prerregistro,
catálogo, pesos y procedencia de ambas etapas ANTES de analizar ningún PDF.
examen/preparar.py verifica una correspondencia biyectiva: falta, sobra,
duplicado por bytes, symlink o archivo no PDF => rechazo, sin revelar nombres.
El sello puede estar fuera de la carpeta o dentro como único archivo auxiliar.
El conjunto de hashes identifica el intento, independientemente del orden del
JSON. Un marcador persistente en Drive impide reejecución accidental del mismo
conjunto, incluso después de fallo. No hay --force ni reintento automático.
No es protección frente a un operador que borre deliberadamente el control.

medir_examen.py abre cada PDF una sola vez con PyMuPDF y procesa sus páginas en
memoria; no llama a nativo.extraer (que guarda artefactos). No guarda texto,
recortes, ADN, fuentes extraídas, páginas, trazas ni predicciones individuales,
ni siquiera en temporales. Solo persiste métricas agregadas y metadatos de
integridad/control sin rutas, nombres de documentos o contenido. Los avisos de
MuPDF y las excepciones se sanitizan antes de llegar a la salida del notebook.
No ejecuta entrenamiento ni OCR que necesite temporales con páginas.

Tipo sellado: nativo si existe al menos una página con texto extraíble no
vacío; escaneado si no hay ninguna. Un PDF mixto se sella nativo, pero sus
páginas sin texto se cuentan como sin referencia. Número de páginas y tipo se
comprueban contra el sello en esa única apertura; discrepancia invalida la
corrida entera. Los PDFs con firmas, sellos o contraseña se rechazan.

Para nativos, RAWDICT A aporta etiquetas en memoria; la consulta se rasteriza a
96 DPI con ruido fijo: desenfoque 0,45 px, ruido normal sigma 2, JPEG calidad 80,
semilla 2610 por hash de origen y página. Es REAL-rasterizado, NO escáner físico.
Se evalúan glifos por carácter A conocido y alineación A: es tipografía
condicionada a segmentación/transcripción correcta, no OCR extremo a extremo.
Para escaneados sin nativo emparejado no existe verdad de fuente/tamaño/tinta:
NO EVALUABLE, métricas null y páginas sin referencia contadas. No inventar
etiquetas usando OCR o el propio alumno. Este sello no incluye emparejamientos.

El catálogo y alias de nombres públicos de fuentes se congelan ANTES del
sellado en examen/catalogo_preexamen.json. No adaptar alias al examen.
Métrica principal: familias holdout del protocolo v1 que no entrenaron ninguna
etapa. Si una familia holdout aparece en la procedencia de los pesos, rechazo.
Se cuentan aparte caracteres de familias train, desconocidas, glifos fuera de
catálogo, texto no horizontal y cajas fuera de ventana. No ampliar catálogo ni
reinterpretar nombres después de abrir el examen. Cero glifos elegibles produce
NO EVALUABLE (no 0% ni éxito). Las métricas siempre muestran denominadores,
cobertura respecto a todos los caracteres nativos no blancos y exclusiones.
Top-1/top-5 incluyen abstenciones como fallos; errores pt/ΔE se calculan solo
con predicción válida, con su propia cobertura. Sin al menos dos familias de
holdout evaluadas no se certifican los umbrales. Ningún resultado del subconjunto
se presenta como cobertura de todo el examen.

Las tres filas se calculan durante la misma pasada: vecino, CNN solo sintético,
y la MISMA CNN afinada A. Afinado debe declarar el SHA de los pesos sintéticos
de origen y conservar la unión de familias/documentos vistos. Ningún SHA de
PDF de examen puede pertenecer a entrenamiento. Orígenes recomprimidos o
renombrados con bytes distintos requieren control humano antes del sellado.
Cada fila incluye GPU, tiempo de entrenamiento e inferencia y coste conocido
o null. Los errores globales incluyen media/mediana/p95; no publicar detalles
por carácter, documento, fuente ni página.

Si el modelo no supera al vecino en REAL se informa como resultado negativo.
Sin PDF nativo evaluable, sin sellado o sin ejecución de Bruno: REAL = NO
VERIFICADO/NO EVALUABLE según corresponda. No sustituirlo por un fixture generado
por el desarrollador. No volver a entrenar o seleccionar pesos con este resultado.

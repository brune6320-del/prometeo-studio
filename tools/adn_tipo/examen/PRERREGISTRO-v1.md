# D-10 · Prerregistro v1 · 26-10-2026

Se registra antes de entrenar. Semilla 2610; no ajustar umbrales por el examen.
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

Bruno aporta PDFs propios SIN firmas ni sellos de terceros. Claude ejecuta
preparar_examen.py, verifica autoría, separa documentos por SHA-256 de origen
y familias; sella manifiesto + imágenes + etiquetas con SHA-256. Este agente
NO abre el examen real ni lo ejecuta. Se permite rasterización con ruido
(identificarla separadamente de escáner físico). El entrenamiento nativo usa
otra carpeta y sus orígenes no pueden intersectar el examen. Claude ejecuta
la evaluación final y devuelve solo métricas agregadas y hashes.

Si el modelo no supera al vecino en REAL se informa como resultado negativo.
Sin PDFs propios, sin sellado o sin ejecución de Claude: REAL = NO VERIFICADO.
No sustituirlo por un PDF generado por el desarrollador ni por sintético.

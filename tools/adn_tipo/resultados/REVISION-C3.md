# Corrección D-10 · 26-10-2026

Base: dc5ddd5b768a3e745cbaf903efbd4ba36aac5805. Solo tools/adn_tipo.
Entrada comprobada: tensor() normaliza a 64×64, dos max pools producen 16×16.
AvgPool2d(4,4) sustituye AdaptiveAvgPool2d((4,4)); pesos compatibles sin migrar.
Se rechazan tamaños distintos, pues fuera de ese contrato no son equivalentes.
La dependencia de color en cargar_imagen se importa al usarla: las pruebas
aisladas del modelo no necesitan instalar OCR ni scikit-image.

Pruebas: 4 CPU pasan y 1 CUDA omitida por hardware no disponible. Igualdad
exacta CPU de salidas y gradientes float32/float64, salidas de red completa,
carga estricta de state_dict anterior, rechazo de dimensiones y un paso de
backward/optimizador bajo use_deterministic_algorithms(True). Datos aleatorios
de prueba, sin corpus ni corrida de entrenamiento. Log adjunto.

La suite histórica test_adn/test_examen no pudo importarse en este entorno:
ModuleNotFoundError: skimage. También falta pyspellchecker; no se instalaron
dependencias sin autorización. No es una regresión atribuida al parche. Las
30 pruebas comunicadas por Claude no se presentan como repetidas aquí.
test_examen.setUp crea .cache antes del directorio temporal, como solicitó
la revisión. Solo contiene fixtures artificiales; d10-examen no se abrió.

PRERREGISTRO.md v2 intacto: SHA-256
16b5a933c466c04eaa9a28e06dcb62ceb4be2c66b73e1391b1a16d546637d776.
CUDA/T4, reproducibilidad entre GPU y suite completa: NO VERIFICADO.
GPU consumida: 0. No se descargaron pesos ni se ejecutó el examen.

## Continuación tras autorización de Bruno · 26-10-2026

La limitación anterior de dependencias quedó resuelta en el venv C3 aislado.
Se instalaron scikit-image 0.24.0 (Python 3.9) y pyspellchecker 0.8.3 con sus
cuatro dependencias faltantes; se conservaron torch 2.8.0 y el entorno previo.
Inventario completo en pip-freeze-c3.txt; variantes fijadas en
requirements-c3-py39.txt. Ver V3-EJECUCION.md para rutas y procedimiento.
Fuentes de fixtures descargadas mediante fuentes.py, con revisión y doble
SHA fuente/licencia de fuentes.lock.json; siguen ignoradas, nunca en Git.

Se detectó importación anticipada de pytesseract incluso para camino A:
ahora se carga solo al usar OCR B; si falta, B informa OCR no ejecutado.
El test de PDF mixto mantiene su mock de OCR original: no demuestra OCR real.
Se añaden origen/metodo explícitos para distinguir vecino de CNN.

Suite final: 43 pruebas, 42 pasan y 1 CUDA omitida. Las 30 históricas pasan.
El humo v3 usa una época CPU en un fixture artificial de diez imágenes;
no abre holdout ni examen y no acredita mejora. Sus pesos temporales se
descartan. Se prueba separación por origen/carácter, duplicados, early stopping
y persistencia/carga del checkpoint. CUDA, consumo real Colab, desarrollo con
padre v2, placebo de campaña, comparación real y examen: NO VERIFICADO.
V2 y v3 conservan los hashes publicados. No se alteran resultados negativos.

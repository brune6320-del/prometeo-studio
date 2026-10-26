# v3 · laboratorio separado de v2

El prerregistro v3 se publicó en 168c2ec antes del humo de implementación.
PRERREGISTRO.md v2 y sus notebooks no cambian. Usar entrenar_v3.py de manera
explícita; entrenar.py sigue siendo v2. No abrir el examen de Bruno.

Implementado: separación por fuente/carácter sintético o documento origen
nativo, rechazo de fuga de imágenes, pérdidas separadas, early stopping
(25 épocas, delta 1e-4, máximo 300/100), control permutado, generaciones
inmutables con predicciones, etiquetas y hashes. Cada época guarda pesos
antes de avanzar; pesos.pt es una copia del mejor checkpoint interno.
El checkpoint permite recuperar esa generación; no hay reanudación automática
bit-idéntica del optimizador/RNG tras una interrupción. Ante fallo conservarlo
y usar una salida nueva. No sobreescribir ni continuar silenciosamente.

## Antes de una GPU, Bruno

1. Ejecutar desarrollo_v3.py sobre train autorizado, padre v2 completo y
   catálogo compartido. No usa holdout. El padre pudo ver ese train: desarrollo
   no mide generalización ni constituye prueba de mejora.
2. Revisar los archivos padre.json y vecino.json. Si hay techo/suelo, detener
   y rediseñar solo desarrollo. Completar revisado_por y techo_o_suelo en
   desarrollo.json; sin ese paso la GPU se rechaza.
3. Preparar presupuesto.json: unidades_disponibles (saldo real <=20 del total
   compartido, restar lo ya gastado), unidades_por_hora, segundos_maximos y
   saldo_verificado_por. Todos positivos y límite temporal compatible con saldo.
   Bruno debe vigilar además el contador real de Colab; la tarifa por tiempo
   es estimación, no medición de consumo. Falta de presupuesto bloquea la corrida.
4. Montar Drive y usar una carpeta NUEVA bajo /content/drive. Verificar que
   no exista otro trabajo GPU, incluidos procesos fuera de este ejecutor.
   El bloqueo local solo coordina otros procesos entrenar_v3 de este host.
5. Ejecutar alumno y control en serie, en carpetas distintas; reservar coste
   para ambos. El control usa --control. Sin control, no hay conclusión causal.

```sh
nice -n 15 python tools/adn_tipo/desarrollo_v3.py /ruta/train \
  --padre /ruta/v2/pesos.pt --galeria /ruta/catalogo --salida /ruta/desarrollo-v3
nice -n 15 python tools/adn_tipo/entrenar_v3.py /ruta/train \
  --device cuda --salida /content/drive/MyDrive/Prometeo/ADN/v3-generacion-nueva \
  --presupuesto /ruta/presupuesto.json --desarrollo /ruta/desarrollo-v3/desarrollo.json
```

CPU solo permite --humo (una época, sin selección de hiperparámetros ni
acreditación de aprendizaje). El test usa fixtures propios sin holdout.json,
demuestra artefactos/contratos y descarta sus pesos al terminar. No cuenta como
entrenamiento de campaña ni justifica promover. Un resultado GPU es TESTED,
nunca VERIFIED por este constructor. El examen real sigue bloqueado hasta
congelar candidato y revisar el contrato del runner de examen con el custodio.

## Entorno local de esta campaña

Venv autorizado con --system-site-packages:
/Users/gladys/Documents/Codex/2026-10-26/files-pasted-by-the-user-campa/work/.venv-c3

Un .pth dentro del venv añade en modo lectura los paquetes del entorno previo
/Users/gladys/Projects/prometeo-indice/tools/indice/.venv/lib/python3.9/site-packages.
Python venv no hereda automáticamente otro venv; por eso esta referencia es
explícita. PyTorch 2.8.0 se carga de esa ruta y no se reinstaló ni actualizó.
Pip freeze previo/posterior de ese entorno es idéntico. Los seis paquetes
nuevos solo están en .venv-c3. requirements-c3-py39.txt fija sus versiones;
requirements.txt conserva Python 3.11/scikit-image 0.25.2 recomendado.
pip-freeze-c3.txt es evidencia de inventario, no un lock portable: contiene
paquetes heredados del sistema Apple con URLs locales no instalables fuera
de esta máquina. No intentar pip install -r sobre ese inventario.

Camino A nativo ya no importa pytesseract al cargar el módulo. Camino B real
sigue requiriendo pytesseract, Tesseract español, catálogo y DPI; no se ejecutó
ni se instaló OCR en esta campaña. Método y origen quedan anotados cuando se usa.

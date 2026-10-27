# D-10: comprobación adicional sin entrenar · 26-oct-2026

La rama `studio/adn-tipografico` ya había avanzado desde la base indicada
`dc5ddd5` hasta `d8bffe5` al iniciar esta revisión. Se conserva ese trabajo:
pooling fijo en `64f20f6`, prerregistro v3 en `168c2ec` y ejecutor separado
en `d8bffe5`. No se ha reescrito ninguno de esos commits ni los prerregistros.
El humo que describe la revisión local anterior pertenece a aquella ejecución;
esta revisión no lo repite.

**Pooling.** `tensor()` fija RGB 64×64; los dos MaxPool producen 16×16.
`AvgPool2d(4, stride=4)` y AdaptiveAvgPool2d(4×4) coinciden exactamente en
salida y gradiente CPU, tanto float32 como float64. También se comprueban
compatibilidad del state_dict anterior y salida de la red completa. La prueba
de backward CPU usa determinismo estricto y un único paso unitario de SGD
con tensores aleatorios, sin corpus ni artefactos de pesos. CUDA no está
disponible: su prueba queda omitida, no aprobada. No se usa warn_only.

**Color: revisión de escala y peso.** La cabeza original ya era lineal y
conservaba valores negativos de a/b. No se identificó una sigmoid que los
recortara. La normalización es tamaño/24 y Lab/[100,128,128], y la inferencia
deshace esas escalas. Las pruebas nuevas comprueban signos y unidades de
inferencia, MAE por canal y ΔE2000 calculado en Lab físico durante validación.

Sean S el error cuadrático del tamaño normalizado y C la media de los tres
errores cuadráticos de color normalizado. La regresión v2 es S/4 + 3C/4;
v3 fija S + 4C, además de la misma CE. Respecto a CE, aumenta tamaño ×4 y
color ×16/3. El peso relativo color/tamaño aumenta de 3 a 4 (×4/3), no ×4.
El test verifica la expresión v3 y sus gradientes con números independientes.
MSE normalizada no equivale a ΔE2000: hay ponderación por escala y la métrica
de color no es euclídea. Esa discrepancia es una hipótesis para el mal color
observado; no demuestra su causa ni que v3 mejore. No se ajustaron pesos de
la loss usando holdout ni se modificó el protocolo ya comprometido.

**Selección.** Se repitieron únicamente las pruebas puras de partición por
fuente/carácter, agrupación por documento, ausencia de imágenes duplicadas
entre particiones, rechazo de clases faltantes y early stopping. El protocolo
existente fija validación interna de familias train, 300 épocas máximas
sintéticas, paciencia 25 y delta 1e-4. El vecino y umbrales de v2 se conservan.

**Resultado local:** 14 pruebas consideradas: 13 aprobadas y 1 CUDA omitida;
0 fallos. Log: `pruebas-nube-sin-entrenar.txt`. Python 3.12.14,
torch 2.8.0+cpu, numpy 1.26.4, Pillow 11.3.0 y scikit-image 0.25.2 en un
venv aislado de la nube. Ninguna época, ni siquiera de humo, se ejecutó aquí.
No se abrió el holdout, Drive, pesos de campaña ni el examen real.

Se añade `.github/workflows/d10-contratos.yml` con las mismas dependencias y
selección explícita de pruebas para CPU. El comando del workflow se probó
localmente; no se atribuye una ejecución de GitHub Actions sin observarla.
No usar discovery de toda la suite para este encargo: incluiría el test de
humo que invoca entrenamiento. En un entorno CUDA con torch compatible,
`test_modelo` ejecutará también el caso CUDA; aquí no se verificó T4.

```sh
cd tools/adn_tipo
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 CUBLAS_WORKSPACE_CONFIG=:4096:8 \
python -m unittest -v test_modelo test_color_v3 \
  test_v3.V3Test.test_grupo_fuente_caracter_y_orden_independiente \
  test_v3.V3Test.test_documento_completo_no_cruza_particion \
  test_v3.V3Test.test_no_reubica_grupos_si_falta_clase \
  test_v3.V3Test.test_no_acepta_copia_cruzada \
  test_v3.V3Test.test_parada_empate_y_no_finito
```

Hashes comprobados antes y después:

- v2: `16b5a933c466c04eaa9a28e06dcb62ceb4be2c66b73e1391b1a16d546637d776`.
- v3: `13d904c646f392b4b219ca45faec14c0a8e7c9707d387301d225a9bc4f4e9daa`.

El examen real de Bruno sigue cerrado. El resultado negativo comunicado de
v2 no se reclasifica. La mejora empírica del color y el cumplimiento de los
umbrales v3 siguen sin medirse en esta revisión.

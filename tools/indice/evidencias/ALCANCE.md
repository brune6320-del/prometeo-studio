# Alcance comprobado — D-2 — 25/10/2026

Trabajo individual en `/Users/gladys/Projects/prometeo-indice`, rama `studio/indice-visual`, base `d6d35583ea176daafee1a9be101b8edfb934d0ca`. Se reutilizaron los seis commits existentes y se completaron PDF y recortador. Solo se modificó `tools/indice/`; no se modificó `studio/collage`.

Las ocho pruebas de `pruebas.txt` usan exclusivamente datos sintéticos. `integral_cpu.json` procede de ejecutar `verificar_sintetico.py` con el SigLIP fijado, CPU, nice 15 y lote 1; comprueba SHA-256 de pesos descargados, imágenes, páginas PDF, video, recortes, búsqueda, duplicados, grupos y exportación. No se entrenó ningún modelo.

`primer_ensayo_fallo_recorte.txt` conserva el primer fallo: se había exigido que un recorte quedase primero y el original quedó segundo. Se retiró únicamente esa exigencia de calidad de la prueba funcional; se conserva el rango 2 y el mismo conjunto sintético/semilla. Recall@1 0,9444 y recall@5 1,0. No se ajustaron pesos ni umbrales ni se sustituyó la consulta. El resultado no acredita calidad sobre referentes reales.

Licencia declarada para SigLIP/pesos: Apache-2.0, ficha oficial guardada con revisión en `licencia_modelo.json`. La revisión histórica de pesos carece de README. Se verificó el hash publicado de `model.safetensors`: `2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8`. Transformers 4.57.6: Apache-2.0. PyMuPDF 1.26.5: AGPL-3.0 o comercial (https://pypi.org/project/PyMuPDF/1.26.5/).

No existen `tools/recortador/` ni `gustos.json` reales en esta base/carpeta. Integración probada con piezas y etiquetas sintéticas, no con IDs reales de tarjetas Studio. No se inventan vínculos; se reportan los no vinculados. Holdout persistido por SHA-256 de fuente y política fija; diferentes recortes en archivos distintos aún pueden contaminar una futura evaluación y requieren revisión previa al entrenamiento.

NO VERIFICADO: MPS, otra Mac, escala grande, calidad con referentes reales, integración con salida real del recortador y correspondencias reales de gustos. No se ejecutó `medir.py` contra datos reales: su CLI solo crea pares sintéticos. No se suben imágenes, pesos ni cachés a Git. El ZIP incluye fuentes, evidencias y parches de recuperación; no incluye datos reales ni credenciales.

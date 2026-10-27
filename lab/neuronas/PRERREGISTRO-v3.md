# PRERREGISTRO v3 · FASE 5c (N-1 · Capa media `features.5` + Prueba ciega humana)

- **Fecha de sello (antes de mirar activaciones de `features.5`):** `2026-10-27`
- **Archivo JSON sellado:** `lab/neuronas/prerregistro_v3.json` (`sha256 = 230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8`)
- **Prerregistros anteriores preservados intactos:**
  - `lab/neuronas/prerregistro.json` (`v1`, `sha256 = a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388`)
  - `lab/neuronas/prerregistro_v2.json` (`v2`, `sha256 = 729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555`)

## 1. Hipótesis y diseño de la Parte 1 (Capa media `features.5`)

1. **Capa estudiada:** `features.5` (etapa 3 de `ConvNeXt-tiny`, `384` canales convolucionales, mapa espacial $14 \times 14$ sobre entrada $224 \times 224$).
2. **Muestreo de neuronas:** `200` neuronas elegidas al azar sin reemplazo entre los `384` canales usando la semilla fija `SEED = 2610`.
3. **Corpus y partición:** el mismo corpus de `630` imágenes CC0 (`lab/neuronas/corpus_cc0_630.json`, `sha256 = f0c3483f...`) y la misma partición (`SEED = 2610`): `441` imágenes en `train` (70 %) para descubrimiento y redacción de etiquetas libres, y `189` imágenes en `validacion` (30 %) ciegas que no se miran al etiquetar.
4. **Etiquetas libres centradas en verbos visuales de diseño:** se redactan en español libre observando solo los mosaicos de `train` (sin mezclar metadatos de catálogo del museo como «escultura» o «grabado», sino propiedades visuales y compositivas: contraste, claroscuro, temperatura cromática, saturación, textura de trazo, orientación vertical/horizontal, simetría, aislamiento central vs sangrado). Si en `train` no se observa un patrón visual claro, se escribe **`«no lo sé»`**.
5. **Mismas pruebas no tautológicas y mismos umbrales que en 5b:**
   - **a) Apagado con control justo (`confirmada_a`):** sobre las `top-9` imágenes de `train` de la neurona $X$, se pone a `0` el canal $X$ en `features.5`, se propaga por `features.6 -> features.7 -> avgpool -> classifier` y se mide el cambio medio $L_2$ en los 1000 logits del clasificador. Se compara frente a apagar cada una de 5 neuronas control $Y_1\dots Y_5$ (semilla `2610 + X`) elegidas entre los 25 canales de `features.5` con activación media absoluta más parecida en `train`. Pasa si $E(X) \ge 2{,}0 \times E(Y_m)$ en al menos **4 de 5** sorteos.
   - **b) Predicción ciega en validación (`confirmada_b`):** usando únicamente el texto de la etiqueta escrita, se puntúa de `0` a `3` cada una de las `189` imágenes de validación. Pasa si `etiqueta != "no lo sé"` y el $\text{ROC AUC}$ frente a la activación real de la neurona $X$ en validación (top 20 % = 38 positivas) es $\ge 0{,}70$.
   - **Criterio de legibilidad (`legible = true`):** `confirmada_a and confirmada_b and etiqueta != "no lo sé"`.
6. **Hipótesis registrada:** *«en `features.5` el % legible es mayor que el 13 % de `features.7`»*. Si no lo es, se reporta íntegramente el negativo.

## 2. Diseño de la Parte 2 (Prueba ciega humana para Bruno · 20 pares)

1. Entre las neuronas legibles de `features.7` (y, si las hay, de `features.5`), se eligen **20 neuronas al azar** con semilla `SEED = 2610`.
2. Para cada neurona se construye un par visual sin cabeceras ni pistas textuales: el mosaico `top-9` real de la neurona y un mosaico señuelo (`top-9` de otra neurona elegida al azar con `SEED = 2610`), asignando al azar la posición **izquierda / derecha**.
3. Una única página `.html` local y sin internet muestra la etiqueta de cada par y los dos mosaicos, permite marcar «izquierda» o «derecha» y guarda las respuestas en un `.json` junto a la página. La clave secreta se guarda en un archivo separado que Bruno no abre.
4. **Umbral de validación humana:** $\ge 15 / 20$ aciertos ($p = 0{,}02069 < 0{,}05$ frente al azar $p = 0{,}5$).

# Prerregistro v2 · FASE 5b: Atlas con Prueba de Verdad (N-1 v2)

- **Fecha de sellado (antes de mirar activaciones en el corpus de 630 imágenes):** `2026-10-26`
- **Rama:** `studio/neuronas-atlas`
- **SHA-256 de `lab/neuronas/prerregistro_v2.json`:** `729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555`
- **SHA-256 de `lab/neuronas/corpus_cc0_630.json`:** `f0c3483fafa8c04be6492ff62190071c8f6278beb8dec78b05110a6cabb5875f`
- **Prerregistro v1 intacto:** `lab/neuronas/prerregistro.json` (`a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388`).

## 1. Corpus ampliado CC0 (`630` imágenes, semilla `2610`)

- **Total de imágenes CC0 verificadas:** `630` (`565` del Cleveland Museum of Art Open Access API, `59` de The Metropolitan Museum of Art Open Access y `6` referentes adicionales de D-3).
- **Mezcla por categoría:** `168` pinturas, `154` grabados, `130` objetos (cerámica/escultura/bronce), `120` fotografías y `58` carteles/obra gráfica.
- **Partición sellada con semilla `2610`:**
  - **Descubrimiento (`train`, 70 %):** `441` imágenes (usadas para extraer los mosaicos `top-9` del polo + y del polo − y escribir las etiquetas).
  - **Validación ciega (`validacion`, 30 %):** `189` imágenes (no se miran al etiquetar; reservadas exclusivamente para la prueba b).

## 2. Dos pruebas no tautológicas prerregistradas

1. **Prueba a) Apagado con control justo (`confirmada_a`):**
   - Sobre las `top-9` imágenes de `train` de la neurona $X$, se mide el cambio medio $L_2$ en el vector de 1000 logits del clasificador al apagar $X$:
     $$E(X \mid \text{Top9}_{\text{train}}(X)) = \frac{1}{9} \sum_{i \in \text{Top9}_{\text{train}}(X)} \| z_i - z_i^{(-X)} \|_2$$
   - Se compara contra apagar cada una de **5 neuronas control** $Y_1, \dots, Y_5$ sorteadas al azar (semilla `2610 + X`) entre las 25 neuronas $Y \neq X$ con activación media absoluta en `train` más parecida a la de $X$.
   - **Confirmada en (a)** sí y solo sí $E(X \mid \text{Top9}_{\text{train}}(X)) \ge 2,0 \times E(Y_m \mid \text{Top9}_{\text{train}}(X))$ en **al menos 4 de los 5** sorteos de control.
2. **Prueba b) Predicción ciega en validación (`confirmada_b`):**
   - Solo a partir de la etiqueta escrita (sin mirar la activación de `ConvNeXt-tiny` en validación), se puntúa de `0` a `3` cuánto encaja cada una de las `189` imágenes de validación con la descripción de la etiqueta.
   - Si en el mosaico de `train` no se observa un patrón claro, la etiqueta se escribe como `«no lo sé»` y cuenta automáticamente como no legible (`confirmada_b = false`).
   - **Confirmada en (b)** sí y solo sí `etiqueta != "no lo sé"` y el **ROC AUC** de la puntuación `0..3` frente a la activación real en validación (positivos = top 20 % de activación en las 189 imágenes de validación) es **$\ge 0,70$**.
3. **Criterio de neurona «legible»:**
   $$\text{legible}(X) \iff \text{confirmada\_a}(X) \;\wedge\; \text{confirmada\_b}(X) \;\wedge\; (\text{etiqueta} \neq \text{«no lo sé»})$$

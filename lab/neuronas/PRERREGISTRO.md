# Prerregistro · FASE 5: Atlas Piloto de Neuronas (N-1)

- **Fecha de sellado (antes de descargar pesos o mirar activaciones):** `2026-10-26`
- **Rama:** `studio/neuronas-atlas`
- **SHA-256 de `lab/neuronas/prerregistro.json`:** `a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388`
- **Modalidad del corpus:** **Piloto reducido** (`22` piezas del corpus D-3 en `~/Desktop/REFERENTES/corpus-editorial/muestras/`, ya que las 442 fotos de Bruno aún no están en carpeta local; en Git solo se guardan los hashes SHA-256).

## 1. Comprobación de licencia del modelo y pesos (Paso 3)

- **Librería y receta de entrenamiento (`pytorch/vision`):** Licencia **`BSD-3-Clause`** ([pytorch/vision LICENSE](https://github.com/pytorch/vision/blob/main/LICENSE) y [CITATION.cff](https://github.com/pytorch/vision/blob/main/CITATION.cff)).
- **Arquitectura original (`facebookresearch/ConvNeXt`):** Licencia **`MIT`**.
- **Pesos autorizados:** `ConvNeXt_Tiny_Weights.IMAGENET1K_V1` (`https://download.pytorch.org/models/convnext_tiny-983f1562.pth`, prefijo SHA-256 `983f1562`), entrenados sobre ImageNet-1K con la receta de TorchVision (excluidos los modelos SWAG CC-BY-NC; sujeto a los términos de uso de investigación de ImageNet-1K).

## 2. Parámetros prerregistrados antes de mirar (Paso 4)

1. **Última etapa:** `features.7` (`Stage 4` de `ConvNeXt-tiny`, bloque final `features.7.2`, dimensión de canal $C = 768$, mapa espacial $7 	imes 7$ para entrada $224 	imes 224$).
2. **Etapa siguiente (para prueba de apagado):** `classifier` (`LayerNorm2d(768) -> Flatten(1) -> Linear(768, 1000)`).
3. **Muestreo de neuronas:** `200` neuronas elegidas al azar sin reemplazo entre `(0, Ellipsis, 767)` con semilla fija `SEED = 2610` (`random.Random(2610).sample(range(768), 200)`).
4. **Umbral de etiqueta confirmada (prueba de apagado):**
   - Para cada neurona $c$, se ordenan las 22 piezas por su activación media espacial $a_{i,c} = \frac{1}{49}\sum_{u,v} A_{i,c}(u,v)$.
   - **Top-9 polo +:** las 9 piezas de mayor activación (índices `0..8`).
   - **Top-9 polo −:** las 9 piezas de menor activación (índices `13..21`).
   - **9 imágenes control:** las 9 piezas centrales en torno a la mediana (índices `6..14`).
   - Al apagar la neurona $c$ ($A_{i,c} \leftarrow 0$), se mide la caída $\Delta_i(c) = \max(0, z_{i, k^*_c} - z^{(-c)}_{i, k^*_c})$ en la unidad $k^*_c = \arg\max_k W_{\text{cls}}[k, c]$ de la etapa siguiente (`classifier`).
   - La etiqueta queda **`confirmada: true`** sí y solo sí:
     $$\overline{\Delta}_{\text{top9}}(c) > 0 \quad \wedge \quad \overline{\Delta}_{\text{top9}}(c) \ge 2,0 \times \overline{\Delta}_{\text{control9}}(c)$$
   - Las neuronas que no cumplen el umbral quedan con **`confirmada: false`** y **no se borran**.

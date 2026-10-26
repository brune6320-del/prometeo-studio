# Contrato de Ficha Unificada · ADN Unido (`<nombre>.ficha.json` v1.0.0 — Fase 4c)

Este documento define el **contrato de salida estable y versionado** (`schema_version: "1.0.0"`) producido por `tools/adn_unido/estudiar_todo.py` al unificar:
1. **ADN Tipográfico (`D-10`, `tools/adn_tipo/`)** en el commit `dc5ddd5b768a3e745cbaf903efbd4ba36aac5805` (`schema_version: "1.0.0"`), ejecutando en CPU el **Camino B sin la CNN** con filtro estricto de fiabilidad léxica (`pyspellchecker` `es + en + de + fr`), control de sesgo de clase del vecino (`> 3 × 1/12 = 25%`) y cota física de tamaño en puntos.
2. **ADN de Diseño (`D-11b`, `tools/adn_diseno/`)** en el commit `d25e70187db2424be43c16c214059687c01252d4` (`schema_version: "1.1.0"`).

Su consumidor directo es **Forja 5 «Esencia»** (DeepSeek, en Prometeo).

---

## 0. Prerregistro de umbrales de fiabilidad tipográfica (fijados el `2026-10-26` ANTES de correr Fase 4c)

Con fecha **`2026-10-26`** (antes de ejecutar la evaluación de Fase 4c sobre los 18 carteles y sobre la galería sintética), quedan fijados de forma inmutable los siguientes cuatro criterios de rechazo/aceptación para evitar la ley de Goodhart:

| Regla / Criterio | Umbral prerregistrado (`2026-10-26`) | Condición de rechazo / marcado | Efecto en `<nombre>.ficha.json` (`bloque tipo`) |
|---|---|---|---|
| **1. Filtro léxico de basura OCR (`fraccion_palabras_reales`)** | `fraccion_palabras_reales >= 0.50` sobre palabras de `>= 3` letras reconocidas por `pyspellchecker` en unión multilingüe (`es ∪ en ∪ de ∪ fr`). Si hay `0` palabras de `>= 3` letras, la fracción es `0.0`. | `fraccion_palabras_reales < 0.50` (o `0` palabras de `>= 3` letras). | `"fiable": false`, `"motivo_fiabilidad"` explícito y `"metricas_letra": "no_fiable"` (o campos en `"no_fiable"`). |
| **2. Umbral mínimo de confianza tipográfica (`confianza_tipo`)** | `confianza_tipo >= 0.35` | `confianza_tipo < 0.35` | `"fiable": false`, `"motivo_fiabilidad"` explícito y `"metricas_letra": "no_fiable"` (o campos en `"no_fiable"`). |
| **3. Prueba de colapso/sesgo hacia «Anton» (matriz de confusión 12 familias)** | Cuota uniforme esperada por familia $= 1/12 \approx 0.0833$ ($8,33\%$). Umbral máximo admisible de predicción para `Anton` $= 3 \times (1/12) = 0.2500$ ($25,0\%$). | Si `Anton` gana en $> 25,0\%$ de las muestras evaluadas (en la galería sintética o en el lote de carteles), se declara sesgo del método. | Se documenta la matriz de confusión $12 \times 12$ y el campo `fuente_vecino_top1` (y `fuente_detectada`) se marca como `"sesgado"` (conservando en `fuente_vecino_bruta_sesgada` el valor bruto solo a efectos de auditoría). |
| **4. Cota física de tamaño tipográfico (`tamano_pt`)** | `0 < tamano_pt <= alto_imagen_pt_96dpi`, donde `alto_imagen_pt_96dpi = alto_px * (72.0 / 96.0)`. | Cualquier glifo o agregado cuyo `tamano_pt > alto_imagen_pt_96dpi`. | El tamaño se marca como `"imposible"` y no se propaga al promedio ni a las métricas válidas. |

---

## 1. Estructura de primer nivel de `<nombre>.ficha.json`

Toda ficha unida válida contiene exactamente **4 claves de primer nivel**:

| Clave de primer nivel | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `schema_version` | `string` | Sí | Versión del contrato de la ficha unida. Valor fijo actual: `"1.0.0"`. |
| `tipo` | `object` | Sí | Bloque de ADN tipográfico (`tools/adn_tipo/`). Incluye `"fiable": true \| false` y motivos honestos. |
| `diseno` | `object` | Sí | Bloque de ADN de diseño (`tools/adn_diseno/`). Declara `"estado": "calculado" \| "no_calculado"`. |
| `procedencia` | `object` | Sí | Trazabilidad criptográfica y de versiones de la pieza y los motores empleados. |

---

## 2. Especificación del bloque `tipo` en Fase 4c

En los **18 carteles rasterizados (`.jpg`)**:
- `estado` (`string`): `"calculado_camino_b_sin_cnn"` o `"sin_texto_ocr"`.
- `fiable` (`boolean`, obligatorio): `true` únicamente si `fraccion_palabras_reales >= 0.50` (con al menos 1 palabra de $\ge 3$ letras) **y** `confianza_tipo >= 0.35`; en caso contrario `false`.
- `motivo_fiabilidad` (`string`, obligatorio): Explicación exacta de por qué es fiable o qué umbral incumple (`fraccion_palabras_reales < 0.50`, `confianza_tipo < 0.35`, `sin palabras >= 3 letras`, etc.).
- `filtro_ocr` (`object`, obligatorio):
  - `idiomas_diccionario`: `["es", "en", "de", "fr"]`
  - `palabras_3plus_totales`: número de palabras alfanuméricas con $\ge 3$ letras.
  - `palabras_3plus_reconocidas`: número de dichas palabras reconocidas en `es ∪ en ∪ de ∪ fr`.
  - `lista_palabras_3plus`: detalle por palabra (`palabra`, `reconocida`, `idiomas`).
  - `fraccion_palabras_reales`: `float` en $[0.0, 1.0]$.
  - `umbral_fraccion_palabras_reales`: `0.50`.
  - `umbral_confianza_tipo`: `0.35`.
- `cnn` (`object`, obligatorio): `{"estado": "no_calculado", "motivo": "pesos.pt se entrenan en Colab (D-10), aún no entrenados"}`.
- `sesgo_vecino` (`object`, obligatorio):
  - `familia_auditada`: `"Anton"`
  - `umbral_colapso`: `0.25` (`3 * 1/12`)
  - `proporcion_anton_galeria`: proporción en evaluación sobre la galería sintética
  - `proporcion_anton_carteles`: proporción de carteles donde `Anton` gana en bruto
  - `es_sesgado`: `boolean`
- `metricas_letra` (`string` `"no_fiable"` o `object`):
  - Si `fiable == false`: `"metricas_letra": "no_fiable"`, y las métricas crudas quedan apartadas en `metricas_letra_descartadas_auditoria` con `"estado": "no_fiable"` para que Forja 5 no las consuma por error.
  - Si `fiable == true`: objeto con `fuente_vecino_top1` (`"sesgado"` si `es_sesgado == true`, o el nombre de la familia si no hay sesgo), `tamano_pt_medio` (o `"imposible"` si excede `alto_imagen_pt_96dpi`), `tamano_pt_max` (o `"imposible"`), `tamanos_imposibles_descartados` (`int`), `inclinacion_lineas_deg`, `interletra_pt_media`, `interlinea_pt_media`, `tinta_lab_media`.

En las **4 piezas tipográficas vectoriales OpenType/TrueType (`.ttf`)**:
- `estado`: `"calculado_nativo_opentype"`, `fiable`: `true` (lectura directa de tablas binarias `name`, `OS/2`, `head`, `post`, `fvar`), y en `diseno`: `"estado": "no_calculado"`.

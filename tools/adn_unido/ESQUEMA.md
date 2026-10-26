# Contrato de Ficha Unificada · ADN Unido (`<nombre>.ficha.json` v1.0.0 — Fase 4d)

Este documento define el **contrato de salida estable y versionado** (`schema_version: "1.0.0"`) producido por `tools/adn_unido/estudiar_todo.py` al unificar:
1. **ADN Tipográfico (`D-10`, `tools/adn_tipo/`)** en el commit `dc5ddd5b768a3e745cbaf903efbd4ba36aac5805` (`schema_version: "1.0.0"`), ejecutando en CPU el **Camino B sin la CNN** con **Régimen C (recorte nativo por caja de símbolo de Tesseract a resolución original del cartel)**, filtro estricto de fiabilidad léxica (`pyspellchecker` `es + en + de + fr`), control de sesgo de clase del vecino y cota física de tamaño en puntos.
2. **ADN de Diseño (`D-11b`, `tools/adn_diseno/`)** en el commit `d25e70187db2424be43c16c214059687c01252d4` (`schema_version: "1.1.0"`).

Su consumidor directo es **Forja 5 «Esencia»** (DeepSeek, en Prometeo).

---

## 0. Prerregistro de umbrales (fijados el `2026-10-26` ANTES de correr Fase 4c y Fase 4d)

### 0.1. Prerregistro de Fase 4d (`2026-10-26` — fijado ANTES de correr los regímenes A, B y C)

Para eliminar en `tools/adn_unido/` la causa del colapso hacia `Anton` detectada en la Fase 4c (recortar palabras sobre la rejilla reducida de `192 px` y partirlas en columnas iguales), se define y prerregistra el **Régimen C** antes de ejecutar las pruebas:

| Parámetro prerregistrado (`2026-10-26`) | Definición exacta | Criterio de éxito prerregistrado | Regla de decisión sobre `fuente_vecino_top1` |
|---|---|---|---|
| **Régimen A (referencia aislada `64×64`)** | Glifo sintético individual `64×64` de `tools/adn_tipo/.cache/dataset` (`700` muestras: `train.json` + `holdout.json`) normalizado directamente con `geometria` (`32×32`). | Referencia base (`59,29%` acierto, `8,71%` cuota `Anton`). | Línea base sin recorte de cartel. |
| **Régimen B (recorte antiguo de rejilla `8×8` $\to$ `32×32`)** | Glifo submuestreado a baja resolución (`192 px` de cartel $\approx 8\times 8$ por carácter) y reescalado a `32×32`. | Fallo demostrado en Fase 4c (`9,43%` acierto, `64,00%` cuota `Anton`). | Causaba el colapso hacia `Anton`. |
| **Régimen C («recorte nativo por caja de Tesseract»)** | Los `700` glifos sintéticos se disponen en láminas/carteles a resolución nativa (`1:1`), se extraen las cajas por símbolo (`makebox` / `image_to_boxes` de Tesseract 5.5.3 en coordenadas originales del cartel), se recorta cada símbolo a **resolución original** con margen pequeño (`pad = 2..3 px`), se inserta centrado en la plantilla `64×64` sobre su color de papel percentil-90 (idéntico a `tools/adn_tipo/inferir.py` líneas 29-31: `parche = Image.new('RGB', (64, 64), papel); parche.paste(crop, (32 - w//2, 48 - h))`) y se evalúa `geometria` (`32×32`) + vecino `Buscador`. | **Éxito sí y solo sí:**<br>1. `acierto_top1(C) >= 0.50` ($\ge 50,0\%$), **y**<br>2. `cuota_anton(C) <= 2 * (1/12)` ($\le 0.1667$, es decir $\le 16,67\%$). | `fuente_vecino_top1` **solo deja de estar marcado como `"sesgado"` en las fichas de los carteles si el Régimen C cumple ambos criterios del prerregistro**. Si no cumple cualquiera de los dos, se reporta como negativo honesto y `fuente_vecino_top1` sigue marcado como `"sesgado"`. |

### 0.2. Prerregistro de Fase 4c (`2026-10-26` — mantenido intacto en Fase 4d)

| Regla / Criterio | Umbral prerregistrado (`2026-10-26`) | Condición de rechazo / marcado | Efecto en `<nombre>.ficha.json` (`bloque tipo`) |
|---|---|---|---|
| **1. Filtro léxico de basura OCR (`fraccion_palabras_reales`)** | `fraccion_palabras_reales >= 0.50` sobre palabras de `>= 3` letras reconocidas por `pyspellchecker` (`es ∪ en ∪ de ∪ fr`). Si hay `0` palabras de `>= 3` letras, la fracción es `0.0`. | `fraccion_palabras_reales < 0.50` (o `0` palabras de `>= 3` letras). | `"fiable": false`, `"motivo_fiabilidad"` explícito y `"metricas_letra": "no_fiable"`. |
| **2. Umbral mínimo de confianza tipográfica (`confianza_tipo`)** | `confianza_tipo >= 0.35` | `confianza_tipo < 0.35` | `"fiable": false`, `"motivo_fiabilidad"` explícito y `"metricas_letra": "no_fiable"`. |
| **3. Cota física de tamaño tipográfico (`tamano_pt`)** | `0 < tamano_pt <= alto_imagen_pt_96dpi`, donde `alto_imagen_pt_96dpi = alto_px * (72.0 / 96.0)`. | `tamano_pt > alto_imagen_pt_96dpi`. | El tamaño se marca como `"imposible"` y no se propaga al promedio ni al máximo válido. |

---

## 1. Estructura de primer nivel de `<nombre>.ficha.json`

Toda ficha unida válida contiene exactamente **4 claves de primer nivel**:

| Clave de primer nivel | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `schema_version` | `string` | Sí | Versión del contrato de la ficha unida. Valor fijo actual: `"1.0.0"`. |
| `tipo` | `object` | Sí | Bloque de ADN tipográfico (`tools/adn_tipo/`). Incluye `"fiable": true \| false`, `"regimen_recorte": "C_nativo_por_caracter"` y motivos honestos. |
| `diseno` | `object` | Sí | Bloque de ADN de diseño (`tools/adn_diseno/`). Declara `"estado": "calculado" \| "no_calculado"`. |
| `procedencia` | `object` | Sí | Trazabilidad criptográfica y de versiones de la pieza y los motores empleados. |

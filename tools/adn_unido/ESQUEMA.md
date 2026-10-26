# Contrato de Ficha Unificada · ADN Unido (`<nombre>.ficha.json` v1.0.0 — Fase 4b)

Este documento define el **contrato de salida estable y versionado** (`schema_version: "1.0.0"`) producido por `tools/adn_unido/estudiar_todo.py` al unificar:
1. **ADN Tipográfico (`D-10`, `tools/adn_tipo/`)** en el commit `dc5ddd5b768a3e745cbaf903efbd4ba36aac5805` (`schema_version: "1.0.0"`), ejecutando en CPU el **Camino B sin la CNN** (OCR determinista Tesseract 5.5.3 + geometría de glifos $32 \times 32$ + vecino más próximo sobre `tools/adn_tipo/.cache/dataset/galeria.json` + línea base, interletra, interlínea y ortografía).
2. **ADN de Diseño (`D-11b`, `tools/adn_diseno/`)** en el commit `d25e70187db2424be43c16c214059687c01252d4` (`schema_version: "1.1.0"`).

Su consumidor directo es **Forja 5 «Esencia»** (DeepSeek, en Prometeo).

---

## 1. Estructura de primer nivel de `<nombre>.ficha.json`

Toda ficha unida válida contiene exactamente **4 claves de primer nivel**:

| Clave de primer nivel | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `schema_version` | `string` | Sí | Versión del contrato de la ficha unida. Valor fijo actual: `"1.0.0"`. |
| `tipo` | `object` | Sí | Bloque de ADN tipográfico (`tools/adn_tipo/`). Declara `"estado": "calculado_camino_b_sin_cnn" \| "sin_texto_ocr" \| "calculado_nativo_opentype" \| "no_calculado"`. |
| `diseno` | `object` | Sí | Bloque de ADN de diseño (`tools/adn_diseno/`). Declara `"estado": "calculado" \| "no_calculado"`. |
| `procedencia` | `object` | Sí | Trazabilidad criptográfica y de versiones de la pieza y los motores empleados. |

---

## 2. Regla de negativos honestos y determinismo OCR (Ley 8 · Fase 4b)

1. **Sub-bloque de la CNN (`tipo.cnn`) en los 18 carteles:**
   - Como los pesos `pesos.pt` requieren entrenamiento GPU en Colab (D-10) y aún no se han entrenado, en los 18 carteles el sub-bloque `tipo.cnn` declara explícitamente:
     ```json
     "cnn": {
       "estado": "no_calculado",
       "motivo": "pesos.pt se entrenan en Colab (D-10), aún no entrenados"
     }
     ```
2. **Determinismo del OCR y del vecino de glifos en CPU:**
   - Se fija:
     - Ejecutable y versión: `tesseract 5.5.3` (`/opt/homebrew/bin/tesseract`)
     - Lenguajes: `-l spa+eng`
     - Segmentación de página y motor: `--psm 6 --oem 1`
     - Hilos OpenMP fijados a 1: `-c OMP_THREAD_LIMIT=1` (`OMP_THREAD_LIMIT=1`)
     - Espacios entre palabras: `-c preserve_interword_spaces=1`
     - Semilla: `SEED = 2610` (`tools/adn_tipo/comun.py`)
     - Galería sintética congelada: `tools/adn_tipo/.cache/dataset/galeria.json` (`1.204` glifos renderizados sobre las 12 familias OFL de `fuentes.lock.json`).
3. **Carteles sin texto detectado por OCR bajo `--psm 6` fijo:**
   - Si un cartel (como `met_335536.jpg`, litografía con rotulación manual caligráfica) produce `0` palabras alfanuméricas bajo `--psm 6`, no se maquilla ni se fuerza: `tipo.estado` se reporta como `"sin_texto_ocr"`, conservando la estimación geométrica de bandas de `adn_diseno`.
4. **Piezas tipográficas vectoriales OpenType/TrueType (`.ttf`):**
   - En `tipo`: se leen de forma determinista las tablas binarias OpenType (`name`, `OS/2`, `head`, `post`, `fvar`) y se cruza con `tools/adn_tipo/fuentes.lock.json` (`"estado": "calculado_nativo_opentype"`).
   - En `diseno`: no se inventa un cartel ni una paleta cromática artificial; se declara `"estado": "no_calculado"` con `k_elegido: null`, `paleta_insuficiente: null`, `confianza_global: null`.

---

## 3. Especificación de los bloques

### 3.1. Bloque `tipo`
- `estado` (`string`, obligatorio): `"calculado_camino_b_sin_cnn"`, `"sin_texto_ocr"`, `"calculado_nativo_opentype"` o `"no_calculado"`.
- `fuente_detectada` (`string`, obligatorio): Familia tipográfica principal (por vecino de píxeles $32 \times 32$ en carteles con texto, o tabla `name` en archivos `.ttf`), `"sin_texto_ocr"` o `"no_calculado"`.
- En carteles rasterizados (`estado` en `{"calculado_camino_b_sin_cnn", "sin_texto_ocr"}`):
  - `cnn` (`object`, obligatorio): `{"estado": "no_calculado", "motivo": "pesos.pt se entrenan en Colab (D-10), aún no entrenados"}`.
  - `motor_ocr` (`object`, obligatorio): `version`, `lenguajes`, `psm` (`6`), `oem` (`1`), `omp_thread_limit` (`1`), `semilla` (`2610`), `galeria_sha256`.
  - `texto_ocr` (`string`): Texto extraído por Tesseract.
  - `texto_ocr_resumen` (`string`): Resumen en $\le 6$ palabras del texto OCR detectado.
  - `num_palabras_ocr` (`int`): Número de palabras alfanuméricas detectadas.
  - `num_glifos_analizados` (`int`): Número de glifos comparados contra `galeria.json`.
  - `metricas_letra` (`object`): Contiene `fuente_vecino_top1`, `fuentes_vecino_top3`, `tamano_pt_medio`, `tamano_pt_max`, `peso_dominante`, `cursiva_proporcion`, `inclinacion_lineas_deg`, `interletra_pt_media`, `interlinea_pt_media`, `tinta_lab_media` (en CIE $L^*a^*b^*$, nunca RGB crudo) y `metrica_principal_resumen`.
  - `confianza_tipo` (`number` en $[0.0, 1.0]$): Confianza combinada del margen de semejanza del vecino de píxeles ($\le 0,80$, `tools/adn_tipo/inferir.py`) y la confianza media de palabra de Tesseract.
  - `ortografia` (`array`): Salida del verificador ortográfico español (`pyspellchecker`, solo marca `"revisar"`, nunca corrige).
  - `spans_muestra` (`array`): Muestra estructurada de spans inferidos (`bbox`, `texto`, `fuente`, `tamano_pt`, `peso`, `cursiva`, `inclinacion`, `tinta_lab`, `interletra`, `interlinea`, `linea_base`, `origen`, `confianza`).

### 3.2. Bloque `diseno`
- `estado` (`string`, obligatorio): `"calculado"` o `"no_calculado"`.
- Si `estado == "calculado"`: contiene el contrato íntegro `estudio.json` (`schema_version: "1.1.0"`) validado por `tools/adn_diseno/esquema.py`.
- Si `estado == "no_calculado"`: contiene `motivo` (`string`), `k_elegido` (`null`), `paleta_insuficiente` (`null`) y `confianza_global` (`null`).

### 3.3. Bloque `procedencia`
Contiene obligatoriamente:
- `nombre_archivo` (`string`)
- `sha256_imagen` (`string`, 64 hex)
- `commit_adn_tipo` (`"dc5ddd5b768a3e745cbaf903efbd4ba36aac5805"`)
- `commit_adn_diseno` (`"d25e70187db2424be43c16c214059687c01252d4"`)
- `schema_version_adn_tipo` (`"1.0.0"`)
- `schema_version_adn_diseno` (`"1.1.0"`)
- `fecha_utc` (`string`, ISO-8601 UTC)
- `maquina` (`string`)
- `sha256_ficha_determinista` (`string`, 64 hex calculado excluyendo `fecha_utc`)

# Contrato de Ficha Unificada · ADN Unido (`<nombre>.ficha.json` v1.0.0)

Este documento define el **contrato de salida estable y versionado** (`schema_version: "1.0.0"`) producido por `tools/adn_unido/estudiar_todo.py` al unificar:
1. **ADN Tipográfico (`D-10`, `tools/adn_tipo/`)** en el commit `dc5ddd5b768a3e745cbaf903efbd4ba36aac5805` (`schema_version: "1.0.0"`).
2. **ADN de Diseño (`D-11b`, `tools/adn_diseno/`)** en el commit `d25e70187db2424be43c16c214059687c01252d4` (`schema_version: "1.1.0"`).

Su consumidor directo es **Forja 5 «Esencia»** (DeepSeek, en Prometeo).

---

## 1. Estructura de primer nivel de `<nombre>.ficha.json`

Toda ficha unida válida contiene exactamente **4 claves de primer nivel**:

| Clave de primer nivel | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `schema_version` | `string` | Sí | Versión del contrato de la ficha unida. Valor fijo actual: `"1.0.0"`. |
| `tipo` | `object` | Sí | Bloque de ADN tipográfico (`tools/adn_tipo/`). Declara `"estado": "calculado" \| "calculado_nativo_opentype" \| "no_calculado"`. |
| `diseno` | `object` | Sí | Bloque de ADN de diseño (`tools/adn_diseno/`). Declara `"estado": "calculado" \| "no_calculado"`. |
| `procedencia` | `object` | Sí | Trazabilidad criptográfica y de versiones de la pieza y los motores empleados. |

---

## 2. Regla de negativos honestos (Ley 8)

1. **Cuando una parte de `adn_tipo` requiere GPU, binarios externos (`tesseract`) o pesos (`pesos.pt`) no presentes en la Mac mini:**
   - No se inventa ni se simula la inferencia tipográfica.
   - El bloque `tipo` se rellena con:
     ```json
     {
       "estado": "no_calculado",
       "motivo": "Explicación verificable de la dependencia o peso ausente en la Mac mini",
       "fuente_detectada": "no_calculado",
       "estimacion_estructural_adn_diseno": { ... }
     }
     ```
2. **Cuando la pieza de entrada es un binario tipográfico vectorial OpenType/TrueType (`.ttf`):**
   - En `tipo`: se leen de forma determinista las tablas binarias OpenType (`name`, `OS/2`, `head`, `post`, `fvar`) y se cruza con `tools/adn_tipo/fuentes.lock.json` (`"estado": "calculado_nativo_opentype"`), declarando explícitamente que el OCR/CNN sobre imagen rasterizada no aplica a un contenedor `.ttf`.
   - En `diseno`: no se inventa un cartel ni una paleta cromática artificial; se declara `"estado": "no_calculado"` con su `"motivo"` explícito y `k_elegido: null`, `paleta_insuficiente: null`, `confianza_global: null`.

---

## 3. Especificación de los bloques

### 3.1. Bloque `tipo`
- `estado` (`string`, obligatorio): `"calculado"`, `"calculado_nativo_opentype"` o `"no_calculado"`.
- `motivo` (`string`, obligatorio cuando `estado != "calculado"`): Causa exacta y verificable.
- `fuente_detectada` (`string`, obligatorio): Nombre de la familia tipográfica detectada (p. ej. `"Cormorant Garamond (Light, 300)"`) o `"no_calculado"`.
- Si `estado == "calculado"`: incluye la salida completa de `tools/adn_tipo` (`zonas`, `escala`, `interlineado_global`, `confianza_media`).
- Si `estado == "calculado_nativo_opentype"`: incluye `metadatos_opentype` (`familia`, `subfamilia`, `nombre_completo`, `postscript_name`, `usWeightClass`, `usWidthClass`, `italicAngle`, `units_per_em`, `es_variable`, `tablas_opentype`) y `catalogo_adn_tipo` (cruce con `tools/adn_tipo/fuentes.lock.json`).
- Si `estado == "no_calculado"`: incluye `dependencias_faltantes` (lista verificada en tiempo de ejecución) y `estimacion_estructural_adn_diseno` (el bloque geométrico `escala_tipografica` de `adn_diseno` si la pieza es una imagen).

### 3.2. Bloque `diseno`
- `estado` (`string`, obligatorio): `"calculado"` o `"no_calculado"`.
- Si `estado == "calculado"`: contiene el contrato íntegro `estudio.json` (`schema_version: "1.1.0"`) validado por `tools/adn_diseno/esquema.py` (`referente`, `paleta`, `reticula`, `escala_tipografica`, `vacio`, `jerarquia`, `saliencia`, `confianza`), donde:
  - `diseno.paleta.k_elegido` $\in [3, 10]$
  - `diseno.paleta.paleta_insuficiente` $\in \{\text{true}, \text{false}\}$
  - `diseno.confianza.global` $\in [0.0, 1.0]$
- Si `estado == "no_calculado"`: contiene `motivo` (`string`), `k_elegido` (`null`), `paleta_insuficiente` (`null`) y `confianza_global` (`null`).

### 3.3. Bloque `procedencia`
Contiene obligatoriamente:
- `nombre_archivo` (`string`): Nombre base del archivo de entrada.
- `sha256_imagen` (`string`, 64 hex): Hash SHA-256 exacto de los bytes del archivo de entrada.
- `commit_adn_tipo` (`string`): Hash del commit de `tools/adn_tipo/` (`"dc5ddd5b768a3e745cbaf903efbd4ba36aac5805"`).
- `commit_adn_diseno` (`string`): Hash del commit base de `tools/adn_diseno/` (`"d25e70187db2424be43c16c214059687c01252d4"`).
- `schema_version_adn_tipo` (`string`): `"1.0.0"`.
- `schema_version_adn_diseno` (`string`): `"1.1.0"`.
- `fecha_utc` (`string`): Marca temporal ISO-8601 en UTC (`YYYY-MM-DDTHH:MM:SSZ`).
- `maquina` (`string`): Identificador del nodo y arquitectura donde se ejecutó el estudio.
- `sha256_ficha_determinista` (`string`, 64 hex): Hash SHA-256 canónico de la ficha excluyendo `procedencia.fecha_utc`, utilizado para verificar determinismo estricto entre corridas.

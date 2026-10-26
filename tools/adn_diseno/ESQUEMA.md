# Contrato de Salida · ADN de Diseño (`estudio.json` v1.0.0)

Este documento define el **contrato de salida estable y versionado** (`schema_version: "1.0.0"`) producido por `tools/adn_diseno/` para su consumo por **Forja 4** (conversión en tokens de relaciones visuales) y por `tools/adn_diseno/aplicar.py`.

> **Regla de versionado:** No se puede añadir, renombrar ni eliminar ningún bloque fijo ni cambiar las unidades de medida sin incrementar `schema_version` siguiendo Versionado Semántico (`MAJOR.MINOR.PATCH`).
>
> **Regla cromática estricta:** Queda prohibido emitir valores RGB crudos (`[R, G, B]` o hex `#RRGGBB`) en `estudio.json`. Todo color se expresa exclusivamente en el espacio perceptual **CIE $L^*a^*b^*$ (iluminante D65, observador $2^\circ$)** y sus coordenadas cilíndricas **CIE $L^*C^*_{ab}h_{ab}$**, y toda distancia cromática se calcula mediante **$\Delta E_{2000}$ (CIEDE2000, Sharma et al., 2005)**.

---

## 1. Estructura de primer nivel de `estudio.json`

Todo archivo `estudio.json` válido contiene exactamente estas **9 claves de primer nivel**, de las cuales **7 son los bloques funcionales obligatorios del contrato**:

| Clave de primer nivel | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `schema_version` | `string` | Sí | Versión del contrato de esquema. Valor fijo actual: `"1.0.0"`. |
| `referente` | `object` | Sí | Metadatos técnicos del referente estudiado (tipo de entrada, hash SHA-256, dimensiones y relación de aspecto), sin copiar contenido privativo ni imágenes en bruto. |
| `paleta` | `object` | **Bloque fijo 1** | Paleta perceptual en CIE $L^*a^*b^*$ ($k$-means ponderado por área), proporciones, distancias $\Delta E_{2000}$, armonía, contraste de valores, temperatura y saturación media. |
| `reticula` | `object` | **Bloque fijo 2** | Columnas detectadas, márgenes relativos, medianiles, ejes de alineación, proximidad a tercios y proporción áurea ($\phi$), ritmo y repetición. |
| `escala_tipografica` | `object` | **Bloque fijo 3** | Salida de `tools/adn_tipo/` (D-10) si existe en el repositorio, o hueco estructurado con estimación geométrica de bandas de texto. |
| `vacio` | `object` | **Bloque fijo 4** | Porcentaje de aire / espacio negativo, reparto por cuadrantes y centro de peso visual con vector de equilibrio. |
| `jerarquia` | `object` | **Bloque fijo 5** | Jerarquía de tamaños y pesos visuales, razones de escala entre elementos ($1.0 : r_2 : r_3 \dots$), índice de dominancia y recorrido visual. |
| `saliencia` | `object` | **Bloque fijo 6** | Mapa de saliencia visual (qué mira primero el ojo), foco primario, focos secundarios, concentración espacial y rejilla $8 \times 8$ lista para tokenización. |
| `confianza` | `object` | **Bloque fijo 7** | Confianza numérica en $[0.0, 1.0]$ desglosada para cada uno de los 6 bloques anteriores más puntuación global y notas diagnósticas. |

---

## 2. Especificación detallada por bloque

### 2.1. `referente`
Identifica la pieza analizada sin almacenar píxeles ni texto con copyright:
```json
{
  "id": "cma_1950_455",
  "tipo_entrada": "imagen",
  "sha256_origen": "484e5e6dc9277f9be194420e092a3573f33769d52d275d0c41e1d3df50c5bd94",
  "dimensiones": {
    "ancho_px": 656,
    "alto_px": 893,
    "relacion_aspecto": 0.7346,
    "orientacion": "vertical"
  }
}
```
* `tipo_entrada`: `"imagen" | "pdf_pagina" | "fotograma" | "pieza_recortador"`.
* `orientacion`: `"vertical" | "horizontal" | "cuadrada"`.

### 2.2. `paleta` (CIE $L^*a^*b^*$ + proporción + $\Delta E_{2000}$)
```json
{
  "espacio_color": "CIE_L*a*b*_D65_2deg",
  "metodo": "kmeans_lab_ponderado_area",
  "num_colores": 5,
  "colores": [
    {
      "id": "c0",
      "rol": "dominante",
      "lab": { "L": 81.42, "a": 2.15, "b": 18.64 },
      "lch": { "L": 81.42, "C": 18.76, "h_deg": 83.42 },
      "proporcion": 0.4125
    }
  ],
  "pares_delta_e2000": [
    {
      "par": ["c0", "c1"],
      "delta_e2000": 48.72,
      "delta_L": 62.10
    }
  ],
  "matriz_delta_e2000": [
    [0.0, 48.72, 31.15]
  ],
  "armonia": {
    "tipo": "complementaria_dividida",
    "diferencia_angular_principal_deg": 154.2,
    "explicacion": "Contraste entre tonos cálidos ocres/amarillos y acentos fríos/rojizos."
  },
  "contraste_valores": {
    "rango_L": 68.4,
    "contraste_dominante_secundario_L": 54.2,
    "contraste_max_delta_e2000": 58.9,
    "desviacion_L_ponderada": 24.6,
    "clave_tonal": "alto_contraste"
  },
  "temperatura": {
    "indice_calidez_lab": 14.8,
    "clasificacion": "calida",
    "proporcion_calidos": 0.78,
    "proporcion_frios": 0.22
  },
  "saturacion_media": {
    "croma_medio_C": 21.4,
    "croma_max_C": 52.8,
    "clasificacion": "moderada"
  }
}
```
* **Invariante:** Ningún subcampo de `paleta` puede contener coordenadas RGB ni códigos hexadecimales. La suma de `colores[*].proporcion` es $1.0 \pm 10^{-4}$.

### 2.3. `reticula`
```json
{
  "columnas": {
    "num_columnas": 2,
    "anchos_relativos": [0.46, 0.46],
    "regularidad": 0.88
  },
  "margenes": {
    "superior_rel": 0.062,
    "inferior_rel": 0.075,
    "izquierdo_rel": 0.058,
    "derecho_rel": 0.064,
    "simetria_horizontal": 0.94,
    "simetria_vertical": 0.89
  },
  "medianiles": {
    "medianiles_verticales_x_rel": [0.50],
    "ancho_medio_rel": 0.032,
    "medianiles_horizontales_y_rel": [0.28, 0.74]
  },
  "ejes_alineacion": {
    "verticales_x_rel": [
      { "pos": 0.06, "fuerza": 0.92 },
      { "pos": 0.50, "fuerza": 0.81 }
    ],
    "horizontales_y_rel": [
      { "pos": 0.18, "fuerza": 0.88 },
      { "pos": 0.62, "fuerza": 0.79 }
    ]
  },
  "proporciones_geometricas": {
    "alineacion_tercios": 0.84,
    "alineacion_aurea": 0.91,
    "ejes_proximos_tercios": [0.333, 0.667],
    "ejes_proximos_aureos": [0.382, 0.618],
    "sistema_dominante": "aureo"
  },
  "ritmo_y_repeticion": {
    "paso_vertical_rel": 0.145,
    "paso_horizontal_rel": 0.240,
    "regularidad_ritmica": 0.76,
    "repeticion_bloques": 4
  }
}
```
* Todas las coordenadas espaciales están normalizadas en $[0.0, 1.0]$ respecto al ancho (`x_rel`) o alto (`y_rel`) del lienzo para que sean independientes de la resolución en píxeles.

### 2.4. `escala_tipografica`
Si `tools/adn_tipo/` (D-10) existe en el árbol del proyecto, se invoca directamente y su resultado se integra en `datos_adn_tipo`. Si no existe, se mantiene el hueco con `datos_adn_tipo: null` y se rellenan las métricas geométricas de bandas tipográficas:
```json
{
  "fuente_analisis": "hueco_estimacion_estructural",
  "adn_tipo_disponible": false,
  "hay_texto_detectado": true,
  "niveles_detectados": 3,
  "alturas_relativas_lineas": [0.082, 0.038, 0.019],
  "razon_escala": 2.10,
  "densidad_tipografica_rel": 0.14,
  "zonas_texto_rel": [
    { "rol": "titular", "caja_rel": [0.08, 0.06, 0.84, 0.12], "altura_rel": 0.082 }
  ],
  "datos_adn_tipo": null
}
```

### 2.5. `vacio`
```json
{
  "porcentaje_aire": 42.6,
  "proporcion_aire": 0.426,
  "distribucion_cuadrantes": {
    "sup_izq": 0.48,
    "sup_der": 0.52,
    "inf_izq": 0.34,
    "inf_der": 0.36
  },
  "centro_peso_visual": {
    "x_rel": 0.485,
    "y_rel": 0.542,
    "desviacion_del_centro": {
      "dx": -0.015,
      "dy": 0.042,
      "distancia_euclidea": 0.0446
    },
    "equilibrio": "centrado"
  }
}
```

### 2.6. `jerarquia`
```json
{
  "num_elementos_principales": 4,
  "razones_tamano": [1.0, 0.44, 0.19, 0.08],
  "razones_peso_visual": [1.0, 0.52, 0.24, 0.11],
  "indice_dominancia": 1.92,
  "niveles": [
    {
      "rango": 1,
      "id_region": "r1",
      "rol_jerarquico": "primario_focal",
      "caja_rel": [0.12, 0.18, 0.74, 0.58],
      "area_rel": 0.429,
      "peso_visual_rel": 0.512,
      "contraste_local_delta_e2000": 44.8
    }
  ],
  "recorrido_visual_rel": [
    { "orden": 1, "x_rel": 0.49, "y_rel": 0.47, "peso": 0.512 },
    { "orden": 2, "x_rel": 0.48, "y_rel": 0.12, "peso": 0.266 }
  ]
}
```

### 2.7. `saliencia`
```json
{
  "metodo": "spectral_residual_hou_zhang_2007_mas_itti_koch_ciede2000",
  "licencia_metodo": "Dominio público algorítmico (Hou & Zhang CVPR 2007 + Itti, Koch & Niebur PAMI 1998)",
  "foco_primario": {
    "x_rel": 0.468,
    "y_rel": 0.391,
    "intensidad": 1.0,
    "cuadrante": "sup_izq"
  },
  "focos_secundarios": [
    { "orden": 2, "x_rel": 0.531, "y_rel": 0.141, "intensidad": 0.78, "radio_rel": 0.11 }
  ],
  "concentracion_espacial": 0.68,
  "coincidencia_jerarquia_saliencia": 0.85,
  "mapa_rejilla_8x8": [
    [0.12, 0.18, 0.42, 0.65, 0.61, 0.38, 0.15, 0.10]
  ]
}
```

### 2.8. `confianza`
```json
{
  "global": 0.86,
  "por_bloque": {
    "paleta": 0.96,
    "reticula": 0.84,
    "escala_tipografica": 0.65,
    "vacio": 0.92,
    "jerarquia": 0.89,
    "saliencia": 0.90
  },
  "notas": {
    "paleta": "Convergencia k-means en CIE Lab con ΔE2000 verificado.",
    "escala_tipografica": "Hueco D-10 activo (tools/adn_tipo/ no encontrado); estimación por morfología de líneas horizontales."
  }
}
```

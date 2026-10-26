# Contrato de Salida · ADN de Diseño (`estudio.json` v1.1.0)

Este documento define el **contrato de salida estable y versionado** (`schema_version: "1.1.0"`) producido por `tools/adn_diseno/` para su consumo por **Forja 4** (conversión en tokens de relaciones visuales) y por `tools/adn_diseno/aplicar.py`.

* **Cambios en `v1.1.0` (D-11b):**
  1. **`paleta` con $K$ adaptativo ($3 \dots 10$):** Añade `k_rango_evaluado` (`[3, 10]`), `k_elegido`, `umbral_delta_e2000_objetivo` (`5.0`), `delta_e2000_cuantizacion_media`, `delta_e2000_cuantizacion_std` y la bandera booleana explícita `"paleta_insuficiente": true | false` cuando incluso con $K=10$ la $\Delta E_{2000}$ media de los píxeles frente a su color de paleta reconvertido a sRGB supera `5.0`.
  2. **`confianza` continua (Ley 8):** Sustituye todos los escalones fijos por fórmulas continuas medidas sobre el residuo de cuantización $\Delta E_{2000}$, la separabilidad bimodal figura/fondo, la fracción de peso visual explicada y la relación señal-a-ruido (SNR) espacial (`saliencia.snr_espacial`).

> **Regla de versionado:** No se puede añadir, renombrar ni eliminar ningún bloque fijo ni cambiar las unidades de medida sin incrementar `schema_version` siguiendo Versionado Semántico (`MAJOR.MINOR.PATCH`).
>
> **Regla cromática estricta:** Queda prohibido emitir valores RGB crudos (`[R, G, B]` o hex `#RRGGBB`) en `estudio.json`. Todo color se expresa exclusivamente en el espacio perceptual **CIE $L^*a^*b^*$ (iluminante D65, observador $2^\circ$)** y sus coordenadas cilíndricas **CIE $L^*C^*_{ab}h_{ab}$**, y toda distancia cromática se calcula mediante **$\Delta E_{2000}$ (CIEDE2000, Sharma et al., 2005)**.

---

## 1. Estructura de primer nivel de `estudio.json`

Todo archivo `estudio.json` válido contiene exactamente estas **9 claves de primer nivel**, de las cuales **7 son los bloques funcionales obligatorios del contrato**:

| Clave de primer nivel | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `schema_version` | `string` | Sí | Versión del contrato de esquema. Valor fijo actual: `"1.1.0"`. |
| `referente` | `object` | Sí | Metadatos técnicos del referente estudiado (tipo de entrada, hash SHA-256, dimensiones y relación de aspecto), sin copiar contenido privativo ni imágenes en bruto. |
| `paleta` | `object` | **Bloque fijo 1** | Paleta perceptual en CIE $L^*a^*b^*$ ($k$-means adaptativo $K \in [3, 10]$ ponderado por área), `k_elegido`, residuo $\Delta E_{2000}$, `paleta_insuficiente`, proporciones, distancias $\Delta E_{2000}$, armonía, contraste de valores, temperatura y saturación media. |
| `reticula` | `object` | **Bloque fijo 2** | Columnas detectadas, márgenes relativos, medianiles, ejes de alineación, proximidad a tercios y proporción áurea ($\phi$), ritmo y repetición. |
| `escala_tipografica` | `object` | **Bloque fijo 3** | Salida de `tools/adn_tipo/` (D-10) si existe en el repositorio, o hueco estructurado con estimación geométrica de bandas de texto. |
| `vacio` | `object` | **Bloque fijo 4** | Porcentaje de aire / espacio negativo, reparto por cuadrantes y centro de peso visual con vector de equilibrio. |
| `jerarquia` | `object` | **Bloque fijo 5** | Jerarquía de tamaños y pesos visuales, razones de escala entre elementos ($1.0 : r_2 : r_3 \dots$), índice de dominancia y recorrido visual. |
| `saliencia` | `object` | **Bloque fijo 6** | Mapa de saliencia visual (qué mira primero el ojo), foco primario, focos secundarios, concentración espacial, `snr_espacial` y rejilla $8 \times 8$ lista para tokenización. |
| `confianza` | `object` | **Bloque fijo 7** | Confianza continua en $[0.0, 1.0]$ calculada sobre residuos/SNR para cada uno de los 6 bloques anteriores más puntuación global y notas diagnósticas. |

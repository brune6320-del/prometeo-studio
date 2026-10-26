# D-11 / D-11b · Respuestas a la Revisión de Claude y Registro de Cambios (`RESPUESTAS-REVISION.md`)

Este documento conserva las respuestas honestas entregadas en `e55c4fd` y registra la implementación autorizada en **D-11b** sobre la rama `studio/adn-diseno` (`schema_version: "1.1.0"`).

---

## 1. Confianza calculada de forma continua (Ley 8 — ningún número fijo)

* **Diagnóstico en `2264309` / `e55c4fd`:** Los 6 bloques devolvían constantes o escalones condicionales (`0.96/0.85`, `0.90/0.75`, `0.90/0.76/0.65`, `0.94`, `0.92/0.78`, `0.91`).
* **Implementación en D-11b (0 constantes fijas):**
  1. **`paleta` (`color_lab.py`):**
     $$C_{\text{paleta}} = \exp\left(-\frac{\overline{\Delta E_{2000}}_{\text{px}}}{9,5}\right) \cdot \left(0,70 + \frac{0,30}{1 + \sigma(\Delta E_{2000,\text{px}})/10,0}\right)$$
  2. **`reticula` (`composicion.py`):** Producto continuo de la fracción lisa del soporte ($F_{\text{liso}}$, píxeles con $\|\nabla L^*\| < 4,5$), la relación señal-a-ruido de los perfiles de borde proyectados ($CV_{\text{bordes}} / (CV_{\text{bordes}} + 0,45)$), la regularidad de columnas y la afinidad geométrica ($\max(\text{tercios}, \text{áurea})$).
  3. **`escala_tipografica` (`composicion.py`):** Producto continuo de $F_{\text{liso}}$ y el contraste pico-a-mediana de las bandas horizontales de gradiente ($0,50 + 0,50 \cdot \text{SNR}_{\text{bandas}}$).
  4. **`vacio` (`composicion.py`):** Combinación continua de la contigüidad espacial de los 4 vecinos del aire ($0,55 \cdot C_{\text{contig}}$) y la separabilidad bimodal figura/fondo ($0,45 \cdot S_{\text{bimodal}} \cdot F_{\text{liso}}$).
  5. **`jerarquia` (`composicion.py`):** Fracción del peso visual activo explicada por componentes conexas coherentes ($\Delta E_{2000} < 14$) multiplicada por la pureza del soporte y el contraste medio de las regiones.
  6. **`saliencia` (`saliencia.py`):** Producto continuo de la coherencia espacial local de la rejilla $64 \times 64$ ($1 / (1 + (\overline{\Delta E}_{\text{vecinos}}/7,5)^{1,5})$) por la combinación de SNR espacial ($(P_{95} - P_{50}) / (P_{95} + 0,5 P_{50} + 1)$) y concentración espacial.

### Resultado medido en la Prueba 6 de `medir.py` (`confianza_continua_ruido_vs_3_colores_planos`):

| Bloque | Imagen de ruido aleatorio uniforme (`ruido_aleatorio`) | Imagen limpia de 3 colores planos (`tres_colores_planos`) | Diferencia ($\Delta$ Confianza) |
|---|---|---|---|
| **`global`** | **`0.0421`** | **`0.7503`** | **`+0.7082`** (SUBE) |
| `paleta` | `0.2265` ($K=10, \overline{\Delta E_{00}}=12.913$, `insuf=true`) | `1.0000` ($K=3, \overline{\Delta E_{00}}=0.000$, `insuf=false`) | `+0.7735` |
| `reticula` | `0.0002` | `0.8133` | `+0.8131` |
| `escala_tipografica` | `0.0002` | `0.4776` | `+0.4774` |
| `vacio` | `0.0024` | `0.9051` | `+0.9027` |
| `jerarquia` | `0.0000` | `0.8940` | `+0.8940` |
| `saliencia` | `0.0233` | `0.4117` | `+0.3884` |

---

## 2. $K$ adaptativo ($3 \dots 10$) para degradados y tabla Antes ($K=5$) vs Después ($K$ adaptativo)

En `color_lab.py` (`_kmeans_lab_adaptativo`), $K$ arranca en `3` y crece hasta `10` deteniéndose en el primer $K$ donde la $\Delta E_{2000}$ media de todos los píxeles frente a su color de paleta reconvertido a sRGB (`Lab -> sRGB -> Lab`) es $< 5,0$. Si en $K=10$ sigue $\ge 5,0$, declara `"paleta_insuficiente": true`.

### Tabla comparativa sobre los 5 carteles de D-3 (más los negativos en $K=10$ del corpus completo):

| Cartel del corpus D-3 | Antes ($K=5$ fijo en D-11): $\overline{\Delta E_{2000}}$ | Antes ($K=5$ con semillas D-11b): $\overline{\Delta E_{2000}}$ | Después ($K$ adaptativo $3..10$): $K$ elegido | Después ($K$ adaptativo): $\overline{\Delta E_{2000}}$ | `paleta_insuficiente` | Confianza `paleta` / `global` | Estado final ($\overline{\Delta E_{2000}} < 5,0$) |
|---|---|---|---|---|---|---|---|
| `cma_1934_29.jpg` | `5.661` (FALLA) | `5.373` (FALLA) | **`K = 7`** | **`4.804`** | `false` | `0.5655` / `0.4311` | **OK** (rescatado en $K=7$) |
| `cma_1950_455.jpg` | `2.261` (OK) | `1.702` (OK) | **`K = 3`** | **`2.352`** | `false` | `0.7211` / `0.5751` | **OK** (converge en $K=3$) |
| `cma_1952_10.jpg` | `3.046` (OK) | `3.010` (OK) | **`K = 3`** | **`3.596`** | `false` | `0.6237` / `0.5942` | **OK** (converge en $K=3$) |
| `cma_1966_352.jpg` | `2.492` (OK) | `2.465` (OK) | **`K = 3`** | **`3.331`** | `false` | `0.6589` / `0.5980` | **OK** (converge en $K=3$) |
| `cma_1968_257.jpg` | `6.464` (FALLA) | `6.044` (FALLA) | **`K = 6`** | **`4.838`** | `false` | `0.5545` / `0.4797` | **OK** (rescatado en $K=6$) |
| *`met_335536.jpg` (Moulin Rouge, salpicadura litográfica)* | `8.042` (FALLA) | `7.118` (FALLA) | **`K = 10` (tope)** | **`5.797`** | **`true`** | `0.4939` / `0.3831` | **NEGATIVO HONESTO (`paleta_insuficiente: true`)** |
| *`wikimedia_ed_03.jpg` (Casino de Paris, degradado arcoíris Chéret)* | `8.915` (FALLA) | `8.112` (FALLA) | **`K = 10` (tope)** | **`6.775`** | **`true`** | `0.4468` / `0.2949` | **NEGATIVO HONESTO (`paleta_insuficiente: true`)** |

---

## 3. Genealogía de la rama verificada sobre `origin/studio/collage`

Tras el rebase realizado por Bruno, `studio/adn-diseno` desciende directamente de `origin/studio/collage` (`e9fa572 studio: cierre de Forja 4`), y los commits de D-11b se apoyan encima de `e55c4fd`.

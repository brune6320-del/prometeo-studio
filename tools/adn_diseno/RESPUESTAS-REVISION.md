# D-11 · Respuestas a la Revisión de Claude (`RESPUESTAS-REVISION.md`)

Este documento responde de forma directa y verificable a los tres puntos solicitados para la revisión de código de `studio/adn-diseno` (`ec366d8`), sin alterar el código congelado de los 4 commits anteriores.

---

## 1. ¿La «confianza» (`0,96` / `0,90` / `0,76` …) sale de un cálculo sobre la imagen o es un valor fijo por bloque?

**Respuesta honesta (Ley 8): Son valores fijos / escalones discretos codificados por condicionales (`if/else`), NO una métrica continua calculada a partir del residuo o la incertidumbre sobre la imagen. Según la Ley 8, un número fijo o por escalón binario no es una confianza real.**

A continuación se indican exactamente los archivos y líneas donde se asignan en `ec366d8`:

1. **`tools/adn_diseno/color_lab.py`, línea 343:**
   ```python
   confianza = 0.96 if n_col >= 2 else 0.85
   ```
   Devuelve siempre `0.96` si `k-means` extrae $\ge 2$ colores y `0.85` si queda 1 solo clúster, sin medir el error de cuantización $\Delta E_{2000}$ de los píxeles respecto a sus centroides.
2. **`tools/adn_diseno/composicion.py`, línea 459 (`_analizar_escala_tipografica`):**
   ```python
   confianza = 0.90 if datos_adn_tipo is not None else (0.76 if hay_texto else 0.65)
   ```
   Usa tres constantes fijas (`0.90`, `0.76` o `0.65`) según exista `tools/adn_tipo` o se hayan detectado bandas de gradiente.
3. **`tools/adn_diseno/composicion.py`, líneas 651–656 (`estudiar_composicion`):**
   ```python
   confianzas = {
       "reticula": 0.90 if (ejes_v or ejes_h) else 0.75,
       "escala_tipografica": conf_escala,
       "vacio": 0.94,
       "jerarquia": 0.92 if len(niveles_jer) >= 2 else 0.78,
   }
   ```
   `vacio` es una constante literal (`0.94`), `reticula` vale `0.90` o `0.75`, y `jerarquia` vale `0.92` o `0.78`.
4. **`tools/adn_diseno/saliencia.py`, línea 266 (`estudiar_saliencia`):**
   ```python
   return bloque_saliencia, 0.91
   ```
   Es una constante literal (`0.91`).

### Cómo debe sustituirse en cuanto autorices tocar el código (fórmula real basada en datos):
* **`paleta`:** $C_{\text{paleta}} = \max(0, 1 - \overline{\Delta E_{2000}}(\text{píxel}, \text{centroide asignado}) / 15.0)$.
* **`reticula`:** $C_{\text{retícula}} = \text{media}(\text{fuerza\_picos\_ejes}, \text{regularidad\_columnas}, \max(\text{afinidad\_tercios}, \text{afinidad\_áurea}))$.
* **`vacio`:** margen de separación bimodal entre el histograma de $\Delta E_{2000}(\text{píxel}, \text{fondo})$ del soporte y el de la figura.
* **`jerarquia`:** fracción del peso visual total explicada por las $K$ regiones segmentadas frente al ruido no agrupado.
* **`saliencia`:** relación pico-a-media (SNR espacial) del mapa de saliencia $64 \times 64$.

---

## 2. Comprobación de contenido real sobre el corpus D-3 (capaz de fallar: residuo $\Delta E_{2000} < 5,0$)

Tal como señalas, en `medir.py` (`lineas 371–401`, `probar_corpus_editorial_d3`) solo se llamaba a `validar_estudio(est)` (validez estructural del esquema JSON).

Si añadimos la comprobación de contenido propuesta —**que los píxeles reales asignados a cada color de la paleta (tras reconvertir el centroide Lab $\to$ sRGB $\to$ Lab) estén a una distancia media $\Delta E_{2000} < 5,0$**—, el resultado medido sobre los 5 carteles de `~/Desktop/REFERENTES/corpus-editorial/muestras/` es el siguiente:

| Cartel del corpus D-3 | $\Delta E_{2000}$ máx. de ida y vuelta centroide (`Lab -> sRGB -> Lab`) | $\Delta E_{2000}$ medio de píxeles reales a su color de paleta reconvertido a sRGB | ¿Cumple criterio estricto $\overline{\Delta E_{2000}} < 5,0$ con $K=5$? |
|---|---|---|---|
| `cma_1934_29.jpg` | `0.521` | **`5.661`** | **FALLA** ($5,661 \ge 5,0$; cartel con degradados y medios tonos que con $K=5$ supera el umbral) |
| `cma_1950_455.jpg` | `0.291` | **`2.261`** | **OK** ($< 5,0$) |
| `cma_1952_10.jpg` | `0.431` | **`3.046`** | **OK** ($< 5,0$) |
| `cma_1966_352.jpg` | `0.451` | **`2.492`** | **OK** ($< 5,0$) |
| `cma_1968_257.jpg` | `0.498` | **`6.464`** | **FALLA** ($6,464 \ge 5,0$; cartel policromático donde $K=5$ clústeres son insuficientes para bajar de $\Delta E_{2000} = 5$) |

### Código exacto de la comprobación (listo para integrar en `medir.py` tras la revisión):
```python
def comprobar_fidelidad_cromatica_real(ruta_img: Path, umbral_de00: float = 5.0) -> dict:
    lienzo = cargar_referente(ruta_img, max_dim_analisis=160)
    est = estudiar_referente(ruta_img, max_dim_analisis=160)
    centroides_srgb_lab = []
    for c in est["paleta"]["colores"]:
        lab_c = (c["lab"]["L"], c["lab"]["a"], c["lab"]["b"])
        r_u8, g_u8, b_u8 = lab_a_srgb_u8(*lab_c)
        centroides_srgb_lab.append(srgb_a_lab(r_u8, g_u8, b_u8))

    pxs = [px for fila in lienzo.pixeles_lab for px in fila]
    errores_px = [
        min(delta_e2000(px, c_rt) for c_rt in centroides_srgb_lab)
        for px in pxs
    ]
    de_medio = sum(errores_px) / max(1, len(errores_px))
    return {
        "archivo": ruta_img.name,
        "delta_e2000_medio_píxeles_vs_paleta_srgb": round(de_medio, 3),
        "pasa_umbral_5": de_medio < umbral_de00,
    }
```

---

## 3. ¿La rama nació de `origin/studio/collage` o es una historia nueva (`git init`)?

**Respuesta honesta: Es una historia nueva (`git init` con commit raíz `546f18e`).**

* **Motivo:** El repositorio `https://github.com/brune6320-del/prometeo-studio.git` es privado y el sandbox de ejecución en esta sesión no tiene credenciales de GitHub (`fatal: could not read Username for 'https://github.com': Device not configured`), por lo que no existía clon previo en `~/Projects/` ni fue posible ejecutar `git clone` / `git fetch` desde dentro del sandbox.
* **Salida actual de `git log --oneline -3 --graph` en local:**
  ```text
  * ec366d8 D-11 Parte 4: medir.py (pares sintéticos y cambio de contenido) y colab.ipynb autocontenido
  * d461655 D-11 Parte 3: aplicar.py — propuesta no destructiva de paleta Lab, retícula y jerarquía sobre tablero.json
  * e4db490 D-11 Parte 2: Motor de estudio de ADN de diseño (Lab + ΔE2000, composición, saliencia)
  ```
  *(Y un commit más abajo está el commit raíz `546f18e D-11 Parte 1: Contrato de salida estable ESQUEMA.md y validador esquema.py (v1.0.0)`).*

* **Qué ocurrirá cuando Bruno haga `git fetch origin` y ejecute `git merge-base HEAD origin/studio/collage`:**
  * Antes de rebasar, `git merge-base HEAD origin/studio/collage` devolverá **vacío (exit code 1)** porque `546f18e` es un commit raíz independiente.
  * Para injertar limpiamente los commits de `studio/adn-diseno` sobre `origin/studio/collage` antes del push para que compartan ancestro común (`merge-base == origin/studio/collage`), Bruno solo tiene que ejecutar en su terminal:
    ```bash
    cd /Users/gladys/.gemini/users/user1/Projects/prometeo-adn-diseno
    git fetch origin
    git rebase --onto origin/studio/collage --root studio/adn-diseno
    git log --oneline -3 --graph
    git merge-base HEAD origin/studio/collage
    git push -u origin studio/adn-diseno
    ```

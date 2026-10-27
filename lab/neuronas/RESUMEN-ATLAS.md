# FASE 5b y 5c · Atlas con prueba de verdad (`features.7` vs `features.5`) y Prueba Ciega Humana

## 1. Comparativa de capas: `features.5` (Etapa 3, 384 canales, $14 \times 14$) vs `features.7` (Etapa 4, 768 canales, $7 \times 7$)

En **FASE 5c** (`prerregistro_v3.json` sellado en `53aa6c3` antes de mirar las activaciones de `features.5`, dejando intactos `v1` y `v2`), evaluamos `200` neuronas al azar (`SEED = 2610`) de la capa media `features.5` sobre el mismo corpus de `630` obras CC0 (`441` `train` / `189` `validacion`) con los mismos umbrales (`a`: apagado $\ge 2\times$ control en $\ge 4/5$ sorteos; `b`: $\text{ROC AUC}_{\text{val}} \ge 0{,}70$ puntuando de `0` a `3` solo con la etiqueta escrita). Además, en `features.5` eliminamos por completo los términos de catálogo de museo («escultura», «cerámica», «grabado») para que las etiquetas expresen **exclusivamente verbos visuales y compositivos de diseño** (claroscuro, temperatura cromática, saturación, trama lineal, orientación vertical/horizontal, aislamiento central vs sangrado):

| Métrica (`N = 200` neuronas por capa, `SEED = 2610`) | `features.5` (Capa media, 384 canales, $14 \times 14$) | `features.7` (Última etapa, 768 canales, $7 \times 7$) | Diferencia (`features.5` − `features.7`) |
|---|---:|---:|---:|
| **Neuronas LEGIBLES (pasan `a` y `b`)** | **32 / 200 (`16,00 %`)**<br>IC 95 %: `[11,57 %, 21,71 %]` | **26 / 200 (`13,00 %`)**<br>IC 95 %: `[9,03 %, 18,37 %]` | **`+3,00 pp`** (`+6` neuronas) |
| **Pasan SOLO `a` (`confirmada_a = true`, `confirmada_b = false`)** | **50 / 200 (`25,00 %`)**<br>IC 95 %: `[19,51 %, 31,43 %]` | **112 / 200 (`56,00 %`)**<br>IC 95 %: `[49,07 %, 62,70 %]` | **`-31,00 pp`** (`-62` neuronas) |
| **Pasan SOLO `b` (`confirmada_a = false`, `confirmada_b = true`)** | **22 / 200 (`11,00 %`)**<br>IC 95 %: `[7,38 %, 16,09 %]` | **12 / 200 (`6,00 %`)**<br>IC 95 %: `[3,47 %, 10,19 %]` | **`+5,00 pp`** (`+10` neuronas) |
| No pasan ni `a` ni `b` | 96 / 200 (`48,00 %`)<br>IC 95 %: `[41,18 %, 54,90 %]` | 50 / 200 (`25,00 %`)<br>IC 95 %: `[19,51 %, 31,44 %]` | `+23,00 pp` |
| *Total que pasan Prueba `a` (efecto causal en logits)* | *82 / 200 (`41,00 %`)*<br>IC 95 %: `[34,42 %, 47,92 %]` | *138 / 200 (`69,00 %`)*<br>IC 95 %: `[62,28 %, 75,00 %]` | *`-28,00 pp`* |
| *Total que pasan Prueba `b` (predicción ciega $\text{AUC}_{\text{val}} \ge 0{,}70$)* | *54 / 200 (`27,00 %`)*<br>IC 95 %: `[21,32 %, 33,54 %]` | *38 / 200 (`19,00 %`)*<br>IC 95 %: `[14,17 %, 25,00 %]` | *`+8,00 pp`* |
| *Declaradas `«no lo sé»` (sin patrón claro en `train`)* | *49 / 200 (`24,50 %`)* | *63 / 200 (`31,50 %`)* | *`-7,00 pp`* |

### Lectura metodológica del contraste `features.5` vs `features.7`
1. **Evaluación de la hipótesis de la Parte 1:** La estimación puntual en `features.5` (**`16,00 %`**, `32/200`) supera el `13,00 %` (`26/200`) de `features.7` en `+3,0` puntos porcentuales, aunque los intervalos de confianza al 95 % (`[11,57 %, 21,71 %]` frente a `[9,03 %, 18,37 %]`) se solapan ampliamente y ambas capas quedan muy lejos del `~90 %` preliminar de Cammarata (2026, Qwen3-32B).
2. **Inversión entre selectividad causal (`a`) y descriptibilidad visual (`b`):**
   - En `features.5`, la **Prueba `b`** sube del `19,00 %` al **`27,00 %` (`54/200`)** usando únicamente propiedades visuales de diseño (sin tipos de objeto de museo), y las neuronas sin patrón claro (`«no lo sé»`) bajan de `63` a `49`. Es decir, la capa media sí responde con mayor limpieza a verbos visuales (claroscuro, temperatura cálida/fría, trama lineal, aislamiento central).
   - En cambio, la **Prueba `a`** baja del `69,00 %` en `features.7` al **`41,00 %` en `features.5`**, porque al apagar un solo canal en la etapa 3 la señal atraviesa todavía el *downsampling* `features.6` y los 3 bloques residuales de `features.7`, que amortiguan parte del impacto individual sobre los 1000 logits finales.

## 2. Cinco ejemplos legibles de `features.5`

Mosaicos locales fuera de Git en `/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/neuronas-mosaicos/5_ejemplos_f5/`:

| # | Neurona (`features.5`) | Prueba `a` (sorteos / ratio) | Prueba `b` ($\text{AUC}_{\text{val}}$) | Etiqueta libre en `train` (100 % verbos visuales de diseño) | Mosaico local (fuera de Git) |
|---:|---|---:|---:|---|---|
| 1 | `neurona_f5_360` | `5/5` (`3,91x`) | **`0,8676`** | Responde a sombras profundas de claroscuro, vegetación en tonos verde musgo y celadón y riqueza cromática de pigmento vivo frente a luminosidad general alta, grano fino continuo sobre plano homogéneo y fondo crema envejecido. | `ejemplo_f5_01_neurona_f5_360.png` (`f2c755a2...`) |
| 2 | `neurona_f5_180` | `5/5` (`6,23x`) | **`0,8432`** | Responde a dominante térmica cálida rojiza, soporte cálido marfil y pergamino y paleta dorada y ámbar frente a dominante térmica fría azulada, tonos pizarra oscuros de baja luz y arquitectura compositiva de grandes planos. | `ejemplo_f5_02_neurona_f5_180.png` (`149b805a...`) |
| 3 | `neurona_f5_126` | `5/5` (`2,96x`) | **`0,8429`** | Responde a trama tupida de líneas finas, grano fino continuo sobre plano homogéneo y estrías y pliegues de caída vertical frente a contorno anular de plato o vasija redonda, color concentrado en el centro rodeado de borde apagado y figura exenta en el centro del encuadre. | `ejemplo_f5_03_neurona_f5_126.png` (`d3ee139a...`) |
| 4 | `neurona_f5_063` | `5/5` (`2,62x`) | **`0,8349`** | Prefiere núcleo policromo sobre margen neutro y escala acromática de tintas grises y negras acompañados de temperatura de color fría contra composiciones con dominante térmica cálida rojiza, correspondencia tonal entre mitad superior e inferior y manchas carmesí y bermellón. | `ejemplo_f5_04_neurona_f5_063.png` (`cfab4d74...`) |
| 5 | `neurona_f5_355` | `5/5` (`4,19x`) | **`0,8265`** | Se activa ante grano fino continuo sobre plano homogéneo combinados con achurado minucioso de alta frecuencia y contornos estructurales definidos en contraste con piezas de superficies lisas sin grano con encuadre rectilíneo de líneas rectas finas y foco circular centrado. | `ejemplo_f5_05_neurona_f5_355.png` (`e46ff987...`) |

## 3. Prueba ciega humana para Bruno (20 pares)

- **Página HTML única autocontenida (sin internet):** `/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/prueba-ciega-bruno/prueba_ciega_20_pares.html` (`sha256 = 9317c53f430f2b3c19df1ca17de6922d9057bab744fd55f7dc55c6d361fc4110`)
- **Clave secreta de corrección (Bruno NO la abre):** `/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/prueba-ciega-bruno/clave_secreta_no_abrir.json` (`sha256 = 02a6b30c0d5c2e70f32dd5c1efdcd60d56120686684c20fbe53f4588f2f96cf2`)
- **Script evaluador:** `lab/neuronas/evaluar_prueba_ciega.py` (compara `respuestas_bruno_20_pares.json` con la clave secreta y verifica si acierta $\ge 15/20$, $p = 0{,}02069 < 0{,}05$).

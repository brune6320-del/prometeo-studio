# FASE 5b · Atlas con prueba de verdad (N-1 v2 · ConvNeXt-tiny `features.7`)

## 1. Corrección de las tres fallas metodológicas de la Fase 5

| Falla señalada en Fase 5 | Corrección aplicada en Fase 5b (`prerregistro_v2.json` sellado en `4ac4cd3`) |
|---|---|
| **1. Apagado tautológico** (`control-9` con caída `0,0000` y ratio `>99,9x`) | **Prueba (a) — Apagado con control justo**: sobre las **mismas `top-9` imágenes de `train`** de la neurona $X$, se mide el cambio $L_2$ en los 1000 logits del clasificador al apagar $X$ frente a apagar cada una de **5 neuronas control $Y_1\dots Y_5$** sorteadas al azar (`SEED = 2610 + X`) entre las 25 neuronas con **activación media absoluta más parecida en `train`**. Pasa (`confirmada_a = true`) si $E(X) \ge 2{,}0 \times E(Y_m)$ en al menos **4 de 5** sorteos. |
| **2. Etiquetas de plantilla rígida** (`6 ejes fijos`, colisiones como `113 = 196`) | **Etiquetas libres en español natural**: redactadas observando únicamente el conjunto `train` (`441` imágenes), sin plantilla repetida (`137/137` etiquetas con contenido son **100 % únicas**). Cuando en `train` no se aprecia separación visual clara ($\text{AUC}_{\text{train}} < 0{,}64$), se escribe honestamente **`«no lo sé»`** (`63/200` neuronas), que cuenta como no legible. |
| **3. Corpus insuficiente** (`22` imágenes frente a `768` canales) | **Corpus ampliado a `630` imágenes CC0 verificadas** (`lab/neuronas/corpus_cc0_630.json`, SHA-256 `f0c3483f...`) descargadas de las APIs Open Access del **Cleveland Museum of Art (CMA)** (`565`) y **The Metropolitan Museum of Art (Met)** (`59`) más `6` piezas CC0 de D-3, mezclando pintura (`168`), grabados (`154`), objetos tridimensionales (`130`), fotografía (`120`) y carteles/obra gráfica (`58`). Split aleatorio (`SEED = 2610`): **`441` `train` (70 %)** y **`189` `validacion` (30 % ciego)**. |

## 2. Resultados globales sobre las 200 neuronas (`SEED = 2610`)

*Nota sobre la referencia bibliográfica:* El **~90 % preliminar** citado por Nick Cammarata corresponde a su ensayo de **2026 sobre Qwen3-32B** (no a la serie *Circuits* de *Distill* 2020). En `ConvNeXt-tiny` (`features.7`, 768 canales convolucionales entrenados en ImageNet-1k) evaluado con pruebas no tautológicas sobre un corpus artístico multicanal de 630 obras CC0, la fracción de neuronas simultáneamente selectivas en apagado causal y predecibles a ciegas por un humano/etiquetador desde una etiqueta breve es sustancialmente menor:

| Categoría de resultado | Conteo (`/ 200`) | Porcentaje | IC 95 % (Wilson score) |
|---|---:|---:|---:|
| **Neuronas LEGIBLES (pasan `a` y `b`)** | **26 / 200** | **13,00 %** | **`[9,03 %, 18,37 %]`** |
| **Pasan SOLO `a` (`confirmada_a = true`, `confirmada_b = false`)** | **112 / 200** | **56,00 %** | **`[49,07 %, 62,70 %]`** |
| **Pasan SOLO `b` (`confirmada_a = false`, `confirmada_b = true`)** | **12 / 200** | **6,00 %** | **`[3,47 %, 10,19 %]`** |
| No pasan ni `a` ni `b` | 50 / 200 | 25,00 % | `[19,51 %, 31,44 %]` |
| *Total que pasan `a` (Apagado con control justo $\ge 4/5$)* | *138 / 200* | *69,00 %* | *`[62,28 %, 75,00 %]`* |
| *Total que pasan `b` (Predicción ciega en validación $\text{AUC} \ge 0{,}70$)* | *38 / 200* | *19,00 %* | *`[14,17 %, 25,00 %]`* |
| *Declaradas «no lo sé» (sin patrón visual claro en `train`)* | *63 / 200* | *31,50 %* | *`[25,46 %, 38,24 %]`* |

## 3. Diez ejemplos (5 legibles y 5 no legibles)

Los 10 mosaicos (`polo +` frente a `polo −` en `train`) están guardados localmente fuera de Git en `/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/neuronas-mosaicos/10_ejemplos_v2/`:

| # | Neurona | Estado | Prueba `a` (sorteos / ratio medio) | Prueba `b` ($\text{AUC}_{\text{val}}$) | Etiqueta libre escrita desde `train` | Mosaico local (fuera de Git) |
|---:|---|---|---:|---:|---|---|
| 1 | `neurona_421` | **LEGIBLE (`a` y `b`)** | `5/5` (`4,15x`) | **`0,8351`** | Se activa ante tallas tridimensionales, bustos y relieves en metal o piedra combinados con artefactos escultóricos o cerámicos fotografiados en estudio y núcleo policromo sobre margen neutro —por ejemplo «Zaō Gongen»— en contraste con piezas de cielo luminoso sobre base oscura con positivos fotográficos de cámara con grano óptico y xilografías, litografías y grabados calcográficos. | `ejemplo_01_legible_neurona_421.png` (`11bae6e4...`) |
| 2 | `neurona_694` | **LEGIBLE (`a` y `b`)** | `4/5` (`2,77x`) | **`0,8185`** | Concentra su activación en objetos exentos con volumen físico, figuras escultóricas de bulto redondo y núcleo policromo sobre margen neutro, destacando «Shell with Seated Noble» oponiéndose a pinturas al óleo o temple sobre lienzo y tabla junto con cabecera clara con tercio inferior sombreado y riqueza cromática de pigmento vivo. | `ejemplo_02_legible_neurona_694.png` (`79ebdff3...`) |
| 3 | `neurona_542` | **LEGIBLE (`a` y `b`)** | `4/5` (`3,18x`) | **`0,8104`** | Detecta artefactos escultóricos o cerámicos fotografiados en estudio junto a núcleo policromo sobre margen neutro además de recipientes de cerámica vidriada y alfarería, visible en «Black-Figure Neck-Amphora (Storage Ves» mientras el polo opuesto reúne grabados, aguafuertes y estampas sobre papel asociados a claridad tonal elevada en toda la toma y gradiente vertical de cielo claro a tierra oscura. | `ejemplo_03_legible_neurona_542.png` (`6075b451...`) |
| 4 | `neurona_299` | **LEGIBLE (`a` y `b`)** | `4/5` (`2,74x`) | **`0,8019`** | Reacciona a gradiente vertical de cielo claro a tierra oscura con franjas anchas de composición horizontal y positivos fotográficos de cámara con grano óptico (caso de «The Bridge of Palalda (near Amelieles-»); en el extremo negativo aparecen escenas de equilibrio simétrico arriba-abajo, diferencia marcada de luz entre disco interno y periferia y formato vertical dominante. | `ejemplo_04_legible_neurona_299.png` (`db25edab...`) |
| 5 | `neurona_428` | **LEGIBLE (`a` y `b`)** | `5/5` (`2,71x`) | **`0,8019`** | Detecta estructura tendida en planos horizontales junto a líneas horizontales de horizonte además de cabecera clara con tercio inferior sombreado, visible en «Nymphs and a Satyr (Amor Vincit Omnia)» mientras el polo opuesto reúne composición erguida en columnas verticales asociados a rayado vertical dominante y artefactos escultóricos o cerámicos fotografiados en estudio. | `ejemplo_05_legible_neurona_428.png` (`34a72d6a...`) |
| 6 | `neurona_198` | **NO LEGIBLE (solo `a`)** | `5/5` (`3,44x`) | `0,4811` | Responde a equilibrio simétrico arriba-abajo, grano fino continuo sobre plano homogéneo y formato vertical dominante (como en «The Crucifixion of Saint Andrew») frente a vasijas, cuencos y porcelanas cerámicas, positivos fotográficos de cámara con grano óptico y estructura tendida en planos horizontales. | `ejemplo_06_no_legible_neurona_198.png` (`1f7b0dd1...`) |
| 7 | `neurona_159` | **NO LEGIBLE (solo `a`)** | `5/5` (`2,91x`) | `0,4977` | Prefiere fotografías históricas en albúmina o plata y ejes verticales de figura de pie o pilastra acompañados de movimiento diagonal sin aristas rectas (ej. «Figure 54: Abaissement volontaire de l») contra composiciones con vasijas, cuencos y porcelanas cerámicas, objetos exentos con volumen físico y estructura tendida en planos horizontales. | `ejemplo_07_no_legible_neurona_159.png` (`3de74b90...`) |
| 8 | `neurona_113` | **NO LEGIBLE (solo `b`)** | `0/5` (`1,19x`) | **`0,7852`** | Reacciona a jarrones, platos y tazas de porcelana con piezas tridimensionales de museo en estudio y pieza concentrada en el núcleo con periferia calma (caso de «Fragment of a Wall Painting MET 135348»); en el extremo negativo aparecen escenas de dominante térmica cálida rojiza, obra gráfica impresa en tinta sobre papel y formato vertical dominante. | `ejemplo_08_no_legible_neurona_113.png` (`bb70ba40...`) |
| 9 | `neurona_090` | **NO LEGIBLE (`«no lo sé»`)** | `0/5` (`1,48x`) | `0,5000` | `no lo sé` | `ejemplo_09_no_legible_neurona_090.png` (`57f1ecf7...`) |
| 10 | `neurona_264` | **NO LEGIBLE (solo `a`, `«no lo sé»`)** | `4/5` (`1,77x`) | `0,5000` | `no lo sé` | `ejemplo_10_no_legible_neurona_264.png` (`282f4cf9...`) |

## 4. Verificación reproducible

```bash
.venv/bin/python lab/neuronas/medir_atlas.py
```
Pasa las **8/8 comprobaciones** (`prerregistro.json` v1 intacto, `prerregistro_v2.json` v2 intacto, `corpus_cc0_630.json` con 630 SHA-256 únicos y split 441/189, 200 fichas v2 completas con negativos preservados, 137/137 etiquetas con contenido únicas + 63 `«no lo sé»`, pruebas `a` y `b` verificadas y 0 imágenes/pesos en Git).

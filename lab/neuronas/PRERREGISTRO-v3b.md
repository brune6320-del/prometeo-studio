# PRERREGISTRO v3b · FASE 5d («El salón»: prueba de sensaciones con personas)

- **Fecha de sello (antes de generar la página de El Salón):** `2026-10-28`
- **Archivo JSON sellado:** `lab/neuronas/prerregistro_v3b.json` (`sha256 = 0d110469817fd5fff8ec8473adc0f587d7b5f2da2a1e14f06d06883b8084ecfa`)
- **Semilla nueva:** `SEED_SALON = 2810`
- **Prerregistros anteriores preservados intactos:**
  - `lab/neuronas/prerregistro.json` (`v1`, `sha256 = a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388`)
  - `lab/neuronas/prerregistro_v2.json` (`v2`, `sha256 = 729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555`)
  - `lab/neuronas/prerregistro_v3.json` (`v3`, `sha256 = 230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8`)

## 1. Idea central y reglas de diseño selladas

> *Si una neurona de verdad «ve» algo, la gente normal debería sentir esa diferencia entre lo que más la enciende y lo que menos, sin que nadie le diga qué es.*

1. **Exclusión de neuronas ya vistas por Bruno en 5c (Regla 6):** Quedan excluidas las 20 neuronas reales del sorteo de 5c (`neurona_078`, `105`, `193`, `294`, `387`, `421`, `479`, `f5_013`, `f5_126` [par 9], `f5_165` [par 13 señuelo], `f5_197`, `f5_224`, `f5_244` [par 13], `f5_275`, `f5_301`, `f5_311`, `f5_330`, `f5_352`, `f5_355`, `f5_360`) más el señuelo del par 9 (`f5_214`). Las 38 neuronas legibles restantes se reparten sin solapamiento entre la Parte 1 (`12` pares), la Parte 2 (`20` pares) y la Parte 3 (`6` pares).
2. **Contraste real y umbral de color CIE Lab (Regla 3):**
   - Cada par enfrenta las **9 imágenes de `train` que MÁS activan la neurona (`polo_pos`)** con las **9 imágenes que MENOS la activan (`polo_neg`)**, mostradas como miniaturas completas ($224 \times 224$) en cuadrícula $3 \times 3$.
   - Umbral de contraste cromático: **$\Delta E_{ab} = 10{,}0$** en CIE $L^*a^*b^*$ entre el color medio de las 9 imágenes de `polo_pos` y las 9 de `polo_neg`.
   - Si una neurona tiene **$\Delta E_{ab} < 10{,}0$**, queda **prohibido** asignarle un eje de color o luz; solo puede usarse para ejes espaciales o estructurales no cromáticos (`recto / curvo`, `agitado / tranquilo`, `lejano / cercano`).
3. **Lenguaje de calle (Regla 2):**
   - Máximo **12 palabras** por pregunta (`7` palabras en todas las preguntas de la Parte 2: *«¿Cuál de los dos se siente más ___?»*), una sola idea.
   - **Palabras estrictamente prohibidas (`0` apariciones):** `claroscuro`, `celadón`, `tondo`, `exenta`, `policromo`, `acromática`, `achurado`, `encuadre`, `periferia`, `perímetro`, `cerámica`, `pigmento`, `soporte`, `frente a`.
4. **Controles de azar (Regla 4) y de atención (Regla 5):**
   - **4 pares de control al azar:** dos mosaicos $3 \times 3$ elegidos al azar en `train` (neurona inventada), con lado «predicho» ficticio equilibrado (`2` izquierda, `2` derecha). El acierto humano esperado es $\approx 50\ \%$; sirve para detectar sesgos de posición.
   - **2 pares de atención obvios:** `9` imágenes muy oscuras ($L^* < 18$) contra `9` imágenes muy claras ($L^* > 78$), equilibrados (`1` izquierda, `1` derecha). Quien falle los **2** pares de atención queda excluido del análisis.

## 2. Tabla de las 20 neuronas y ejes de sensación de la Parte 2 (`Sentir`)

Posición del lado predicho (`polo_pos`) sorteada con `SEED_SALON = 2810` y equilibrada exactamente (`10` izquierda, `10` derecha):

| # | Neurona | Etapa | $\Delta E_{ab}$ (Lab) | $\Delta L^*$ | $\Delta b^*$ | Eje de sensación (calle) | Pregunta ($\le 12$ palabras) | Lado que más activa (`polo_pos`) |
|---:|---|---|---:|---:|---:|---|---|---|
| 1 | `neurona_f5_025` | `features.5` | `29,62` | `-29,10` | `-4,85` | `oscuro / luminoso` | ¿Cuál de los dos se siente más oscuro? | `derecha` |
| 2 | `neurona_f5_180` | `features.5` | `28,29` | `+22,95` | `+15,47` | `cálido / frío` | ¿Cuál de los dos se siente más cálido? | `izquierda` |
| 3 | `neurona_727` | `features.7` | `25,70` | `+25,37` | `+3,95` | `ligero / pesado` | ¿Cuál de los dos se siente más ligero? | `izquierda` |
| 4 | `neurona_599` | `features.7` | `24,83` | `+24,74` | `+1,59` | `luminoso / oscuro` | ¿Cuál de los dos se siente más luminoso? | `derecha` |
| 5 | `neurona_f5_155` | `features.5` | `22,38` | `+22,34` | `-0,03` | `suave / áspero` | ¿Cuál de los dos se siente más suave? | `derecha` |
| 6 | `neurona_f5_362` | `features.5` | `21,57` | `-21,42` | `-2,49` | `encerrado / abierto` | ¿Cuál de los dos se siente más encerrado? | `derecha` |
| 7 | `neurona_f5_221` | `features.5` | `18,70` | `-17,94` | `-4,89` | `cercano / lejano` | ¿Cuál de los dos se siente más cercano? | `izquierda` |
| 8 | `neurona_f5_137` | `features.5` | `18,19` | `-16,65` | `-7,13` | `tranquilo / agitado` | ¿Cuál de los dos se siente más tranquilo? | `derecha` |
| 9 | `neurona_f5_332` | `features.5` | `17,56` | `-17,05` | `+4,05` | `colorido / apagado` | ¿Cuál de los dos se siente más colorido? | `derecha` |
| 10 | `neurona_374` | `features.7` | `17,17` | `-16,80` | `-3,49` | `pesado / ligero` | ¿Cuál de los dos se siente más pesado? | `izquierda` |
| 11 | `neurona_f5_178` | `features.5` | `15,89` | `+14,49` | `-5,60` | `apagado / colorido` | ¿Cuál de los dos se siente más apagado? | `izquierda` |
| 12 | `neurona_f5_143` | `features.5` | `14,95` | `-12,30` | `+8,25` | `antiguo / nuevo` | ¿Cuál de los dos se siente más antiguo? | `derecha` |
| 13 | `neurona_f5_285` | `features.5` | `13,89` | `+13,10` | `+4,54` | `ordenado / caótico` | ¿Cuál de los dos se siente más ordenado? | `izquierda` |
| 14 | `neurona_428` | `features.7` | `13,51` | `+12,77` | `+3,39` | `abierto / encerrado` | ¿Cuál de los dos se siente más abierto? | `derecha` |
| 15 | `neurona_760` | `features.7` | `13,39` | `-13,03` | `-3,08` | `vacío / lleno` | ¿Cuál de los dos se siente más vacío? | `izquierda` |
| 16 | `neurona_542` | `features.7` | `13,12` | `-12,37` | `-3,90` | `sólido / plano` | ¿Cuál de los dos se siente más sólido? | `derecha` |
| 17 | `neurona_f5_063` | `features.5` | `11,54` | `+0,94` | `-11,50` | `frío / cálido` | ¿Cuál de los dos se siente más frío? | `izquierda` |
| 18 | `neurona_323` | `features.7` | `10,69` | `+10,49` | `+2,04` | `recto / curvo` | ¿Cuál de los dos se siente más recto? | `izquierda` |
| 19 | `neurona_f5_274` | `features.5` | `7,91` | `+7,66` | `-1,13` | `agitado / tranquilo` *(no color)* | ¿Cuál de los dos se siente más agitado? | `derecha` |
| 20 | `neurona_299` | `features.7` | `3,36` | `-1,76` | `-2,04` | `lejano / cercano` *(no color)* | ¿Cuál de los dos se siente más lejano? | `izquierda` |

## 3. Plan de análisis estadístico (Regla 8) y ética (Regla 9)

1. **Filtro de calidad de atención:** Se descartan únicamente los cuestionarios donde el participante falle **ambos** pares de atención obvios (`0/2` en atención). Mínimo `6` participantes válidos (ideal `10`), mezclando personas con experiencia en diseño/arte (`sí`) y fuera de él (`no`).
2. **Por neurona ($j = 1 \dots 20$):**
   - Sea $k_j$ el número de participantes válidos (de $N$) que eligen el lado predicho por la neurona (`polo_pos`).
   - Se calcula la proporción $\hat{p}_j = k_j / N$ y el $p$-valor exacto unilateral de la prueba binomial bajo $H_0: p_j = 0{,}5$:
     $$p_j = \sum_{m = k_j}^{N} \binom{N}{m} 0{,}5^N$$
   - Se aplica la corrección escalonada de **Holm-Bonferroni** sobre la familia de $M = 20$ neuronas: ordenando $p_{(1)} \le p_{(2)} \le \dots \le p_{(20)}$, el $p$-valor ajustado es $\tilde{p}_{(r)} = \min\bigl(1,\; \max_{s \le r} (20 - s + 1)\,p_{(s)}\bigr)$.
   - **Criterio de confirmación («la neurona se siente»):** $\hat{p}_j \ge 0{,}70$ (70 %) **y** $\tilde{p}_j < 0{,}05$.
3. **Análisis global y controles:**
   - Acierto medio en las 20 neuronas reales frente al azar ($50\ \%$) mediante prueba binomial agregada y prueba $t$ / Wilcoxon por participante.
   - Comparación directa del acierto medio en las 20 neuronas reales frente al acierto medio en los **4 pares de control al azar** (y comprobación de sesgo lateral izquierda/derecha en los controles).
   - Desglose estratificado: acierto medio en participantes con `trabaja_en_diseno_o_arte = sí` frente a `no`.
4. **Alimentación de N-2 y D-8 (Parte 4 · Gusto):** Conteo de toques ♥ y ✕ por imagen (`id_pieza`, `sha256`) para desbloquear N-2 y D-8 cuando Bruno acumule $\ge 20$ ♥.

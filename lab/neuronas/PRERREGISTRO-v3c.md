# PRERREGISTRO v3c · FASE 5d (Visto bueno condicional de Claude a «El salón»)

- **Fecha de sello (antes de que responda una sola persona y antes de regenerar la página):** `2026-10-28`
- **Archivo JSON sellado:** `lab/neuronas/prerregistro_v3c.json` (`sha256 = 90e0aa75132c4742bf6dac453dc3f830e39f8748b8e71e394b43d8487ea11bd5`)
- **Prerregistros anteriores preservados intactos:**
  - `lab/neuronas/prerregistro.json` (`v1`, `sha256 = a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388`)
  - `lab/neuronas/prerregistro_v2.json` (`v2`, `sha256 = 729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555`)
  - `lab/neuronas/prerregistro_v3.json` (`v3`, `sha256 = 230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8`)
  - `lab/neuronas/prerregistro_v3b.json` (`v3b`, `sha256 = 0d110469817fd5fff8ec8473adc0f587d7b5f2da2a1e14f06d06883b8084ecfa`)

## Tres cambios sellados del visto bueno condicional de Claude

### 1. Control de brillo («el más claro o el más oscuro»)
En `lab/neuronas/analizar_salon.py`, para cada par $j \in \{1\dots 20\}$ de la Parte 2:
- Se identifica cuál de los dos polos (`polo_pos` o `polo_neg`) es **el más claro** ($\Delta L^*_j \ge 0$) y cuál es **el más oscuro** ($\Delta L^*_j < 0$).
- Se calcula qué elegiría un observador que **solo mire «el más claro o el más oscuro»**:
  1. Para cada participante válido se mide su tasa empírica global de elegir el mosaico más claro ($q_{\text{claro}}$) y el más oscuro ($q_{\text{oscuro}} = 1 - q_{\text{claro}}$) en los pares que no son de brillo puro (`18` pares), lo que determina la predicción esperada de la regla simple de brillo en el par $j$:
     $$\text{acierto\_regla\_simple\_brillo}_j = \begin{cases} 100\,\% & \text{si el eje es de brillo puro («oscuro / luminoso» o «luminoso / oscuro»)} \\ \max\bigl(\bar{q}_{\text{polo}}(j),\; 50\,\% + 50\,\%\cdot\min(1, |\Delta L^*_j|/35{,}0)\bigr) & \text{en los otros 18 ejes} \end{cases}$$
     donde $\bar{q}_{\text{polo}}(j) = \bar{q}_{\text{claro}}$ si `polo_pos` es más claro y $\bar{q}_{\text{oscuro}}$ si `polo_pos` es más oscuro.
  2. Se reporta explícitamente `lado_mas_claro`, `lado_mas_oscuro`, `acierto_regla_simple_brillo_pct` y `supera_regla_brillo` ($\text{acierto\_humano}_j > \text{acierto\_regla\_simple\_brillo}_j$).
- **Criterio de «se siente de verdad» (`se_siente_de_verdad = true`):**
  $$\text{acierto\_humano}_j \ge 70{,}0\,\% \quad\wedge\quad p_{\text{Holm}, j} < 0{,}05 \quad\wedge\quad \text{supera\_regla\_brillo}_j = \text{true}$$
  (Las 2 neuronas cuyo eje es literalmente brillo —`oscuro / luminoso` y `luminoso / oscuro`— sirven como calibración del control de brillo y no pueden superar a una regla que mira solo brillo; las neuronas que de verdad «se sienten» más allá del brillo salen de las otras 18).

### 2. Sorteo de izquierda y derecha por persona (semilla desde el `apodo`)
- Cuando cada participante escribe su `apodo` en la Parte 0, la página calcula una semilla entera determinista de 32 bits a partir de `apodo.trim().toLowerCase()` (hash FNV-1a sumado a la semilla base `2810`) e inicializa un generador PRNG `mulberry32`.
- Con esa semilla personal se barajan vectores equilibrados de posición (`10` izquierda / `10` derecha en las 20 neuronas de la Parte 2; `2/2` en los 4 controles al azar; `1/1` en los 2 controles de atención; `6/6` en la Parte 1; `3/3` en la Parte 3). Así, dos personas sentadas cerca ven lados distintos en sus pantallas, pero cada persona mantiene un equilibrio exacto 50/50 entre izquierda y derecha.
- En el JSON descargado (`salon_respuesta_<apodo>.json`), cada ítem guarda explícitamente:
  - `semilla_apodo`,
  - `lado_polo_pos_mostrado` (`"izquierda"` o `"derecha"`),
  - `sha256_mostrado_izquierda` y `sha256_mostrado_derecha`,
  - `eleccion` (`"izquierda"` o `"derecha"`).

### 3. Separación estricta de los ♥ de Bruno frente a los demás (Parte 4)
- Los ♥ marcados en la Parte 4 **solo cuentan para desbloquear y alimentar N-2 y D-8 si `apodo.strip().lower() == "bruno"`**, guardándose en `corazones_bruno_n2_d8.json`.
- Los ♥ marcados por todos los demás participantes (`apodo != "bruno"`) se guardan y resumen en un archivo separado (`corazones_otros_participantes.json`) y nunca se mezclan con el vector de gusto personal de Bruno.

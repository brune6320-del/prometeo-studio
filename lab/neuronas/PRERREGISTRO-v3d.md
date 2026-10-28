# PRERREGISTRO v3d (con ENMIENDA v3d.1) · FASE 5d («El salón»: Parte 1, botón «Ninguno» y 20 indicaciones de director)

- **Fecha de sello (ANTES de regenerar la página HTML):** `2026-10-28`
- **Archivo JSON sellado (`v3d.1`):** `lab/neuronas/prerregistro_v3d.json` (`sha256 = a857ecf0b6644d825dc986ab312bbcf3a8ca54c4d8eb988cba63f4f7a8234ad4`)
- **Versión previa `v3d.0` en historial Git:** commit `00b4917` (`sha256 json = aee44989f98509a52f3f9583c127f18f2b8cfeb8d89d823ac66ef78426e81384`)
- **Prerregistros anteriores preservados intactos:**
  - `lab/neuronas/prerregistro.json` (`v1`, `sha256 = a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388`)
  - `lab/neuronas/prerregistro_v2.json` (`v2`, `sha256 = 729bb150cc75e50e9ec5d2e43145f5e4d8876aa7119cc9b639f336d8c9ca1555`)
  - `lab/neuronas/prerregistro_v3.json` (`v3`, `sha256 = 230303d5388312ef30652ae09c97a1aef3ecd1ec647db0db58f07599371b78a8`)
  - `lab/neuronas/prerregistro_v3b.json` (`v3b`, `sha256 = 0d110469817fd5fff8ec8473adc0f587d7b5f2da2a1e14f06d06883b8084ecfa`)
  - `lab/neuronas/prerregistro_v3c.json` (`v3c`, `sha256 = 90e0aa75132c4742bf6dac453dc3f830e39f8748b8e71e394b43d8487ea11bd5`)

## 1. Tres cambios sellados en `v3d` y ENMIENDA `v3d.1`

1. **Parte 1 (Primer golpe de vista, 5 s):**
   - Pregunta en pantalla: **«¿Cuál te llamó más la atención?»**
   - Subtítulo debajo: **«No hay respuesta correcta: elige por instinto»**
2. **Tercer botón central en Partes 1 y 2 («Ninguno / se sienten igual»):**
   - Entre «Izquierda» y «Derecha» se añade un tercer botón central: **«Ninguno / se sienten igual»** (`eleccion = "ninguno"`).
   - **Regla de análisis conservadora (`analizar_salon.py`):** toda respuesta `"ninguno"` entra en el denominador $N$ de participantes válidos y cuenta como **NO acierto** (`0` aciertos para la neurona). Se informa explícitamente el porcentaje de `«Ninguno / se sienten igual»` por cada una de las 20 neuronas, en la Parte 1 y en los 4 controles al azar.
3. **Indicaciones de director en la Parte 2 (Sentir) con ENMIENDA `v3d.1` de Claude:**
   - Debajo de cada pregunta de la Parte 2 aparece una indicación de director de **máximo 12 palabras**, concreta, que aclara que se juzga **a la vista** y no por el tema representado, sin ninguna palabra prohibida.
   - **ENMIENDA `v3d.1` tras la revisión de Claude (antes de regenerar la página):**
     - **#2 (`cálido`):** `«cálido: predominan rojos, naranjas y amarillos, sin importar el tema»` (`10` palabras; evita la palabra «sol» que invitaba a buscar un sol literal).
     - **#10 (`pesado`):** `«pesado: masas grandes y oscuras que cargan la imagen hacia abajo»` (`11` palabras; evita «costara moverlo» que hacía pensar en el peso físico del objeto).
     - **#12 (`antiguo`):** `«antiguo: textura gastada y color amarillento, no por el objeto»` (`10` palabras).
     - Las otras 17 indicaciones quedan idénticas a `v3d.0`.

## 2. Las 20 indicaciones de director definitivas (`v3d.1`)

| # | Neurona | Eje de sensación | Pregunta | Indicación de director (`v3d.1`, $\le 12$ palabras) | Palabras |
|---:|---|---|---|---|---:|
| 1 | `neurona_f5_025` | `oscuro / luminoso` | ¿Cuál de los dos se siente más oscuro? | **oscuro: a simple vista domina la sombra, sin importar qué muestre** | `11` |
| 2 | `neurona_f5_180` | `cálido / frío` | ¿Cuál de los dos se siente más cálido? | **cálido: predominan rojos, naranjas y amarillos, sin importar el tema** | `10` |
| 3 | `neurona_727` | `ligero / pesado` | ¿Cuál de los dos se siente más ligero? | **ligero: a la vista parece liviano y aireado, casi sin peso** | `11` |
| 4 | `neurona_599` | `luminoso / oscuro` | ¿Cuál de los dos se siente más luminoso? | **luminoso: desprende más claridad y luz propia al primer vistazo** | `10` |
| 5 | `neurona_f5_155` | `suave / áspero` | ¿Cuál de los dos se siente más suave? | **suave: a la vista parece liso, como si no raspara nada** | `11` |
| 6 | `neurona_f5_362` | `encerrado / abierto` | ¿Cuál de los dos se siente más encerrado? | **encerrado: la vista queda atrapada adentro, sin salida hacia los bordes** | `11` |
| 7 | `neurona_f5_221` | `cercano / lejano` | ¿Cuál de los dos se siente más cercano? | **cercano: se ve tan próximo que parece al alcance de la mano** | `12` |
| 8 | `neurona_f5_137` | `tranquilo / agitado` | ¿Cuál de los dos se siente más tranquilo? | **tranquilo: a la vista transmite quietud y reposo, sin trazos bruscos** | `11` |
| 9 | `neurona_f5_332` | `colorido / apagado` | ¿Cuál de los dos se siente más colorido? | **colorido: los colores se ven vivos e intensos al primer golpe** | `11` |
| 10 | `neurona_374` | `pesado / ligero` | ¿Cuál de los dos se siente más pesado? | **pesado: masas grandes y oscuras que cargan la imagen hacia abajo** | `11` |
| 11 | `neurona_f5_178` | `apagado / colorido` | ¿Cuál de los dos se siente más apagado? | **apagado: a la vista luce grisáceo o descolorido, sin tonos vivos** | `11` |
| 12 | `neurona_f5_143` | `antiguo / nuevo` | ¿Cuál de los dos se siente más antiguo? | **antiguo: textura gastada y color amarillento, no por el objeto** | `10` |
| 13 | `neurona_f5_285` | `ordenado / caótico` | ¿Cuál de los dos se siente más ordenado? | **ordenado: a la vista las formas están alineadas en su sitio** | `11` |
| 14 | `neurona_428` | `abierto / encerrado` | ¿Cuál de los dos se siente más abierto? | **abierto: deja respirar la vista con espacio despejado a lo ancho** | `11` |
| 15 | `neurona_760` | `vacío / lleno` | ¿Cuál de los dos se siente más vacío? | **vacío: a la vista deja mucho fondo libre y despejado alrededor** | `11` |
| 16 | `neurona_542` | `sólido / plano` | ¿Cuál de los dos se siente más sólido? | **sólido: se ve con bulto y volumen firme a simple vista** | `11` |
| 17 | `neurona_f5_063` | `frío / cálido` | ¿Cuál de los dos se siente más frío? | **frío: sus tonos azules o grises se sienten frescos a la vista** | `12` |
| 18 | `neurona_323` | `recto / curvo` | ¿Cuál de los dos se siente más recto? | **recto: a simple vista mandan las líneas derechas y las esquinas** | `11` |
| 19 | `neurona_f5_274` | `agitado / tranquilo` | ¿Cuál de los dos se siente más agitado? | **agitado: se ven trazos revueltos y movidos que inquietan la vista** | `11` |
| 20 | `neurona_299` | `lejano / cercano` | ¿Cuál de los dos se siente más lejano? | **lejano: aleja la vista hacia el fondo, como mirado a distancia** | `11` |

*(Indicaciones de los 4 controles al azar: `sereno: a la vista transmite calma y silencio, sin tensión visual` [10 pal], `intenso: golpea más fuerte la vista por su fuerza y contraste` [10 pal], `liviano: parece flotar a la vista, sin manchas densas ni pesadas` [10 pal], `firme: se ve estable y bien plantado, sin formas que tiemblen` [10 pal]).*

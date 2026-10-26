# Resumen del Atlas Piloto de Neuronas · FASE 5 (N-1)

- **Rama:** `studio/neuronas-atlas` (creada desde `studio/adn-unido` @ `551bf2f1a78f161a2d99497eace590f27a7a6cf6`)
- **Modalidad:** `piloto_reducido` (`22` piezas del corpus D-3 en `~/Desktop/REFERENTES/corpus-editorial/muestras/`; las `442` fotos de Bruno aún no están en carpeta local).
- **Modelo:** `ConvNeXt-tiny` (`torchvision.models.convnext_tiny`, `28.589.128` parámetros).
- **Pesos:** `ConvNeXt_Tiny_Weights.IMAGENET1K_V1` (`https://download.pytorch.org/models/convnext_tiny-983f1562.pth`)
  - **SHA-256 verificado:** `983f1562536e84ff750a1576fb08e54de751dbf2e17c0d8a4a13704341fdcd3d`
  - **Licencia comprobada:** `BSD-3-Clause` (`pytorch/vision` LICENSE y `CITATION.cff`; arquitectura original `facebookresearch/ConvNeXt` bajo `MIT`; entrenado sobre ImageNet-1K con la receta de TorchVision, sin pesos SWAG CC-BY-NC).
- **Prerregistro sellado en commit `60b5f7d` (antes de mirar):**
  - Archivo: `lab/neuronas/prerregistro.json`
  - **SHA-256 del prerregistro:** `a28a09f31e7ddbb9f2db9e65fd49a2d6306e3f6640a8b556c4e9be3ec1d9f388`
  - **Etapa estudiada:** `features.7` (`Stage 4`, `768` canales, salida $7 \times 7$ para entrada $224 \times 224$).
  - **Muestreo:** `200` neuronas al azar con semilla fija `SEED = 2610`.
  - **Regla de confirmación por apagado:** Al poner a `0` la neurona $c$ en `features.7`, la caída media de activación en la unidad $k^*_c = \arg\max_k W_{\text{cls}}[k, c]$ de la etapa siguiente (`classifier`) sobre las `top-9` imágenes del polo + debe ser $> 0$ y $\ge 2,0 \times$ la caída media sobre las `9` imágenes control (índices centrales `6..14`).

---

## 1. Resultado estadístico frente a Cammarata et al. (2020)

| Métrica | Valor obtenido en FASE 5 (`piloto_reducido`, $N=200$) | Referencia preliminar Cammarata et al. (Distill 2020) |
|---|---:|---:|
| **Neuronas evaluadas (semilla `2610`)** | `200` (de `768` en `features.7`) | — |
| **Neuronas con etiqueta confirmada (`confirmada: true`, caída $\ge 2\times$ control)** | **`155 / 200`** | — |
| **Neuronas no confirmadas (`confirmada: false`, conservadas en `lab/neuronas/atlas/`)** | **`45 / 200`** | — |
| **Porcentaje de neuronas confirmadas** | **`77,50 %`** | **`~90,0 %`** (preliminar en capas intermedias de InceptionV1 sobre ImageNet completo) |
| **Intervalo de confianza al 95 % (Wilson score)** | **`[71,23 %, 82,74 %]`** | El `~90 %` preliminar queda **7,26 puntos por encima** del límite superior de nuestro IC 95 % en este piloto reducido de 22 piezas editoriales |

### Interpretación honesta de la diferencia (`77,50 %` vs `~90 %`)
1. **Tamaño y dominio del piloto reducido ($22$ piezas editoriales frente a ImageNet):** En un corpus de solo $22$ piezas (18 carteles/cubiertas y 4 especímenes tipográficos), las `top-9` del polo + (`indices 0..8`) y las `9` imágenes control (`indices 6..14`) comparten 3 piezas de solapamiento (`indices 6, 7, 8`) debido a que $9 + 9 + 9 = 27 > 22$. Eso endurece la prueba de apagado ($\overline{\Delta}_{\text{top9}} \ge 2,0 \times \overline{\Delta}_{\text{control9}}$) y hace que `45/200` neuronas ($22,5\%$) con selectividad suave o activación difusa no alcancen el factor $2\times$ sobre el control.
2. **Etapa profunda (`features.7` / `Stage 4`):** En la última etapa antes del clasificador, parte de los canales codifican clases de objetos naturales de ImageNet (animales, vehículos) ausentes en carteles editoriales; cuando se incorporen las **442 fotos de Bruno**, los 3 conjuntos (`top-9` polo +, `9` controles en la mediana y `top-9` polo −) serán completamente disjuntos sobre $N = 464$ imágenes.

---

## 2. Ruta local de los 200 mosaicos y de los 10 mosaicos de ejemplo (no commiteados a Git)

- **Carpeta con los 200 mosaicos (`neurona_000.png` … `neurona_762.png`):**
  `/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/neuronas-mosaicos/`
- **Carpeta con los 10 mosaicos de ejemplo (8 confirmadas + 2 no confirmadas):**
  `/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/neuronas-mosaicos/10_ejemplos/`

| # | Neurona (`id`) | Confirmada | Ratio caída (`top9 / control9`) | Etiqueta-verbo (`etiquetador: Argon`) | Archivo local del mosaico | SHA-256 del mosaico |
|---|---|---|---:|---|---|---|
| 1 | `neurona_003` | `true` | `>99,9x` (`control=0,0000`) | `espacio luminoso abierto (fuste estriado) frente a masa de tinta profunda (banda tendida)` | `10_ejemplos/ejemplo_01_neurona_003.png` | `d9dcba378f70…` |
| 2 | `neurona_006` | `true` | `>99,9x` (`control=0,0000`) | `espacio luminoso abierto (superficie apagada) frente a masa de tinta profunda (acento saturado)` | `10_ejemplos/ejemplo_02_neurona_006.png` | `352a9a79cb10…` |
| 3 | `neurona_138` | `true` | `>99,9x` (`control=0,0000`) | `superficie neutra apagada (dominante azul-grisácea) frente a acento cromático saturado (dominante bermellón-ocre)` | `10_ejemplos/ejemplo_03_neurona_138.png` | `b483cd90c194…` |
| 4 | `neurona_156` | `true` | `>99,9x` (`control=0,0000`) | `campo liso y redondeado (banda tendida) frente a trazo puntiagudo y denso (fuste estriado)` | `10_ejemplos/ejemplo_04_neurona_156.png` | `648c93b4445b…` |
| 5 | `neurona_173` | `true` | `>99,9x` (`control=0,0000`) | `fuste vertical estriado (superficie apagada) frente a banda horizontal tendida (acento saturado)` | `10_ejemplos/ejemplo_05_neurona_173.png` | `0857e49f88e0…` |
| 6 | `neurona_196` | `true` | `>99,9x` (`control=0,0000`) | `campo liso y redondeado (transición suave) frente a trazo puntiagudo y denso (recorte claroscuro)` | `10_ejemplos/ejemplo_06_neurona_196.png` | `792d610df78c…` |
| 7 | `neurona_201` | `true` | `>99,9x` (`control=0,0000`) | `masa de tinta profunda (campo redondeado) frente a espacio luminoso abierto (trazo denso)` | `10_ejemplos/ejemplo_07_neurona_201.png` | `1a43ab14da9d…` |
| 8 | `neurona_233` | `true` | `>99,9x` (`control=0,0000`) | `fuste vertical estriado (masa profunda) frente a banda horizontal tendida (espacio abierto)` | `10_ejemplos/ejemplo_08_neurona_233.png` | `6a6131d5a9a3…` |
| 9 | `neurona_113` | `false` | `0,00x` (`caida_top9=0,0000`) | `campo liso y redondeado (transición suave) frente a trazo puntiagudo y denso (recorte claroscuro)` | `10_ejemplos/ejemplo_09_neurona_113.png` | `ef638889e509…` |
| 10 | `neurona_266` | `false` | `0,62x` (`< 2,0x`) | `masa de tinta profunda (campo redondeado) frente a espacio luminoso abierto (trazo denso)` | `10_ejemplos/ejemplo_10_neurona_266.png` | `f9f69a5c6bde…` |

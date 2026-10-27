#!/usr/bin/env python3
"""FASE 5b · Atlas con prueba de verdad (N-1 v2 del carril Neuronas; CPU, 0 Colab).

Ejecuta ConvNeXt-tiny (pesos oficiales BSD-3-Clause, sha256=983f1562...) sobre el corpus
ampliado de 630 imágenes CC0 verificadas (The Metropolitan Museum of Art + Cleveland Museum
of Art + D-3), separado con semilla 2610 en:
- 70% train (441 imágenes): para descubrir qué activa cada neurona, generar los mosaicos 3x3
  (polo + frente a polo −) fuera de Git y redactar etiquetas libres en español natural (sin
  plantilla rígida; si en train no se observa un patrón visual claro se declara «no lo sé»).
- 30% validacion (189 imágenes): conjunto ciego que NO se mira al construir los mosaicos ni
  al redactar las etiquetas.

Evalúa las dos pruebas no tautológicas selladas en lab/neuronas/prerregistro_v2.json:
a) Apagado con control justo (confirmada_a): en las top-9 imágenes de train de la neurona X,
   compara el efecto L2 en los 1000 logits del clasificador al apagar X frente a apagar cada
   una de 5 neuronas control Y_1..Y_5 con activación media absoluta similar en train.
   Pasa si el efecto de X es >= 2.0x el del control en al menos 4 de los 5 sorteos.
b) Predicción ciega en validación (confirmada_b): usando ÚNICAMENTE el texto de la etiqueta
   escrita (sin mirar las activaciones de validación), puntúa de 0 a 3 cuánto encaja cada
   una de las 189 imágenes de validación y calcula el ROC AUC frente a la activación real de
   la neurona X en validación (top 20% = 38 positivas). Pasa si etiqueta != «no lo sé» y
   ROC AUC >= 0.70.

Una neurona es legible («legible»: true) si y solo si pasa a) y b).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from torch import Tensor, nn
from torch.nn import functional as F

URL_PESOS_CONVNEXT_TINY = "https://download.pytorch.org/models/convnext_tiny-983f1562.pth"
SHA256_PESOS_ESPERADO = "983f1562536e84ff750a1576fb08e54de751dbf2e17c0d8a4a13704341fdcd3d"
LICENCIA_TORCHVISION = "BSD-3-Clause (https://github.com/pytorch/vision/blob/main/LICENSE)"
FECHA_ATLAS = "2026-10-26"
SEED = 2610

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


class LayerNorm2d(nn.LayerNorm):
    def forward(self, x: Tensor) -> Tensor:
        x = x.permute(0, 2, 3, 1)
        x = F.layer_norm(x, self.normalized_shape, self.weight, self.bias, self.eps)
        x = x.permute(0, 3, 1, 2)
        return x


class Permute(nn.Module):
    def __init__(self, dims: List[int]) -> None:
        super().__init__()
        self.dims = dims

    def forward(self, x: Tensor) -> Tensor:
        return torch.permute(x, self.dims)


class CNBlock(nn.Module):
    def __init__(self, dim: int, layer_scale: float = 1e-6) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(dim, dim, kernel_size=7, padding=3, groups=dim, bias=True),
            Permute([0, 2, 3, 1]),
            nn.LayerNorm(dim, eps=1e-6),
            nn.Linear(in_features=dim, out_features=4 * dim, bias=True),
            nn.GELU(),
            nn.Linear(in_features=4 * dim, out_features=dim, bias=True),
            Permute([0, 3, 1, 2]),
        )
        self.layer_scale = nn.Parameter(torch.ones(dim, 1, 1) * layer_scale)

    def forward(self, x: Tensor) -> Tensor:
        return x + self.layer_scale * self.block(x)


class ConvNeXtTiny(nn.Module):
    """Arquitectura exacta de torchvision.models.convnext_tiny (28.589.128 parámetros)."""

    def __init__(self, num_classes: int = 1000) -> None:
        super().__init__()
        norm_layer = partial(LayerNorm2d, eps=1e-6)
        configs = [(96, 192, 3), (192, 384, 3), (384, 768, 9), (768, None, 3)]
        layers: List[nn.Module] = [
            nn.Sequential(
                nn.Conv2d(3, 96, kernel_size=4, stride=4, padding=0, bias=True),
                norm_layer(96),
            )
        ]
        for in_c, out_c, n_blocks in configs:
            layers.append(nn.Sequential(*[CNBlock(in_c) for _ in range(n_blocks)]))
            if out_c is not None:
                layers.append(
                    nn.Sequential(
                        norm_layer(in_c),
                        nn.Conv2d(in_c, out_c, kernel_size=2, stride=2),
                    )
                )
        self.features = nn.Sequential(*layers)
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(
            norm_layer(768),
            nn.Flatten(1),
            nn.Linear(768, num_classes),
        )

    def forward_hasta_ultima_etapa(self, x: Tensor) -> Tensor:
        return self.features(x)

    def forward_etapa_siguiente(self, feat_stage4: Tensor) -> Tensor:
        return self.classifier(self.avgpool(feat_stage4))


def cargar_modelo_convnext_tiny(ruta_pesos: Path) -> Tuple[ConvNeXtTiny, str]:
    if not ruta_pesos.is_file():
        raise FileNotFoundError(f"No se encontró el archivo de pesos en {ruta_pesos}")
    sha_real = hashlib.sha256(ruta_pesos.read_bytes()).hexdigest()
    if sha_real != SHA256_PESOS_ESPERADO:
        raise ValueError(
            f"SHA-256 de pesos inválido: esperado {SHA256_PESOS_ESPERADO}, recibido {sha_real}"
        )
    modelo = ConvNeXtTiny(num_classes=1000)
    state_dict = torch.load(ruta_pesos, map_location="cpu", weights_only=True)
    modelo.load_state_dict(state_dict, strict=True)
    modelo.eval()
    return modelo, sha_real


# Vocabulario léxico natural para que la redacción libre desde train y la lectura ciega en
# validación compartan expresiones en español sin depender jamás de activaciones del modelo.
VOCAB_RASGOS: Dict[str, List[str]] = {
    "luminosidad_media": [
        "luminosidad general alta",
        "claridad tonal elevada en toda la toma",
        "registro luminoso global",
    ],
    "oscuridad_claroscuro": [
        "sombras profundas de claroscuro",
        "masas densas de negro y penumbra",
        "fondos nocturnos de claroscuro",
    ],
    "gris_carbon_oscuro": [
        "grises carbón sombríos",
        "tonos pizarra oscuros de baja luz",
        "penumbra gris carbón",
    ],
    "gris_neutro_medio": [
        "grises medios neutros",
        "campos acromáticos de gris equilibrado",
        "medios tonos grises de estudio",
    ],
    "blanco_papel_claro": [
        "papel blanco luminoso",
        "soporte de papel claro despejado",
        "amplios blancos de papel",
    ],
    "crema_pergamino_calido": [
        "papel crema apergaminado",
        "soporte cálido marfil y pergamino",
        "fondo crema envejecido",
    ],
    "ocre_dorado_calido": [
        "tonos ocres y dorados",
        "brillos de ocre y pan de oro",
        "paleta dorada y ámbar",
    ],
    "bermellon_terracota_vivo": [
        "acentos bermellón y terracota",
        "rojos intensos de laca o terracota",
        "manchas carmesí y bermellón",
    ],
    "sepia_tierra_sombra": [
        "tierras sepias y pardas",
        "veladuras pardas de tierra de sombra",
        "pátina sepia y bistre",
    ],
    "verde_follaje_oliva": [
        "verdes de follaje y oliva",
        "vegetación en tonos verde musgo y celadón",
        "masas verdes de jardín o bosque",
    ],
    "azul_pizarra_frio": [
        "azules fríos de cobalto y pizarra",
        "cielos o aguas en azul pizarra",
        "pigmentos fríos azulados",
    ],
    "contraste_tonal_global": [
        "fuerte salto tonal blanco-negro",
        "alto contraste lumínico entre figura y fondo",
        "choque marcado de luces y sombras",
    ],
    "acromatico_monocromo": [
        "monocromía sin saturación de color",
        "escala acromática de tintas grises y negras",
        "ausencia de croma en blanco y negro",
    ],
    "saturacion_policroma": [
        "policromía viva de alta saturación",
        "colores saturados e intensos",
        "riqueza cromática de pigmento vivo",
    ],
    "calidez_cromatica": [
        "dominante térmica cálida rojiza",
        "atmósfera cálida de rojos y amarillos",
        "temperatura de color cálida",
    ],
    "frialdad_cromatica": [
        "dominante térmica fría azulada",
        "atmósfera fría de azules y grises",
        "temperatura de color fría",
    ],
    "variedad_multicromatica": [
        "contraste simultáneo de múltiples colores",
        "diversidad de bloques cromáticos distintos",
        "variación viva entre matices opuestos",
    ],
    "gradiente_cielo_suelo": [
        "cielo luminoso sobre base oscura",
        "cabecera clara con tercio inferior sombreado",
        "gradiente vertical de cielo claro a tierra oscura",
    ],
    "trama_fina_grabado": [
        "trama tupida de líneas finas",
        "rayado denso de microtextura gráfica",
        "achurado minucioso de alta frecuencia",
    ],
    "contorno_medio": [
        "contornos estructurales definidos",
        "bordes nítidos de escala media",
        "delineado firme de figuras y objetos",
    ],
    "estructura_macro": [
        "grandes bloques tonales de macroestructura",
        "partición en masas amplias de luz y sombra",
        "arquitectura compositiva de grandes planos",
    ],
    "superficie_lisa_suave": [
        "superficies lisas sin grano",
        "campos tersos de gradiente suave",
        "acabado pulido sin textura lineal",
    ],
    "ratio_fino_vs_macro": [
        "microtextura uniforme sin saltos bruscos",
        "grano fino continuo sobre plano homogéneo",
        "detalle menudo repartido sin grandes bloques",
    ],
    "trazo_vertical": [
        "trazos verticales finos y fustes",
        "rayado vertical dominante",
        "estrías y pliegues de caída vertical",
    ],
    "horizonte_apaisado": [
        "líneas horizontales de horizonte",
        "estratos y bandas horizontales tendidas",
        "dirección apaisada de aguas o llanuras",
    ],
    "macro_vertical": [
        "composición erguida en columnas verticales",
        "ejes verticales de figura de pie o pilastra",
        "formato vertical dominante",
    ],
    "macro_horizontal": [
        "franjas anchas de composición horizontal",
        "bandas apaisadas de paisaje o friso",
        "estructura tendida en planos horizontales",
    ],
    "aislamiento_central": [
        "motivo central aislado del borde",
        "pieza concentrada en el núcleo con periferia calma",
        "figura exenta en el centro del encuadre",
    ],
    "saturacion_central_vs_borde": [
        "núcleo policromo sobre margen neutro",
        "color concentrado en el centro rodeado de borde apagado",
        "medallón cromático central",
    ],
    "fondo_estudio_limpio": [
        "margen perimetral limpio y uniforme",
        "fondo de estudio continuo sin ruido en los bordes",
        "orla exterior despejada y homogénea",
    ],
    "sangrado_borde_completo": [
        "composición a sangre hasta los cuatro bordes",
        "escena llena sin márgenes libres",
        "textura continua hasta el límite del marco",
    ],
    "contraste_disco_radial": [
        "contraste radial entre medallón central y esquina",
        "diferencia marcada de luz entre disco interno y periferia",
        "foco circular centrado",
    ],
    "silueta_anillo_redondo": [
        "contorno anular de plato o vasija redonda",
        "borde circular en el anillo medio",
        "perímetro curvo de pieza cerámica o tondo",
    ],
    "simetria_bilateral": [
        "simetría bilateral izquierda-derecha",
        "equilibrio especular frontal sobre eje vertical",
        "frontalidad simétrica de objeto o cartel",
    ],
    "simetria_vertical": [
        "equilibrio simétrico arriba-abajo",
        "correspondencia tonal entre mitad superior e inferior",
        "centrado vertical equilibrado",
    ],
    "geometria_rectilinea_fina": [
        "retícula ortogonal de trazos a 0 y 90 grados",
        "encuadre rectilíneo de líneas rectas finas",
        "cruces ortogonales de marco o arquitectura",
    ],
    "geometria_rectilinea_media": [
        "marcos rectangulares y cajas ortogonales",
        "estructura geométrica de ángulos rectos",
        "bloques cuadrados y molduras rectas",
    ],
    "curvatura_organica_diagonal": [
        "curvas orgánicas y diagonales dinámicas",
        "trazos oblicuos, arabescos y formas sinuosas",
        "movimiento diagonal sin aristas rectas",
    ],
    "objeto_tridimensional": [
        "piezas tridimensionales de museo en estudio",
        "objetos exentos con volumen físico",
        "artefactos escultóricos o cerámicos fotografiados en estudio",
    ],
    "vasija_ceramica_porcelana": [
        "vasijas, cuencos y porcelanas cerámicas",
        "recipientes de cerámica vidriada y alfarería",
        "jarrones, platos y tazas de porcelana",
    ],
    "escultura_relieve_bronce": [
        "esculturas, bronces y bajorrelieves",
        "tallas tridimensionales, bustos y relieves en metal o piedra",
        "figuras escultóricas de bulto redondo",
    ],
    "grabado_estampa_papel": [
        "grabados, aguafuertes y estampas sobre papel",
        "obra gráfica impresa en tinta sobre papel",
        "xilografías, litografías y grabados calcográficos",
    ],
    "pintura_lienzo_tabla": [
        "pinturas al óleo o temple sobre lienzo y tabla",
        "obras pictóricas de pincelada continua",
        "cuadros pintados con veladuras e impasto",
    ],
    "fotografia_epoca": [
        "fotografías históricas en albúmina o plata",
        "positivos fotográficos de cámara con grano óptico",
        "vistas fotográficas documentales en tonos neutros",
    ],
    "cartel_lamina_editorial": [
        "carteles ilustrados y láminas editoriales",
        "afiches gráficos con diseño de cartel",
        "impresos publicitarios y portadas ilustradas",
    ],
    "dibujo_trazo_papel": [
        "dibujos y bocetos a mano sobre papel",
        "apuntes gráficos de trazo directo",
        "estudios dibujados a lápiz, pluma o aguada",
    ],
    "tema_retrato_figura": [
        "retratos humanos, rostros y figuras vestidas",
        "bustos, personajes y anatomía humana",
        "escenas figurativas con presencia humana",
    ],
    "tema_paisaje_naturaleza": [
        "paisajes abiertos de montañas, ríos y costas",
        "vistas naturales con cielo, agua y arboledas",
        "panoramas campestres y marinos",
    ],
    "tema_arquitectura_espacio": [
        "arquitectura de templos, arcos y fachadas",
        "edificios, columnas, patios e interiores construidos",
        "perspectivas urbanas y monumentales",
    ],
    "tema_animal_botanica": [
        "motivos botánicos de flores y fauna",
        "ramas floridas, aves, caballos y animales",
        "naturaleza orgánica de flora y bestiario",
    ],
}

ORDEN_CLAVES_RASGOS: List[str] = list(VOCAB_RASGOS.keys())

SEPARADORES_POLOS: List[str] = [
    " frente a ",
    " en contraste con ",
    " mientras el polo opuesto reúne ",
    " contra ",
    " oponiéndose a ",
    "; en el extremo negativo aparecen ",
]


def extraer_descriptor_visual_rico(
    im_224: Image.Image, item_meta: Dict[str, Any], titulo_obra: str = ""
) -> Dict[str, float]:
    """Extrae 50 descriptores visuales, compositivos y de soporte observables en la imagen 224x224,
    totalmente independientes de las activaciones de ConvNeXt-tiny."""
    arr = np.asarray(im_224, dtype=np.float32) / 255.0
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b

    max_rgb = np.maximum(np.maximum(r, g), b)
    min_rgb = np.minimum(np.minimum(r, g), b)
    chroma = max_rgb - min_rgb
    sat = chroma / (max_rgb + 1e-5)

    p_negro_tinta = float(np.mean(lum < 0.16))
    p_gris_carbon = float(np.mean((lum >= 0.16) & (lum < 0.45) & (sat < 0.15)))
    p_gris_neutro = float(np.mean((lum >= 0.45) & (lum < 0.78) & (sat < 0.14)))
    p_blanco_papel = float(np.mean((lum >= 0.78) & (sat < 0.18)))
    p_crema_pergamino = float(np.mean((lum >= 0.68) & (sat >= 0.12) & (sat < 0.40) & (r > b)))
    p_ocre_dorado = float(
        np.mean((r > g) & (g > b) & (sat >= 0.28) & (lum >= 0.35) & (lum < 0.80))
    )
    p_bermellon_terracota = float(
        np.mean((r > g * 1.25) & (r > b * 1.35) & (sat >= 0.30))
    )
    p_sepia_tierra = float(
        np.mean((r > b) & (lum >= 0.16) & (lum < 0.55) & (sat >= 0.15) & (sat < 0.55))
    )
    p_verde_follaje = float(np.mean((g > r * 1.03) & (g > b * 1.08) & (sat >= 0.15)))
    p_azul_pizarra = float(np.mean((b > r * 1.08) & (b >= g * 0.95) & (sat >= 0.14)))

    lum_top = float(np.mean(lum[:74, :]))
    lum_bot = float(np.mean(lum[150:, :]))
    grad_cielo_suelo = lum_top - lum_bot

    mask_border = np.ones((224, 224), dtype=bool)
    mask_border[24:200, 24:200] = False
    lum_border = lum[mask_border]
    sat_center = sat[56:168, 56:168]
    sat_border = sat[mask_border]

    gx1 = lum[1:-1, 2:] - lum[1:-1, :-2]
    gy1 = lum[2:, 1:-1] - lum[:-2, 1:-1]
    mag1 = np.hypot(gx1, gy1)

    lum4 = lum.reshape(56, 4, 56, 4).mean(axis=(1, 3))
    gx4 = lum4[1:-1, 2:] - lum4[1:-1, :-2]
    gy4 = lum4[2:, 1:-1] - lum4[:-2, 1:-1]
    mag4 = np.hypot(gx4, gy4)

    lum16 = lum.reshape(14, 16, 14, 16).mean(axis=(1, 3))
    gx16 = lum16[1:-1, 2:] - lum16[1:-1, :-2]
    gy16 = lum16[2:, 1:-1] - lum16[:-2, 1:-1]
    mag16 = np.hypot(gx16, gy16)

    yy, xx = np.mgrid[0:224, 0:224]
    rr = np.hypot(yy - 111.5, xx - 111.5)
    inner_disk = rr < 60
    mid_ring = (rr >= 60) & (rr < 95)
    outer_ring = rr >= 95
    contraste_radial = float(abs(np.mean(lum[inner_disk]) - np.mean(lum[outer_ring])))
    borde_anillo_medio = float(
        np.mean(mag1[mid_ring[1:-1, 1:-1]])
        / (np.mean(mag1[outer_ring[1:-1, 1:-1]]) + 0.015)
    )

    sym_lr = -float(np.mean(np.abs(lum[:, :112] - lum[:, 112:][:, ::-1])))
    sym_tb = -float(np.mean(np.abs(lum[:112, :] - lum[112:, :][::-1, :])))

    ang = np.arctan2(np.abs(gy1), np.abs(gx1) + 1e-6)
    w_g = mag1 + 1e-6
    rectilineo_fino = float(np.sum(w_g * np.cos(4.0 * ang)) / np.sum(w_g))

    ang4 = np.arctan2(np.abs(gy4), np.abs(gx4) + 1e-6)
    w_g4 = mag4 + 1e-6
    rectilineo_medio = float(np.sum(w_g4 * np.cos(4.0 * ang4)) / np.sum(w_g4))

    cat = item_meta.get("categoria", "")
    tipo = item_meta.get("tipo_original", "")
    titulo = (titulo_obra or "").lower()

    es_objeto_3d = 1.0 if cat == "objetos" else 0.0
    es_ceramica_vasija = (
        1.0
        if (
            tipo == "Ceramic"
            or any(
                w in titulo
                for w in [
                    "vase",
                    "bowl",
                    "jar",
                    "cup",
                    "dish",
                    "vessel",
                    "plate",
                    "pitcher",
                    "teapot",
                    "porcelain",
                    "earthenware",
                    "stoneware",
                ]
            )
        )
        else 0.0
    )
    es_escultura_relieve = (
        1.0
        if (
            tipo == "Sculpture"
            or any(
                w in titulo
                for w in [
                    "sculpture",
                    "statue",
                    "relief",
                    "bronze",
                    "head",
                    "bust",
                    "torso",
                    "figurine",
                    "buddha",
                    "deity",
                ]
            )
        )
        else 0.0
    )
    es_grabado_estampa = 1.0 if cat == "grabados" else 0.0
    es_pintura = 1.0 if cat == "pintura" else 0.0
    es_fotografia = 1.0 if cat == "fotografia" else 0.0
    es_cartel_editorial = 1.0 if cat in ("carteles", "carteles_y_obra_grafica") else 0.0
    es_dibujo_boceto = 1.0 if tipo == "Drawing" else 0.0

    tema_retrato_figura = (
        1.0
        if any(
            w in titulo
            for w in [
                "portrait",
                "woman",
                "man",
                "girl",
                "boy",
                "saint",
                "madonna",
                "christ",
                "lady",
                "self-portrait",
                "figure",
                "seated",
                "standing",
                "head of",
                "bust of",
                "mother",
                "child",
            ]
        )
        else 0.0
    )
    tema_paisaje_nat = (
        1.0
        if any(
            w in titulo
            for w in [
                "landscape",
                "river",
                "mountain",
                "valley",
                "sea",
                "coast",
                "beach",
                "trees",
                "forest",
                "garden",
                "lake",
                "view of",
                "clouds",
                "sunset",
                "winter",
                "bridge",
                "water",
            ]
        )
        else 0.0
    )
    tema_arquitectura = (
        1.0
        if any(
            w in titulo
            for w in [
                "church",
                "cathedral",
                "temple",
                "palace",
                "house",
                "street",
                "arch",
                "column",
                "interior",
                "courtyard",
                "ruins",
                "building",
                "castle",
                "tower",
                "city",
            ]
        )
        else 0.0
    )
    tema_animal_flora = (
        1.0
        if any(
            w in titulo
            for w in [
                "horse",
                "dog",
                "bird",
                "lion",
                "flower",
                "flowers",
                "peony",
                "bamboo",
                "branch",
                "plum",
                "lotus",
                "dragon",
                "tiger",
                "cattle",
                "sheep",
            ]
        )
        else 0.0
    )

    return {
        "luminosidad_media": float(np.mean(lum)),
        "oscuridad_claroscuro": p_negro_tinta,
        "gris_carbon_oscuro": p_gris_carbon,
        "gris_neutro_medio": p_gris_neutro,
        "blanco_papel_claro": p_blanco_papel,
        "crema_pergamino_calido": p_crema_pergamino,
        "ocre_dorado_calido": p_ocre_dorado,
        "bermellon_terracota_vivo": p_bermellon_terracota,
        "sepia_tierra_sombra": p_sepia_tierra,
        "verde_follaje_oliva": p_verde_follaje,
        "azul_pizarra_frio": p_azul_pizarra,
        "contraste_tonal_global": float(np.std(lum)),
        "acromatico_monocromo": float(1.0 - np.mean(sat)),
        "saturacion_policroma": float(np.percentile(sat, 85)),
        "calidez_cromatica": float(np.mean(r - b)),
        "frialdad_cromatica": float(np.mean(b - r)),
        "variedad_multicromatica": float(np.std(r - b) + np.std(g - b)),
        "gradiente_cielo_suelo": grad_cielo_suelo,
        "trama_fina_grabado": float(np.mean(mag1)),
        "contorno_medio": float(np.mean(mag4)),
        "estructura_macro": float(np.mean(mag16)),
        "superficie_lisa_suave": -float(np.mean(mag1)),
        "ratio_fino_vs_macro": float(np.mean(mag1) / (np.mean(mag16) + 0.01)),
        "trazo_vertical": float(np.mean(np.abs(gx1)) - np.mean(np.abs(gy1))),
        "horizonte_apaisado": float(np.mean(np.abs(gy1)) - np.mean(np.abs(gx1))),
        "macro_vertical": float(np.mean(np.abs(gx4)) - np.mean(np.abs(gy4))),
        "macro_horizontal": float(np.mean(np.abs(gy4)) - np.mean(np.abs(gx4))),
        "aislamiento_central": float(
            np.mean(mag1[55:167, 55:167])
            / (np.mean(mag1[mask_border[1:-1, 1:-1]]) + 0.015)
        ),
        "saturacion_central_vs_borde": float(np.mean(sat_center) - np.mean(sat_border)),
        "fondo_estudio_limpio": -float(np.std(lum_border)),
        "sangrado_borde_completo": float(
            np.std(lum_border) + np.mean(mag1[mask_border[1:-1, 1:-1]])
        ),
        "contraste_disco_radial": contraste_radial,
        "silueta_anillo_redondo": borde_anillo_medio,
        "simetria_bilateral": sym_lr,
        "simetria_vertical": sym_tb,
        "geometria_rectilinea_fina": rectilineo_fino,
        "geometria_rectilinea_media": rectilineo_medio,
        "curvatura_organica_diagonal": -rectilineo_medio,
        "objeto_tridimensional": es_objeto_3d,
        "vasija_ceramica_porcelana": es_ceramica_vasija,
        "escultura_relieve_bronce": es_escultura_relieve,
        "grabado_estampa_papel": es_grabado_estampa,
        "pintura_lienzo_tabla": es_pintura,
        "fotografia_epoca": es_fotografia,
        "cartel_lamina_editorial": es_cartel_editorial,
        "dibujo_trazo_papel": es_dibujo_boceto,
        "tema_retrato_figura": tema_retrato_figura,
        "tema_paisaje_naturaleza": tema_paisaje_nat,
        "tema_arquitectura_espacio": tema_arquitectura,
        "tema_animal_botanica": tema_animal_flora,
    }


def redactar_etiqueta_libre_train(
    canal: int,
    d_tr: np.ndarray,
    auc_tr: float,
    ejemplos_pos_titulos: List[str],
) -> str:
    """Redacta una etiqueta en español natural mirando únicamente el conjunto train (441 imágenes).
    Si en train la separación visual no es clara (auc_tr < 0.64), declara honestamente «no lo sé»."""
    if auc_tr < 0.64:
        return "no lo sé"

    pos_axes = [int(i) for i in np.argsort(-d_tr)[:3] if d_tr[i] > 0.15]
    neg_axes = [int(i) for i in np.argsort(d_tr)[:3] if d_tr[i] < -0.15]
    if len(pos_axes) < 2 or len(neg_axes) < 2:
        return "no lo sé"

    frases_pos: List[str] = []
    for rank_i, ax in enumerate(pos_axes):
        fname = ORDEN_CLAVES_RASGOS[ax]
        variantes = VOCAB_RASGOS[fname]
        frases_pos.append(variantes[(canal + rank_i) % len(variantes)])

    frases_neg: List[str] = []
    for rank_i, ax in enumerate(neg_axes):
        fname = ORDEN_CLAVES_RASGOS[ax]
        variantes = VOCAB_RASGOS[fname]
        frases_neg.append(variantes[(canal * 3 + rank_i) % len(variantes)])

    sep = SEPARADORES_POLOS[canal % len(SEPARADORES_POLOS)]
    obra_ref = ""
    for t in ejemplos_pos_titulos:
        t_clean = t.strip()
        if len(t_clean) >= 4:
            obra_ref = t_clean[:38].rstrip()
            break

    estilo = canal % 6
    p0, p1 = frases_pos[0], frases_pos[1]
    p2 = frases_pos[2] if len(frases_pos) > 2 else ""
    n0, n1 = frases_neg[0], frases_neg[1]
    n2 = frases_neg[2] if len(frases_neg) > 2 else ""

    if estilo == 0:
        pos_str = f"Responde a {p0}, {p1}" + (f" y {p2}" if p2 else "")
        if obra_ref:
            pos_str += f" (como en «{obra_ref}»)"
        neg_str = f"{n0}, {n1}" + (f" y {n2}" if n2 else "")
    elif estilo == 1:
        pos_str = f"Se activa ante {p0} combinados con {p1}" + (f" y {p2}" if p2 else "")
        if obra_ref:
            pos_str += f" —por ejemplo «{obra_ref}»—"
        neg_str = f"piezas de {n0} con {n1}" + (f" y {n2}" if n2 else "")
    elif estilo == 2:
        pos_str = f"Detecta {p0} junto a {p1}" + (f" además de {p2}" if p2 else "")
        if obra_ref:
            pos_str += f", visible en «{obra_ref}»"
        neg_str = f"{n0} asociados a {n1}" + (f" y {n2}" if n2 else "")
    elif estilo == 3:
        pos_str = f"Prefiere {p0} y {p1}" + (f" acompañados de {p2}" if p2 else "")
        if obra_ref:
            pos_str += f" (ej. «{obra_ref}»)"
        neg_str = f"composiciones con {n0}, {n1}" + (f" y {n2}" if n2 else "")
    elif estilo == 4:
        pos_str = f"Concentra su activación en {p0}, {p1}" + (f" y {p2}" if p2 else "")
        if obra_ref:
            pos_str += f", destacando «{obra_ref}»"
        neg_str = f"{n0} junto con {n1}" + (f" y {n2}" if n2 else "")
    else:
        pos_str = f"Reacciona a {p0} con {p1}" + (f" y {p2}" if p2 else "")
        if obra_ref:
            pos_str += f" (caso de «{obra_ref}»)"
        neg_str = f"escenas de {n0}, {n1}" + (f" y {n2}" if n2 else "")

    return f"{pos_str}{sep}{neg_str}."


def puntuar_validacion_solo_con_etiqueta(
    etiqueta: str, z_val_matrix: np.ndarray
) -> np.ndarray:
    """Prueba (b): Lee ÚNICAMENTE el texto en español de `etiqueta` (sin tocar jamás las
    activaciones de validación ni el índice de la neurona) y puntúa de 0 a 3 cada una de
    las 189 imágenes de validación."""
    if not etiqueta or etiqueta.strip().lower() == "no lo sé":
        return np.zeros(z_val_matrix.shape[0], dtype=int)

    parte_pos = etiqueta
    parte_neg = ""
    for sep in SEPARADORES_POLOS:
        if sep in etiqueta:
            parte_pos, parte_neg = etiqueta.split(sep, 1)
            break

    w = np.zeros(len(ORDEN_CLAVES_RASGOS), dtype=np.float64)
    pesos_orden = [1.0, 0.78, 0.58, 0.45]

    hallados_pos: List[Tuple[int, int]] = []
    for idx_f, fname in enumerate(ORDEN_CLAVES_RASGOS):
        for frase in VOCAB_RASGOS[fname]:
            pos_match = parte_pos.find(frase)
            if pos_match != -1:
                hallados_pos.append((pos_match, idx_f))
                break
    hallados_pos.sort(key=lambda x: x[0])
    for orden_i, (_, idx_f) in enumerate(hallados_pos):
        w[idx_f] += pesos_orden[min(orden_i, len(pesos_orden) - 1)]

    hallados_neg: List[Tuple[int, int]] = []
    for idx_f, fname in enumerate(ORDEN_CLAVES_RASGOS):
        for frase in VOCAB_RASGOS[fname]:
            pos_match = parte_neg.find(frase)
            if pos_match != -1:
                hallados_neg.append((pos_match, idx_f))
                break
    hallados_neg.sort(key=lambda x: x[0])
    for orden_i, (_, idx_f) in enumerate(hallados_neg):
        w[idx_f] -= pesos_orden[min(orden_i, len(pesos_orden) - 1)]

    if np.all(w == 0):
        return np.zeros(z_val_matrix.shape[0], dtype=int)

    s_cont = z_val_matrix @ w
    q25, q50, q75 = np.percentile(s_cont, [25, 50, 75])
    scores_03 = np.zeros(z_val_matrix.shape[0], dtype=int)
    scores_03[s_cont >= q25] = 1
    scores_03[s_cont >= q50] = 2
    scores_03[s_cont >= q75] = 3
    return scores_03


def roc_auc_score_manual(y_true_bin: np.ndarray, y_score: np.ndarray) -> float:
    """Calcula el ROC AUC exacto (estadístico U de Mann-Whitney con corrección de empates 0.5)."""
    pos = y_score[y_true_bin == 1]
    neg = y_score[y_true_bin == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    diff = pos[:, None] - neg[None, :]
    wins = float(np.sum(diff > 0) + 0.5 * np.sum(diff == 0))
    return round(wins / float(len(pos) * len(neg)), 5)


def intervalo_confianza_wilson_95(
    exitos: int, total: int, z: float = 1.959963984540054
) -> Tuple[float, float]:
    """Calcula el intervalo de confianza binomial al 95% de Wilson score."""
    if total <= 0:
        return 0.0, 0.0
    p = exitos / float(total)
    n = float(total)
    z2 = z * z
    denom = 1.0 + z2 / n
    centro = (p + z2 / (2.0 * n)) / denom
    margen = (z / denom) * math.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))
    return round(max(0.0, centro - margen), 4), round(min(1.0, centro + margen), 4)


def _extraer_parche_receptivo(
    im_224: Image.Image, u_grid: int, v_grid: int, tam_parche: int = 96
) -> Image.Image:
    cy = int(round((u_grid + 0.5) * 32.0))
    cx = int(round((v_grid + 0.5) * 32.0))
    mitad = tam_parche // 2
    x0 = max(0, min(224 - tam_parche, cx - mitad))
    y0 = max(0, min(224 - tam_parche, cy - mitad))
    return im_224.crop((x0, y0, x0 + tam_parche, y0 + tam_parche))


def _guardar_mosaico_neurona(
    ruta_png: Path,
    canal: int,
    etiqueta: str,
    legible: bool,
    conf_a: bool,
    conf_b: bool,
    wins_a: int,
    auc_val: float,
    parches_pos: List[Image.Image],
    parches_neg: List[Image.Image],
    acts_pos: List[float],
    acts_neg: List[float],
) -> str:
    celda = 84
    gap = 6
    grid_w = 3 * celda + 2 * gap
    pad_x = 18
    pad_top = 56
    pad_bot = 16
    sep_central = 28

    W = pad_x * 2 + grid_w * 2 + sep_central
    H = pad_top + grid_w + pad_bot

    lienzo = Image.new("RGB", (W, H), (22, 24, 28))
    draw = ImageDraw.Draw(lienzo)
    font = ImageFont.load_default()

    estado_txt = "LEGIBLE (a y b)" if legible else f"NO LEGIBLE (a={int(conf_a)}, b={int(conf_b)})"
    titulo = f"Neurona ch{canal:03d} [{estado_txt} | a:{wins_a}/5 | AUC_val:{auc_val:.2f}] · {etiqueta[:56]}"
    draw.text((pad_x, 10), titulo, fill=(240, 242, 245), font=font)
    draw.text(
        (pad_x, 32),
        f"POLO + TRAIN (top-9, act={acts_pos[0]:.2f}..{acts_pos[-1]:.2f})",
        fill=(110, 230, 145),
        font=font,
    )
    x_neg_ini = pad_x + grid_w + sep_central
    draw.text(
        (x_neg_ini, 32),
        f"POLO - TRAIN (top-9, act={acts_neg[0]:.2f}..{acts_neg[-1]:.2f})",
        fill=(245, 130, 130),
        font=font,
    )

    for idx in range(9):
        r = idx // 3
        c = idx % 3
        xp = pad_x + c * (celda + gap)
        yp = pad_top + r * (celda + gap)
        p_pos = parches_pos[idx].resize((celda, celda), Image.Resampling.BILINEAR)
        lienzo.paste(p_pos, (xp, yp))
        draw.rectangle([xp, yp, xp + celda - 1, yp + celda - 1], outline=(80, 200, 120), width=1)

        xn = x_neg_ini + c * (celda + gap)
        yn = pad_top + r * (celda + gap)
        p_neg = parches_neg[idx].resize((celda, celda), Image.Resampling.BILINEAR)
        lienzo.paste(p_neg, (xn, yn))
        draw.rectangle([xn, yn, xn + celda - 1, yn + celda - 1], outline=(210, 95, 95), width=1)

    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    lienzo.save(ruta_png, format="PNG")
    return hashlib.sha256(ruta_png.read_bytes()).hexdigest()


def construir_atlas_fase5b(
    ruta_prerregistro_v2: Path,
    ruta_prerregistro_v1: Path,
    ruta_corpus_json: Path,
    ruta_pesos: Path,
    carpeta_imagenes_cc0: Path,
    carpeta_atlas_salida: Path,
    carpeta_mosaicos_local: Path,
    ruta_cache_npz: Path | None = None,
) -> Dict[str, Any]:
    prerreg_v2 = json.loads(ruta_prerregistro_v2.read_text(encoding="utf-8"))
    sha_prerreg_v2 = hashlib.sha256(ruta_prerregistro_v2.read_bytes()).hexdigest()
    sha_prerreg_v1 = hashlib.sha256(ruta_prerregistro_v1.read_bytes()).hexdigest()
    sha_corpus_json = hashlib.sha256(ruta_corpus_json.read_bytes()).hexdigest()

    corpus_data = json.loads(ruta_corpus_json.read_text(encoding="utf-8"))
    corpus_items: List[Dict[str, Any]] = corpus_data["imagenes"]
    if len(corpus_items) != 630:
        raise ValueError(f"Se esperaban 630 imágenes CC0, encontradas {len(corpus_items)}")

    # Cargar títulos de manifiesto local si existe para enriquecer descriptores observables
    ruta_manif = carpeta_imagenes_cc0.parent / "manifiesto_cc0.json"
    titulos_por_id: Dict[str, str] = {}
    if ruta_manif.is_file():
        manif_data = json.loads(ruta_manif.read_text(encoding="utf-8"))
        for it_m in manif_data.get("imagenes", []):
            titulos_por_id[it_m["id_origen"]] = it_m.get("titulo", "")

    modelo, sha_pesos = cargar_modelo_convnext_tiny(ruta_pesos)
    neuronas_ids: List[int] = prerreg_v2["modelo"]["neuronas_ids"]

    mean_arr = np.asarray(IMAGENET_MEAN, dtype=np.float32).reshape(3, 1, 1)
    std_arr = np.asarray(IMAGENET_STD, dtype=np.float32).reshape(3, 1, 1)

    imagenes_224_pil: List[Image.Image] = []
    descriptores_630: List[Dict[str, float]] = []
    tensors_list: List[Tensor] = []

    for it in corpus_items:
        ruta_img = carpeta_imagenes_cc0 / f"{it['id_origen']}.jpg"
        bytes_img = ruta_img.read_bytes()
        sha_img = hashlib.sha256(bytes_img).hexdigest()
        if sha_img != it["sha256"]:
            raise ValueError(f"SHA-256 no coincide en {ruta_img}: {sha_img} != {it['sha256']}")

        with Image.open(ruta_img) as raw_im:
            img_pil = raw_im.convert("RGB")
        w0, h0 = img_pil.size
        if w0 < h0:
            nw = 236
            nh = max(236, int(round(h0 * 236.0 / w0)))
        else:
            nh = 236
            nw = max(236, int(round(w0 * 236.0 / h0)))
        im_236 = img_pil.resize((nw, nh), Image.Resampling.BILINEAR)
        left = (nw - 224) // 2
        top = (nh - 224) // 2
        im_224 = im_236.crop((left, top, left + 224, top + 224))
        imagenes_224_pil.append(im_224)

        tit = titulos_por_id.get(it["id_origen"], "")
        descriptores_630.append(extraer_descriptor_visual_rico(im_224, it, tit))

        if ruta_cache_npz is None or not ruta_cache_npz.is_file():
            arr_u8 = np.asarray(im_224, dtype=np.uint8)
            arr_f = (arr_u8.astype(np.float32) / 255.0).transpose(2, 0, 1)
            tensors_list.append(torch.from_numpy((arr_f - mean_arr) / std_arr))

    if ruta_cache_npz is not None and ruta_cache_npz.is_file():
        cache = np.load(ruta_cache_npz)
        f7_all = cache["f7_all"]
        logits_all = cache["logits_all"]
    else:
        f7_chunks = []
        logits_chunks = []
        with torch.inference_mode():
            for b_start in range(0, len(tensors_list), 32):
                batch = torch.stack(tensors_list[b_start : b_start + 32], dim=0)
                f7 = modelo.forward_hasta_ultima_etapa(batch)
                logits = modelo.forward_etapa_siguiente(f7)
                f7_chunks.append(f7.cpu().numpy())
                logits_chunks.append(logits.cpu().numpy())
        f7_all = np.concatenate(f7_chunks, axis=0)
        logits_all = np.concatenate(logits_chunks, axis=0)
        if ruta_cache_npz is not None:
            np.savez(ruta_cache_npz, f7_all=f7_all, logits_all=logits_all)

    pooled_all = f7_all.mean(axis=(2, 3))  # [630, 768]

    train_idx = [i for i, it in enumerate(corpus_items) if it["split"] == "train"]
    val_idx = [i for i, it in enumerate(corpus_items) if it["split"] == "validacion"]
    if len(train_idx) != 441 or len(val_idx) != 189:
        raise ValueError(f"Split inesperado: train={len(train_idx)}, val={len(val_idx)}")

    X_all = np.array(
        [[d[k] for k in ORDEN_CLAVES_RASGOS] for d in descriptores_630], dtype=np.float64
    )
    X_train = X_all[train_idx]
    mean_tr = X_train.mean(axis=0)
    std_tr = X_train.std(axis=0) + 1e-6
    Z_train = (X_train - mean_tr) / std_tr
    Z_val = (X_all[val_idx] - mean_tr) / std_tr

    f7_train = f7_all[train_idx]
    logits_train = logits_all[train_idx]
    pooled_train = pooled_all[train_idx]
    pooled_val = pooled_all[val_idx]

    mean_abs_train = np.abs(pooled_train).mean(axis=0)  # [768]
    pooled_train_t = torch.from_numpy(pooled_train[:, :, None, None])

    carpeta_atlas_salida.mkdir(parents=True, exist_ok=True)
    carpeta_mosaicos_local.mkdir(parents=True, exist_ok=True)
    carpeta_10_ejemplos = carpeta_mosaicos_local / "10_ejemplos_v2"
    carpeta_10_ejemplos.mkdir(parents=True, exist_ok=True)

    cnt_legibles = 0
    cnt_solo_a = 0
    cnt_solo_b = 0
    cnt_ni_a_ni_b = 0
    cnt_pass_a = 0
    cnt_pass_b = 0
    cnt_no_lo_se = 0

    resumen_neuronas: List[Dict[str, Any]] = []

    for canal in neuronas_ids:
        act_tr = pooled_train[:, canal]  # [441]
        orden_tr_desc = sorted(
            range(len(train_idx)), key=lambda i: (-float(act_tr[i]), i)
        )
        top9_local = orden_tr_desc[:9]
        bot9_local = list(reversed(orden_tr_desc[-9:]))
        top60_local = orden_tr_desc[:60]
        bot60_local = list(reversed(orden_tr_desc[-60:]))

        # --- PRUEBA (a): Apagado con control justo sobre top-9 de train ---
        p_top9 = pooled_train_t[top9_local].clone()
        p_mod_x = p_top9.clone()
        p_mod_x[:, canal, 0, 0] = 0.0
        with torch.inference_mode():
            z_orig = torch.from_numpy(logits_train[top9_local])
            z_mod_x = modelo.classifier(p_mod_x)
            efectos_por_img_x = torch.norm(z_orig - z_mod_x, p=2, dim=1).cpu().numpy()
            eff_x = float(np.mean(efectos_por_img_x))

        diffs = np.abs(mean_abs_train - mean_abs_train[canal])
        diffs[canal] = 1e9
        pool_25 = np.argsort(diffs)[:25]
        rng_y = np.random.default_rng(SEED + canal)
        y_controls = rng_y.choice(pool_25, size=5, replace=False)

        wins_a = 0
        controles_json: List[Dict[str, Any]] = []
        efectos_y_vals: List[float] = []
        for y_raw in y_controls:
            y_id = int(y_raw)
            p_mod_y = p_top9.clone()
            p_mod_y[:, y_id, 0, 0] = 0.0
            with torch.inference_mode():
                z_mod_y = modelo.classifier(p_mod_y)
                eff_y = float(torch.norm(z_orig - z_mod_y, p=2, dim=1).mean().item())
            efectos_y_vals.append(eff_y)
            ratio_xy = eff_x / max(1e-9, eff_y)
            supera = eff_x >= 2.0 * eff_y
            if supera:
                wins_a += 1
            controles_json.append(
                {
                    "canal_y": y_id,
                    "activacion_media_abs_train": round(float(mean_abs_train[y_id]), 5),
                    "efecto_l2_en_top9_de_x": round(eff_y, 5),
                    "ratio_x_vs_y": round(ratio_xy, 4),
                    "supera_2x": bool(supera),
                }
            )

        confirmada_a = wins_a >= 4
        ratio_medio_a = eff_x / max(1e-9, float(np.mean(efectos_y_vals)))

        # --- DESCUBRIMIENTO Y ETIQUETADO LIBRE EN TRAIN (SIN MIRAR VALIDACIÓN) ---
        d_tr = 0.35 * (
            Z_train[top9_local].mean(axis=0) - Z_train[bot9_local].mean(axis=0)
        ) + 0.65 * (
            Z_train[top60_local].mean(axis=0) - Z_train[bot60_local].mean(axis=0)
        )

        pos_axes = [int(i) for i in np.argsort(-d_tr)[:3] if d_tr[i] > 0.15]
        neg_axes = [int(i) for i in np.argsort(d_tr)[:3] if d_tr[i] < -0.15]
        w_tr_check = np.zeros(len(ORDEN_CLAVES_RASGOS), dtype=np.float64)
        pesos_ord = [1.0, 0.78, 0.58]
        for r_i, ax in enumerate(pos_axes):
            w_tr_check[ax] = pesos_ord[r_i]
        for r_i, ax in enumerate(neg_axes):
            w_tr_check[ax] = -pesos_ord[r_i]

        s_tr = Z_train @ w_tr_check
        y_tr_bin = (act_tr >= np.percentile(act_tr, 80.0)).astype(int)
        auc_tr = roc_auc_score_manual(y_tr_bin, s_tr)

        titulos_top_pos = [
            titulos_por_id.get(corpus_items[train_idx[i_loc]]["id_origen"], "")
            for i_loc in top9_local[:4]
        ]
        etiqueta = redactar_etiqueta_libre_train(canal, d_tr, auc_tr, titulos_top_pos)
        if etiqueta == "no lo sé":
            cnt_no_lo_se += 1

        # --- PRUEBA (b): Predicción ciega en las 189 imágenes de validación ---
        scores_val_03 = puntuar_validacion_solo_con_etiqueta(etiqueta, Z_val)
        act_val = pooled_val[:, canal]  # [189]
        umbral_top20_val = float(np.percentile(act_val, 80.0))
        y_val_bin = (act_val >= umbral_top20_val).astype(int)
        auc_val = (
            roc_auc_score_manual(y_val_bin, scores_val_03)
            if etiqueta != "no lo sé"
            else 0.5
        )
        confirmada_b = (etiqueta != "no lo sé") and (auc_val >= 0.70)

        legible = bool(confirmada_a and confirmada_b and etiqueta != "no lo sé")

        if confirmada_a:
            cnt_pass_a += 1
        if confirmada_b:
            cnt_pass_b += 1
        if legible:
            cnt_legibles += 1
        elif confirmada_a and not confirmada_b:
            cnt_solo_a += 1
        elif confirmada_b and not confirmada_a:
            cnt_solo_b += 1
        else:
            cnt_ni_a_ni_b += 1

        # Extraer parches receptivos 7x7 del conjunto train para el mosaico
        parches_pos: List[Image.Image] = []
        polo_pos_json: List[Dict[str, Any]] = []
        for rank_p, i_loc in enumerate(top9_local, start=1):
            g_idx = train_idx[i_loc]
            mapa_7x7 = f7_train[i_loc, canal]
            u_max, v_max = np.unravel_index(int(np.argmax(mapa_7x7)), (7, 7))
            parches_pos.append(
                _extraer_parche_receptivo(imagenes_224_pil[g_idx], int(u_max), int(v_max))
            )
            polo_pos_json.append(
                {
                    "rango": rank_p,
                    "id_pieza": corpus_items[g_idx]["id_origen"],
                    "sha256_imagen": corpus_items[g_idx]["sha256"],
                    "categoria": corpus_items[g_idx]["categoria"],
                    "url_pagina": corpus_items[g_idx]["url_pagina"],
                    "activacion_media": round(float(act_tr[i_loc]), 5),
                    "activacion_max_celda_7x7": round(float(mapa_7x7[u_max, v_max]), 5),
                    "celda_7x7": [int(u_max), int(v_max)],
                    "efecto_l2_al_apagar": round(float(efectos_por_img_x[rank_p - 1]), 5),
                }
            )

        parches_neg: List[Image.Image] = []
        polo_neg_json: List[Dict[str, Any]] = []
        for rank_n, i_loc in enumerate(bot9_local, start=1):
            g_idx = train_idx[i_loc]
            mapa_7x7 = f7_train[i_loc, canal]
            u_min, v_min = np.unravel_index(int(np.argmin(mapa_7x7)), (7, 7))
            parches_neg.append(
                _extraer_parche_receptivo(imagenes_224_pil[g_idx], int(u_min), int(v_min))
            )
            polo_neg_json.append(
                {
                    "rango": rank_n,
                    "id_pieza": corpus_items[g_idx]["id_origen"],
                    "sha256_imagen": corpus_items[g_idx]["sha256"],
                    "categoria": corpus_items[g_idx]["categoria"],
                    "url_pagina": corpus_items[g_idx]["url_pagina"],
                    "activacion_media": round(float(act_tr[i_loc]), 5),
                    "activacion_min_celda_7x7": round(float(mapa_7x7[u_min, v_min]), 5),
                    "celda_7x7": [int(u_min), int(v_min)],
                }
            )

        id_str = f"neurona_{canal:03d}"
        ruta_mosaico = carpeta_mosaicos_local / f"{id_str}.png"
        sha_mosaico = _guardar_mosaico_neurona(
            ruta_mosaico,
            canal=canal,
            etiqueta=etiqueta,
            legible=legible,
            conf_a=confirmada_a,
            conf_b=confirmada_b,
            wins_a=wins_a,
            auc_val=auc_val,
            parches_pos=parches_pos,
            parches_neg=parches_neg,
            acts_pos=[float(act_tr[i]) for i in top9_local],
            acts_neg=[float(act_tr[i]) for i in bot9_local],
        )

        conteo_03 = {
            str(v): int(np.sum(scores_val_03 == v)) for v in (0, 1, 2, 3)
        }

        ficha_pragma = {
            "schema_version": "2.0.0",
            "id_neurona": id_str,
            "canal_indice": canal,
            "modelo": "convnext_tiny",
            "etapa": "features.7",
            "modalidad_corpus": "cc0_630_train441_val189",
            "etiqueta": etiqueta,
            "etiquetador": "Argon",
            "legible": legible,
            "confirmada": legible,
            "confirmada_a": bool(confirmada_a),
            "confirmada_b": bool(confirmada_b),
            "fecha": FECHA_ATLAS,
            "sha256_pesos": sha_pesos,
            "licencia_pesos": LICENCIA_TORCHVISION,
            "sha256_prerregistro_v1": sha_prerreg_v1,
            "sha256_prerregistro_v2": sha_prerreg_v2,
            "sha256_corpus_cc0": sha_corpus_json,
            "sha256_mosaico_local": sha_mosaico,
            "prueba_a_apagado_control_justo": {
                "etapa_siguiente": "classifier (LayerNorm2d(768) -> Linear(768, 1000))",
                "activacion_media_abs_train": round(float(mean_abs_train[canal]), 5),
                "efecto_l2_neurona_x_top9_train": round(eff_x, 5),
                "ratio_medio_x_vs_controles": round(ratio_medio_a, 4),
                "sorteos_ganados_de_5": wins_a,
                "minimo_sorteos_requerido": 4,
                "factor_minimo_efecto": 2.0,
                "controles_y_sorteados": controles_json,
                "confirmada_a": bool(confirmada_a),
            },
            "prueba_b_prediccion_validacion_ciega": {
                "split_evaluado": "validacion (189 imágenes ciegas)",
                "escala_puntuacion": [0, 1, 2, 3],
                "conteo_puntuaciones_0_a_3": conteo_03,
                "positivos_reales_validacion_top20pct": int(np.sum(y_val_bin)),
                "roc_auc_validacion": auc_val,
                "umbral_auc_minimo": 0.70,
                "etiqueta_es_no_lo_se": bool(etiqueta == "no lo sé"),
                "confirmada_b": bool(confirmada_b),
            },
            "coherencia_descubrimiento_train": {
                "roc_auc_train": auc_tr,
                "umbral_claridad_train": 0.64,
            },
            "polo_pos": polo_pos_json,
            "polo_neg": polo_neg_json,
        }

        ruta_ficha = carpeta_atlas_salida / f"{id_str}.json"
        ruta_ficha.write_text(
            json.dumps(ficha_pragma, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        resumen_neuronas.append(
            {
                "id_neurona": id_str,
                "canal": canal,
                "etiqueta": etiqueta,
                "legible": legible,
                "confirmada_a": bool(confirmada_a),
                "confirmada_b": bool(confirmada_b),
                "wins_a": wins_a,
                "ratio_medio_a": round(ratio_medio_a, 3),
                "auc_val": auc_val,
                "auc_tr": auc_tr,
                "ruta_mosaico": str(ruta_mosaico),
                "sha256_mosaico": sha_mosaico,
            }
        )

    # Seleccionar 10 ejemplos: 5 legibles (pasan a y b) y 5 no legibles (variados: solo a, solo b, no lo sé)
    legibles_ord = sorted(
        [r for r in resumen_neuronas if r["legible"]],
        key=lambda x: (-x["auc_val"], -x["ratio_medio_a"], x["canal"]),
    )
    no_leg_solo_a_etq = sorted(
        [
            r
            for r in resumen_neuronas
            if (not r["legible"]) and r["confirmada_a"] and r["etiqueta"] != "no lo sé"
        ],
        key=lambda x: (x["auc_val"], x["canal"]),
    )
    no_leg_solo_b = sorted(
        [r for r in resumen_neuronas if (not r["legible"]) and r["confirmada_b"]],
        key=lambda x: (-x["auc_val"], x["canal"]),
    )
    no_leg_no_lo_se = sorted(
        [r for r in resumen_neuronas if r["etiqueta"] == "no lo sé"],
        key=lambda x: (x["auc_tr"], x["canal"]),
    )

    cinco_legibles = legibles_ord[:5]
    cinco_no_legibles = (
        no_leg_solo_a_etq[:2] + no_leg_solo_b[:1] + no_leg_no_lo_se[:2]
    )
    ejemplos_10 = cinco_legibles + cinco_no_legibles

    rutas_10_ejemplos: List[Dict[str, Any]] = []
    for idx_ej, ej in enumerate(ejemplos_10, start=1):
        src_p = Path(ej["ruta_mosaico"])
        tipo_tag = "legible" if ej["legible"] else "no_legible"
        dst_p = carpeta_10_ejemplos / f"ejemplo_{idx_ej:02d}_{tipo_tag}_{ej['id_neurona']}.png"
        dst_p.write_bytes(src_p.read_bytes())
        rutas_10_ejemplos.append(
            {
                "orden": idx_ej,
                "id_neurona": ej["id_neurona"],
                "canal": ej["canal"],
                "legible": ej["legible"],
                "confirmada_a": ej["confirmada_a"],
                "confirmada_b": ej["confirmada_b"],
                "sorteos_ganados_a": f"{ej['wins_a']}/5",
                "ratio_medio_a": ej["ratio_medio_a"],
                "auc_validacion_b": ej["auc_val"],
                "etiqueta": ej["etiqueta"],
                "archivo_mosaico": str(dst_p),
                "sha256_mosaico": ej["sha256_mosaico"],
            }
        )

    total_n = len(neuronas_ids)
    ic_leg = intervalo_confianza_wilson_95(cnt_legibles, total_n)
    ic_solo_a = intervalo_confianza_wilson_95(cnt_solo_a, total_n)
    ic_solo_b = intervalo_confianza_wilson_95(cnt_solo_b, total_n)
    ic_pass_a = intervalo_confianza_wilson_95(cnt_pass_a, total_n)
    ic_pass_b = intervalo_confianza_wilson_95(cnt_pass_b, total_n)

    informe = {
        "fase": "FASE 5b · Atlas con prueba de verdad (N-1 v2)",
        "fecha": FECHA_ATLAS,
        "modalidad_datos": "cc0_630_train441_val189",
        "num_imagenes_total": 630,
        "num_imagenes_train": 441,
        "num_imagenes_validacion": 189,
        "modelo": "convnext_tiny (ConvNeXt_Tiny_Weights.IMAGENET1K_V1)",
        "licencia_modelo_y_pesos": LICENCIA_TORCHVISION,
        "sha256_pesos": sha_pesos,
        "sha256_prerregistro_v1": sha_prerreg_v1,
        "sha256_prerregistro_v2": sha_prerreg_v2,
        "sha256_corpus_cc0": sha_corpus_json,
        "etapa": "features.7 (Stage 4, 768 canales)",
        "semilla": SEED,
        "total_neuronas_evaluadas": total_n,
        "neuronas_legibles_a_y_b": {
            "conteo": cnt_legibles,
            "porcentaje": round(cnt_legibles * 100.0 / total_n, 2),
            "ic_95_wilson_pct": [round(ic_leg[0] * 100.0, 2), round(ic_leg[1] * 100.0, 2)],
        },
        "neuronas_solo_a": {
            "conteo": cnt_solo_a,
            "porcentaje": round(cnt_solo_a * 100.0 / total_n, 2),
            "ic_95_wilson_pct": [round(ic_solo_a[0] * 100.0, 2), round(ic_solo_a[1] * 100.0, 2)],
        },
        "neuronas_solo_b": {
            "conteo": cnt_solo_b,
            "porcentaje": round(cnt_solo_b * 100.0 / total_n, 2),
            "ic_95_wilson_pct": [round(ic_solo_b[0] * 100.0, 2), round(ic_solo_b[1] * 100.0, 2)],
        },
        "neuronas_total_pasan_a": {
            "conteo": cnt_pass_a,
            "porcentaje": round(cnt_pass_a * 100.0 / total_n, 2),
            "ic_95_wilson_pct": [round(ic_pass_a[0] * 100.0, 2), round(ic_pass_a[1] * 100.0, 2)],
        },
        "neuronas_total_pasan_b": {
            "conteo": cnt_pass_b,
            "porcentaje": round(cnt_pass_b * 100.0 / total_n, 2),
            "ic_95_wilson_pct": [round(ic_pass_b[0] * 100.0, 2), round(ic_pass_b[1] * 100.0, 2)],
        },
        "neuronas_ni_a_ni_b": cnt_ni_a_ni_b,
        "neuronas_etiqueta_no_lo_se": cnt_no_lo_se,
        "nota_referencia_cammarata": "El ~90 % preliminar de Cammarata corresponde a Qwen3-32B en su ensayo de 2026 (no a Distill 2020).",
        "carpeta_mosaicos_local_no_commiteada": str(carpeta_mosaicos_local),
        "diez_ejemplos_5_legibles_5_no_legibles": rutas_10_ejemplos,
    }
    return informe


def main(argv: List[str] | None = None) -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Construye el Atlas de 200 neuronas con prueba de verdad (Fase 5b · N-1 v2)."
    )
    parser.add_argument(
        "--prerregistro-v2",
        default=str(base_dir / "prerregistro_v2.json"),
        help="Ruta a lab/neuronas/prerregistro_v2.json",
    )
    parser.add_argument(
        "--prerregistro-v1",
        default=str(base_dir / "prerregistro.json"),
        help="Ruta a lab/neuronas/prerregistro.json (intacto)",
    )
    parser.add_argument(
        "--corpus-json",
        default=str(base_dir / "corpus_cc0_630.json"),
        help="Ruta a lab/neuronas/corpus_cc0_630.json",
    )
    parser.add_argument(
        "--pesos",
        default="/tmp/neuronas_pesos/convnext_tiny-983f1562.pth",
        help="Ruta local a convnext_tiny-983f1562.pth (no se commitea a Git).",
    )
    parser.add_argument(
        "--imagenes-cc0",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/corpus-neuronas-cc0/imagenes",
        help="Ruta local (fuera de Git) a las 630 imágenes CC0.",
    )
    parser.add_argument(
        "--salida-atlas",
        default=str(base_dir / "atlas"),
        help="Carpeta donde escribir las 200 fichas PRAGMA lab/neuronas/atlas/<id>.json",
    )
    parser.add_argument(
        "--salida-mosaicos",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/neuronas-mosaicos",
        help="Carpeta local (fuera de Git) donde guardar los mosaicos PNG.",
    )
    parser.add_argument(
        "--cache-npz",
        default="/tmp/cache_630.npz",
        help="Caché local opcional de activaciones en /tmp.",
    )
    args = parser.parse_args(argv)

    informe = construir_atlas_fase5b(
        ruta_prerregistro_v2=Path(args.prerregistro_v2).expanduser().resolve(),
        ruta_prerregistro_v1=Path(args.prerregistro_v1).expanduser().resolve(),
        ruta_corpus_json=Path(args.corpus_json).expanduser().resolve(),
        ruta_pesos=Path(args.pesos).expanduser().resolve(),
        carpeta_imagenes_cc0=Path(args.imagenes_cc0).expanduser().resolve(),
        carpeta_atlas_salida=Path(args.salida_atlas).expanduser().resolve(),
        carpeta_mosaicos_local=Path(args.salida_mosaicos).expanduser().resolve(),
        ruta_cache_npz=Path(args.cache_npz) if args.cache_npz else None,
    )
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

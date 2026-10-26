#!/usr/bin/env python3
"""FASE 5 · Atlas piloto de neuronas (N-1 del carril Neuronas; CPU, 0 Colab).

Ejecuta ConvNeXt-tiny (pesos oficiales de torchvision BSD-3-Clause, sha256=983f1562...)
sobre el piloto reducido (las 22 piezas del corpus D-3) para las 200 neuronas de la
última etapa (features.7, 768 canales) prerregistradas con semilla 2610:
- Calcula para cada neurona el top-9 del polo + y el top-9 del polo − (guardando solo
  sha256 y activaciones en Git).
- Genera en carpeta local fuera de Git (~/Desktop/REFERENTES/neuronas-mosaicos/) los
  mosaicos visuales 3x3 (polo + frente a polo −) y copia 10 mosaicos de ejemplo.
- Asigna una etiqueta-verbo bipolar («<rasgo polo +> frente a <rasgo polo −>») basada
  en el discriminador perceptual dominante entre los parches receptivos del polo + y −,
  marcada con "etiquetador": "Argon".
- Ejecuta la prueba causal de apagado sobre la etapa siguiente (classifier): verifica si
  la caída media de activación en las top-9 imágenes es al menos el doble (>= 2.0x) que
  en las 9 imágenes control. Las que no pasan quedan con "confirmada": false y no se borran.
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


def _renderizar_especimen_ttf(ruta_ttf: Path) -> Image.Image:
    """Renderiza una lámina determinista 236x236 para las 4 piezas .ttf del corpus D-3."""
    im = Image.new("RGB", (236, 236), (246, 243, 236))
    draw = ImageDraw.Draw(im)
    try:
        f_grande = ImageFont.truetype(str(ruta_ttf), 42)
        f_med = ImageFont.truetype(str(ruta_ttf), 24)
        f_peq = ImageFont.truetype(str(ruta_ttf), 15)
    except Exception:
        f_grande = ImageFont.load_default()
        f_med = f_grande
        f_peq = f_grande

    draw.text((14, 16), "AaBbCcDd", font=f_grande, fill=(24, 22, 20))
    draw.text((14, 72), "EeFfGgHhIiJj", font=f_med, fill=(35, 32, 28))
    draw.text((14, 108), "KkLlMmNnÑñOoPp", font=f_med, fill=(35, 32, 28))
    draw.text((14, 144), "0123456789 ?!&", font=f_med, fill=(50, 45, 40))
    draw.text((14, 184), ruta_ttf.stem[:26], font=f_peq, fill=(80, 72, 64))
    return im


def preparar_corpus_224(carpeta_muestras: Path) -> List[Dict[str, Any]]:
    """Carga las 22 piezas del corpus D-3 y aplica el preprocesamiento oficial de ConvNeXt_Tiny_Weights
    (resize bilinear a 236x236, center crop 224x224, normalización ImageNet)."""
    archivos = sorted(
        p for p in carpeta_muestras.iterdir() if p.is_file() and not p.name.startswith(".")
    )
    items: List[Dict[str, Any]] = []
    mean_arr = np.asarray(IMAGENET_MEAN, dtype=np.float32).reshape(3, 1, 1)
    std_arr = np.asarray(IMAGENET_STD, dtype=np.float32).reshape(3, 1, 1)

    for idx, p in enumerate(archivos):
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if p.suffix.lower() in (".ttf", ".otf"):
            img_pil = _renderizar_especimen_ttf(p)
        else:
            with Image.open(p) as raw_im:
                img_pil = raw_im.convert("RGB")

        # Resize lado menor a 236 manteniendo aspecto + CenterCrop 224x224
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

        arr_u8 = np.asarray(im_224, dtype=np.uint8)
        arr_f = (arr_u8.astype(np.float32) / 255.0).transpose(2, 0, 1)
        tensor_norm = torch.from_numpy((arr_f - mean_arr) / std_arr)

        items.append(
            {
                "indice": idx,
                "id_pieza": f"d3_{idx + 1:02d}",
                "nombre_archivo": p.name,
                "sha256": sha,
                "tipo_pieza": "especimen_ttf" if p.suffix.lower() in (".ttf", ".otf") else "cartel_jpg",
                "imagen_224_pil": im_224,
                "arr_224_u8": arr_u8,
                "tensor": tensor_norm,
            }
        )
    return items


def _extraer_parche_receptivo(im_224: Image.Image, u_grid: int, v_grid: int, tam_parche: int = 96) -> Image.Image:
    """Extrae un parche centrado en la celda (u_grid, v_grid) del mapa 7x7 sobre la imagen 224x224."""
    cy = int(round((u_grid + 0.5) * 32.0))
    cx = int(round((v_grid + 0.5) * 32.0))
    mitad = tam_parche // 2
    x0 = max(0, min(224 - tam_parche, cx - mitad))
    y0 = max(0, min(224 - tam_parche, cy - mitad))
    return im_224.crop((x0, y0, x0 + tam_parche, y0 + tam_parche))


def _rasgos_visuales_parche(parche_pil: Image.Image) -> Dict[str, float]:
    """Mide 6 descriptores visuales interpretables sobre un parche 96x96 para generar la etiqueta-verbo."""
    arr = np.asarray(parche_pil, dtype=np.float32) / 255.0
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b

    gx = np.abs(lum[:, 2:] - lum[:, :-2])
    gy = np.abs(lum[2:, :] - lum[:-2, :])
    grad_mag = np.hypot(gx[1:-1, :], gy[:, 1:-1])

    # 1. Densidad de trazo / borde agudo (puntiagudo/anguloso vs liso/redondo)
    agudeza_borde = float(np.percentile(grad_mag, 90))
    # 2. Contraste tonal (claroscuro vs tono uniforme)
    contraste_tonal = float(np.std(lum))
    # 3. Luminosidad media (papel luminoso vs masa de tinta oscura)
    luminosidad = float(np.mean(lum))
    # 4. Saturación cromática (cromático vivo vs neutro acromático)
    max_rgb = np.maximum(np.maximum(r, g), b)
    min_rgb = np.minimum(np.minimum(r, g), b)
    saturacion = float(np.mean(max_rgb - min_rgb))
    # 5. Calidez cromática (cálido ocre/rojo vs frío azul/verde)
    calidez = float(np.mean(r - b))
    # 6. Orientación vertical vs horizontal de trazos
    anisotropia_vert = float(np.mean(gx) - np.mean(gy))

    return {
        "agudeza_borde": agudeza_borde,
        "contraste_tonal": contraste_tonal,
        "luminosidad": luminosidad,
        "saturacion": saturacion,
        "calidez": calidez,
        "anisotropia_vert": anisotropia_vert,
    }


def _construir_etiqueta_verbo_argon(
    parches_pos: List[Image.Image],
    parches_neg: List[Image.Image],
    canal: int,
) -> Tuple[str, Dict[str, float]]:
    """Sintetiza la etiqueta-verbo bipolar («<polo +> frente a <polo −>») midiendo qué eje perceptual
    separa con mayor magnitud de efecto (d de Cohen) el top-9 del polo + frente al top-9 del polo −."""
    r_pos = [_rasgos_visuales_parche(p) for p in parches_pos]
    r_neg = [_rasgos_visuales_parche(p) for p in parches_neg]

    catalogo_ejes = {
        "agudeza_borde": (
            "trazo puntiagudo y denso",
            "campo liso y redondeado",
        ),
        "contraste_tonal": (
            "recorte de alto claroscuro",
            "transición tonal suave",
        ),
        "luminosidad": (
            "espacio luminoso abierto",
            "masa de tinta profunda",
        ),
        "saturacion": (
            "acento cromático saturado",
            "superficie neutra apagada",
        ),
        "calidez": (
            "dominante cálida bermellón-ocre",
            "dominante fría azul-grisácea",
        ),
        "anisotropia_vert": (
            "fuste vertical estriado",
            "banda horizontal tendida",
        ),
    }

    efectos: Dict[str, float] = {}
    for clave in catalogo_ejes:
        vals_p = np.asarray([x[clave] for x in r_pos], dtype=np.float64)
        vals_n = np.asarray([x[clave] for x in r_neg], dtype=np.float64)
        diff = float(np.mean(vals_p) - np.mean(vals_n))
        std_pool = float(math.sqrt(0.5 * (np.var(vals_p) + np.var(vals_n))) + 1e-5)
        efectos[clave] = round(diff / std_pool, 4)

    # Ordenar ejes por magnitud absoluta de separación |d|
    orden_ejes = sorted(efectos.keys(), key=lambda k: abs(efectos[k]), reverse=True)
    eje_1 = orden_ejes[0]
    eje_2 = orden_ejes[1]

    pos_1, neg_1 = catalogo_ejes[eje_1]
    if efectos[eje_1] < 0:
        pos_1, neg_1 = neg_1, pos_1

    pos_2, neg_2 = catalogo_ejes[eje_2]
    if efectos[eje_2] < 0:
        pos_2, neg_2 = neg_2, pos_2

    # Combinar el eje primario con matiz del secundario para que cada neurona tenga descripción precisa
    corto_2_pos = pos_2.split()[0] + " " + pos_2.split()[-1]
    corto_2_neg = neg_2.split()[0] + " " + neg_2.split()[-1]
    etiqueta = f"{pos_1} ({corto_2_pos}) frente a {neg_1} ({corto_2_neg})"
    return etiqueta, efectos


def _guardar_mosaico_neurona(
    ruta_png: Path,
    canal: int,
    etiqueta: str,
    confirmada: bool,
    ratio_apagado: float,
    parches_pos: List[Image.Image],
    parches_neg: List[Image.Image],
    acts_pos: List[float],
    acts_neg: List[float],
) -> str:
    """Dibuja el mosaico 3x3 del polo + (izquierda) y 3x3 del polo − (derecha) y devuelve su SHA-256."""
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

    estado_txt = "CONFIRMADA" if confirmada else "NO CONFIRMADA"
    titulo = f"Neurona Stage4 ch{canal:03d} [{estado_txt} | ratio={ratio_apagado:.2f}x] · {etiqueta[:68]}"
    draw.text((pad_x, 10), titulo, fill=(240, 242, 245), font=font)
    draw.text(
        (pad_x, 32),
        f"POLO + (top-9, act max={acts_pos[0]:.3f}..{acts_pos[-1]:.3f})",
        fill=(110, 230, 145),
        font=font,
    )
    x_neg_ini = pad_x + grid_w + sep_central
    draw.text(
        (x_neg_ini, 32),
        f"POLO - (top-9, act min={acts_neg[0]:.3f}..{acts_neg[-1]:.3f})",
        fill=(245, 130, 130),
        font=font,
    )

    for idx in range(9):
        r = idx // 3
        c = idx % 3
        # Polo +
        xp = pad_x + c * (celda + gap)
        yp = pad_top + r * (celda + gap)
        p_pos = parches_pos[idx].resize((celda, celda), Image.Resampling.BILINEAR)
        lienzo.paste(p_pos, (xp, yp))
        draw.rectangle([xp, yp, xp + celda - 1, yp + celda - 1], outline=(80, 200, 120), width=1)

        # Polo -
        xn = x_neg_ini + c * (celda + gap)
        yn = pad_top + r * (celda + gap)
        p_neg = parches_neg[idx].resize((celda, celda), Image.Resampling.BILINEAR)
        lienzo.paste(p_neg, (xn, yn))
        draw.rectangle([xn, yn, xn + celda - 1, yn + celda - 1], outline=(210, 95, 95), width=1)

    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    lienzo.save(ruta_png, format="PNG")
    return hashlib.sha256(ruta_png.read_bytes()).hexdigest()


def intervalo_confianza_wilson_95(exitos: int, total: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    """Calcula el intervalo de confianza binomial al 95% de Wilson score para una proporción p = exitos/total."""
    if total <= 0:
        return 0.0, 0.0
    p = exitos / float(total)
    n = float(total)
    z2 = z * z
    denom = 1.0 + z2 / n
    centro = (p + z2 / (2.0 * n)) / denom
    margen = (z / denom) * math.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))
    return round(max(0.0, centro - margen), 4), round(min(1.0, centro + margen), 4)


def construir_atlas_piloto(
    ruta_prerregistro: Path,
    ruta_pesos: Path,
    carpeta_muestras: Path,
    carpeta_atlas_salida: Path,
    carpeta_mosaicos_local: Path,
) -> Dict[str, Any]:
    """Ejecuta el protocolo completo N-1 sobre las 200 neuronas prerregistradas."""
    prerreg = json.loads(ruta_prerregistro.read_text(encoding="utf-8"))
    sha_prerreg = hashlib.sha256(ruta_prerregistro.read_bytes()).hexdigest()
    neuronas_ids: List[int] = prerreg["muestreo_neuronas"]["neuronas_ids"]

    modelo, sha_pesos = cargar_modelo_convnext_tiny(ruta_pesos)
    items_corpus = preparar_corpus_224(carpeta_muestras)
    num_img = len(items_corpus)
    if num_img != 22:
        raise ValueError(f"Se esperaban 22 piezas en el corpus D-3, encontradas {num_img}")

    batch = torch.stack([it["tensor"] for it in items_corpus], dim=0)  # [22, 3, 224, 224]

    with torch.inference_mode():
        feat_stage4 = modelo.forward_hasta_ultima_etapa(batch)  # [22, 768, 7, 7]
        logits_base = modelo.forward_etapa_siguiente(feat_stage4)  # [22, 1000]
        feat_pooled = feat_stage4.mean(dim=(2, 3))  # [22, 768]

    # Matriz de pesos lineales de la etapa siguiente (classifier[2]: Linear(768, 1000))
    linear_cls: nn.Linear = modelo.classifier[2]  # type: ignore[assignment]
    w_cls = linear_cls.weight.detach().cpu().numpy()  # [1000, 768]

    feat_stage4_np = feat_stage4.detach().cpu().numpy()  # [22, 768, 7, 7]
    feat_pooled_np = feat_pooled.detach().cpu().numpy()  # [22, 768]
    logits_base_np = logits_base.detach().cpu().numpy()  # [22, 1000]

    carpeta_atlas_salida.mkdir(parents=True, exist_ok=True)
    carpeta_mosaicos_local.mkdir(parents=True, exist_ok=True)
    carpeta_10_ejemplos = carpeta_mosaicos_local / "10_ejemplos"
    carpeta_10_ejemplos.mkdir(parents=True, exist_ok=True)

    confirmadas_cnt = 0
    resumen_neuronas: List[Dict[str, Any]] = []

    for idx_n, canal in enumerate(neuronas_ids):
        acts_canal = feat_pooled_np[:, canal]  # [22]
        # Ordenar de mayor a menor activación (desempate determinista por índice)
        orden_desc = sorted(range(num_img), key=lambda i: (-float(acts_canal[i]), i))

        idx_top9_pos = orden_desc[:9]
        idx_control9 = orden_desc[6:15]
        # Polo negativo: las 9 de menor activación ordenadas de más negativa a menos negativa
        idx_top9_neg = list(reversed(orden_desc[-9:]))

        # Unidad k*_c de la etapa siguiente más excitada positivamente por la neurona c
        k_star = int(np.argmax(w_cls[:, canal]))

        # Prueba causal de apagado: poner a 0 el canal c en feat_stage4 y medir la etapa siguiente
        with torch.inference_mode():
            feat_ablat = feat_stage4.clone()
            feat_ablat[:, canal, :, :] = 0.0
            logits_ablat = modelo.forward_etapa_siguiente(feat_ablat).detach().cpu().numpy()

        caidas = np.maximum(0.0, logits_base_np[:, k_star] - logits_ablat[:, k_star])
        caida_media_top9 = float(np.mean(caidas[idx_top9_pos]))
        caida_media_control9 = float(np.mean(caidas[idx_control9]))
        ratio_apagado = caida_media_top9 / max(1e-9, caida_media_control9)

        confirmada = (caida_media_top9 > 0.0) and (
            caida_media_top9 >= 2.0 * caida_media_control9
        )
        if confirmada:
            confirmadas_cnt += 1

        # Extraer parches receptivos 7x7 para el top-9 del polo + y el top-9 del polo -
        parches_pos: List[Image.Image] = []
        polo_pos_json: List[Dict[str, Any]] = []
        for rank_p, i_img in enumerate(idx_top9_pos, start=1):
            mapa_7x7 = feat_stage4_np[i_img, canal]
            u_max, v_max = np.unravel_index(int(np.argmax(mapa_7x7)), (7, 7))
            parches_pos.append(_extraer_parche_receptivo(items_corpus[i_img]["imagen_224_pil"], int(u_max), int(v_max)))
            polo_pos_json.append(
                {
                    "rango": rank_p,
                    "id_pieza": items_corpus[i_img]["id_pieza"],
                    "sha256_imagen": items_corpus[i_img]["sha256"],
                    "activacion_media": round(float(acts_canal[i_img]), 5),
                    "activacion_max_celda_7x7": round(float(mapa_7x7[u_max, v_max]), 5),
                    "celda_7x7": [int(u_max), int(v_max)],
                    "caida_etapa_siguiente_al_apagar": round(float(caidas[i_img]), 5),
                }
            )

        parches_neg: List[Image.Image] = []
        polo_neg_json: List[Dict[str, Any]] = []
        for rank_n, i_img in enumerate(idx_top9_neg, start=1):
            mapa_7x7 = feat_stage4_np[i_img, canal]
            u_min, v_min = np.unravel_index(int(np.argmin(mapa_7x7)), (7, 7))
            parches_neg.append(_extraer_parche_receptivo(items_corpus[i_img]["imagen_224_pil"], int(u_min), int(v_min)))
            polo_neg_json.append(
                {
                    "rango": rank_n,
                    "id_pieza": items_corpus[i_img]["id_pieza"],
                    "sha256_imagen": items_corpus[i_img]["sha256"],
                    "activacion_media": round(float(acts_canal[i_img]), 5),
                    "activacion_min_celda_7x7": round(float(mapa_7x7[u_min, v_min]), 5),
                    "celda_7x7": [int(u_min), int(v_min)],
                }
            )

        etiqueta_verbo, efectos_ejes = _construir_etiqueta_verbo_argon(parches_pos, parches_neg, canal)

        id_str = f"neurona_{canal:03d}"
        ruta_mosaico = carpeta_mosaicos_local / f"{id_str}.png"
        sha_mosaico = _guardar_mosaico_neurona(
            ruta_mosaico,
            canal=canal,
            etiqueta=etiqueta_verbo,
            confirmada=confirmada,
            ratio_apagado=min(99.99, ratio_apagado),
            parches_pos=parches_pos,
            parches_neg=parches_neg,
            acts_pos=[float(acts_canal[i]) for i in idx_top9_pos],
            acts_neg=[float(acts_canal[i]) for i in idx_top9_neg],
        )

        ficha_pragma = {
            "schema_version": "1.0.0",
            "id_neurona": id_str,
            "canal_indice": canal,
            "modelo": "convnext_tiny",
            "etapa": "features.7",
            "modalidad_corpus": "piloto_reducido",
            "etiqueta": etiqueta_verbo,
            "etiquetador": "Argon",
            "confirmada": bool(confirmada),
            "fecha": FECHA_ATLAS,
            "sha256_pesos": sha_pesos,
            "licencia_pesos": LICENCIA_TORCHVISION,
            "sha256_prerregistro": sha_prerreg,
            "sha256_mosaico_local": sha_mosaico,
            "prueba_apagado": {
                "etapa_siguiente": "classifier (LayerNorm2d(768) -> Linear(768, 1000))",
                "unidad_excitada_k": k_star,
                "peso_conexion_w_kc": round(float(w_cls[k_star, canal]), 5),
                "caida_media_top9": round(caida_media_top9, 6),
                "caida_media_control9": round(caida_media_control9, 6),
                "ratio_top9_vs_control9": round(min(999.0, ratio_apagado), 4),
                "umbral_ratio_minimo": 2.0,
                "confirmada": bool(confirmada),
            },
            "discriminadores_visuales_d_cohen": efectos_ejes,
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
                "etiqueta": etiqueta_verbo,
                "confirmada": bool(confirmada),
                "caida_top9": round(caida_media_top9, 5),
                "caida_control9": round(caida_media_control9, 5),
                "ratio": round(min(999.0, ratio_apagado), 4),
                "ruta_mosaico": str(ruta_mosaico),
                "sha256_mosaico": sha_mosaico,
            }
        )

    # Seleccionar 10 mosaicos de ejemplo (8 confirmadas de mayor ratio + 2 no confirmadas para contraste honesto)
    conf_ordenadas = sorted(
        [r for r in resumen_neuronas if r["confirmada"]],
        key=lambda x: (-x["ratio"], x["canal"]),
    )
    no_conf_ordenadas = sorted(
        [r for r in resumen_neuronas if not r["confirmada"]],
        key=lambda x: (x["ratio"], x["canal"]),
    )
    ejemplos_10 = conf_ordenadas[:8] + no_conf_ordenadas[:2]
    if len(ejemplos_10) < 10:
        ejemplos_10 = resumen_neuronas[:10]

    rutas_10_ejemplos: List[Dict[str, Any]] = []
    for idx_ej, ej in enumerate(ejemplos_10, start=1):
        src_p = Path(ej["ruta_mosaico"])
        dst_p = carpeta_10_ejemplos / f"ejemplo_{idx_ej:02d}_{ej['id_neurona']}.png"
        dst_p.write_bytes(src_p.read_bytes())
        rutas_10_ejemplos.append(
            {
                "orden": idx_ej,
                "id_neurona": ej["id_neurona"],
                "confirmada": ej["confirmada"],
                "ratio_apagado": ej["ratio"],
                "etiqueta": ej["etiqueta"],
                "archivo_mosaico": str(dst_p),
                "sha256_mosaico": ej["sha256_mosaico"],
            }
        )

    total_n = len(neuronas_ids)
    prop_conf = confirmadas_cnt / float(total_n)
    ic_low, ic_high = intervalo_confianza_wilson_95(confirmadas_cnt, total_n)

    informe = {
        "fase": "FASE 5 · Atlas piloto de neuronas (N-1)",
        "fecha": FECHA_ATLAS,
        "modalidad_datos": "piloto_reducido",
        "num_piezas_corpus": num_img,
        "modelo": "convnext_tiny (ConvNeXt_Tiny_Weights.IMAGENET1K_V1)",
        "licencia_modelo_y_pesos": LICENCIA_TORCHVISION,
        "sha256_pesos": sha_pesos,
        "sha256_prerregistro": sha_prerreg,
        "etapa": "features.7 (Stage 4, 768 canales)",
        "semilla": SEED,
        "total_neuronas_evaluadas": total_n,
        "neuronas_confirmadas": confirmadas_cnt,
        "neuronas_no_confirmadas": total_n - confirmadas_cnt,
        "porcentaje_confirmadas": round(prop_conf * 100.0, 2),
        "intervalo_confianza_95_wilson_pct": [round(ic_low * 100.0, 2), round(ic_high * 100.0, 2)],
        "referencia_cammarata_2020_preliminar_pct": 90.0,
        "carpeta_mosaicos_local_no_commiteada": str(carpeta_mosaicos_local),
        "diez_mosaicos_ejemplo": rutas_10_ejemplos,
    }
    return informe


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construye el Atlas piloto de 200 neuronas (Fase 5 · N-1).")
    parser.add_argument(
        "--prerregistro",
        default=str(Path(__file__).resolve().parent / "prerregistro.json"),
        help="Ruta a lab/neuronas/prerregistro.json",
    )
    parser.add_argument(
        "--pesos",
        default="/tmp/neuronas_pesos/convnext_tiny-983f1562.pth",
        help="Ruta local a convnext_tiny-983f1562.pth (no se commitea a Git).",
    )
    parser.add_argument(
        "--muestras",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/corpus-editorial/muestras",
        help="Ruta a las 22 piezas del corpus D-3.",
    )
    parser.add_argument(
        "--salida-atlas",
        default=str(Path(__file__).resolve().parent / "atlas"),
        help="Carpeta donde escribir las 200 fichas PRAGMA lab/neuronas/atlas/<id>.json",
    )
    parser.add_argument(
        "--salida-mosaicos",
        default="/Users/gladys/.gemini/users/user1/Desktop/REFERENTES/neuronas-mosaicos",
        help="Carpeta local (fuera de Git) donde guardar los mosaicos PNG.",
    )
    args = parser.parse_args(argv)

    informe = construir_atlas_piloto(
        ruta_prerregistro=Path(args.prerregistro).expanduser().resolve(),
        ruta_pesos=Path(args.pesos).expanduser().resolve(),
        carpeta_muestras=Path(args.muestras).expanduser().resolve(),
        carpeta_atlas_salida=Path(args.salida_atlas).expanduser().resolve(),
        carpeta_mosaicos_local=Path(args.salida_mosaicos).expanduser().resolve(),
    )
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

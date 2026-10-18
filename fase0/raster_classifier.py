"""
PROMETEO · FASE 0 · DETERMINISTIC RASTER BACKGROUND SAFETY CLASSIFIER (§5, §6)
────────────────────────────────────────────────────────────────────────────────
Clasifica regiones objetivo de OCR para edición raster en tres clases canónicas:
  · RASTER_CLASS_A (SAFE_SIMPLE_BACKGROUND):
      Fondo uniforme/casi uniforme, texto aislado, sin líneas atravesando glifos,
      sin textura apreciable, suficiente contraste y resolución, OCR confiable.
      ÚNICA CLASE ELEGIBLE PARA EDICIÓN EN RASTER_PATCH_VERIFY_V0_1.
  · RASTER_CLASS_B (MODERATE_BACKGROUND):
      Gradiente suave, ruido moderado, textura repetitiva leve, artefactos de
      compresión, líneas próximas. Resultado: UNCERTAIN / HONEST_REJECT.
  · RASTER_CLASS_C (COMPLEX_OR_UNSAFE_BACKGROUND):
      Fotografía, textura irregular fuerte, sellos, firmas, marcas de agua,
      líneas de tabla/gráficos superpuestos, baja resolución, baja confianza OCR.
      Resultado: UNSAFE / HONEST_REJECT.

INVARIANTE:
  Deterministic / No-LLM / No-Neural. Evaluado estrictamente con métricas de imagen
  y umbrales pre-registrados en raster_verifier_profile_v0_1.json.
"""
from __future__ import annotations

import datetime
import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

cv2 = None
HAS_CV2 = False

try:
    import verifier2
except ImportError:
    from . import verifier2

# Constantes canónicas de taxonomía
RASTER_CLASS_A = "RASTER_CLASS_A"
RASTER_CLASS_B = "RASTER_CLASS_B"
RASTER_CLASS_C = "RASTER_CLASS_C"

SAFETY_SAFE = "SAFE"
SAFETY_UNCERTAIN = "UNCERTAIN"
SAFETY_UNSAFE = "UNSAFE"

# Reason Codes Formalizados (ORDEN 137 §26)
REASON_SAFE_UNIFORM = "SAFE_UNIFORM_BACKGROUND"
REASON_BG_TOO_COMPLEX = "BACKGROUND_TOO_COMPLEX"
REASON_EDGE_DENSITY_EXCEEDED = "EDGE_DENSITY_EXCEEDED"
REASON_RING_VARIANCE_EXCEEDED = "RING_VARIANCE_EXCEEDED"
REASON_GRADIENT_DETECTED = "BACKGROUND_GRADIENT_DETECTED"
REASON_PATCH_OVERLAPS_GRAPHIC = "PATCH_OVERLAPS_GRAPHIC"
REASON_OCR_CONFIDENCE_LOW = "OCR_CONFIDENCE_TOO_LOW"
REASON_OCR_CONFIDENCE_MARGINAL = "OCR_CONFIDENCE_MARGINAL"
REASON_TARGET_OUT_OF_BOUNDS = "TARGET_OUT_OF_BOUNDS"
REASON_TARGET_SIZE_IMPLAUSIBLE = "TARGET_SIZE_IMPLAUSIBLE"
REASON_BACKGROUND_MISMATCH = "BACKGROUND_SURROUNDING_MISMATCH"
REASON_PAGE_SKEW_DETECTED = "PAGE_SKEW_DETECTED"
REASON_UNSUPPORTED_RASTER = "UNSUPPORTED_RASTER_STRUCTURE"

_PROFILE_CACHE: Optional[Dict[str, Any]] = None



def load_verifier_profile(profile_path: Optional[str] = None) -> Dict[str, Any]:
    """Carga y cachea el perfil de verificación v0.1 con umbrales pre-registrados."""
    global _PROFILE_CACHE
    if _PROFILE_CACHE is not None and profile_path is None:
        return _PROFILE_CACHE

    if profile_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        profile_path = os.path.join(base_dir, "raster_verifier_profile_v0_1.json")

    with open(profile_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if profile_path.endswith("raster_verifier_profile_v0_1.json"):
        _PROFILE_CACHE = data
    return data


def _ensure_gray_array(image: Union[np.ndarray, Image.Image]) -> np.ndarray:
    """Convierte la entrada a un array 2D uint8 en escala de grises."""
    if isinstance(image, Image.Image):
        gray_img = image.convert("L")
        return np.array(gray_img, dtype=np.uint8)
    elif isinstance(image, np.ndarray):
        if image.ndim == 2:
            return image.astype(np.uint8)
        elif image.ndim == 3:
            if HAS_CV2 and image.shape[2] in (3, 4):
                if image.shape[2] == 4:
                    return cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)
                return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                # RGB a Gray por pesos ITU-R BT.601
                return np.dot(image[:, :, :3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)
    raise ValueError(f"Formato de imagen no soportado: {type(image)}")


def _compute_edge_density_and_gradient(ring_patch: np.ndarray, mask: np.ndarray) -> Tuple[float, float]:
    """Calcula la densidad de bordes y la magnitud de gradiente promedio en la máscara del anillo."""
    if not np.any(mask):
        return 0.0, 0.0

    if HAS_CV2:
        gx = cv2.Sobel(ring_patch, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(ring_patch, cv2.CV_32F, 0, 1, ksize=3)
        mag = np.sqrt(gx**2 + gy**2)
    else:
        # Fallback numpy gradient
        gy, gx = np.gradient(ring_patch.astype(np.float32))
        mag = np.sqrt(gx**2 + gy**2)

    ring_mag = mag[mask]
    if ring_mag.size == 0:
        return 0.0, 0.0

    # Píxeles con gradiente > 30 son considerados bordes significativos
    edge_pixels = np.sum(ring_mag > 30.0)
    edge_density = float(edge_pixels) / float(ring_mag.size)
    mean_gradient = float(np.mean(ring_mag))
    return edge_density, mean_gradient


def classify_raster_target(
    image: Union[np.ndarray, Image.Image],
    target_bbox_pt: Tuple[float, float, float, float],
    ocr_confidence: float = 85.0,
    page_size_pt: Optional[Tuple[float, float]] = None,
    dpi: float = 300.0,
    skew_deg: float = 0.0,
    profile_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Clasifica deterministamente una región objetivo de OCR.

    Args:
        image: Imagen completa de la página en espacio raster (e.g. 300 DPI).
        target_bbox_pt: Bounding box del target OCR en puntos (x0, y0, x1, y1).
        ocr_confidence: Confianza reportada por el OCR (0-100).
        page_size_pt: (width_pt, height_pt) opcional de la página.
        dpi: Resolución física de comparación (default 300 DPI).
        skew_deg: Ángulo de rotación/sesgo de la página o línea (grados).
        profile_path: Ruta al archivo JSON del perfil (opcional).


    Returns:
        Diccionario estructurado con clasificación, métricas, umbrales y reason codes.
    """
    profile = load_verifier_profile(profile_path)
    geom_cfg = profile.get("geometry", {})
    bg_cfg = profile.get("background_classifier", {})

    margin_pt = float(geom_cfg.get("margin_pt", 3.0))
    ring_width_px = int(geom_cfg.get("ring_width_px", 8))
    min_h_pt = float(geom_cfg.get("min_target_height_pt", 4.0))
    max_h_pt = float(geom_cfg.get("max_target_height_pt", 72.0))

    ring_var_max_a = float(bg_cfg.get("class_a_ring_variance_max", 25.0))
    ring_std_max_a = float(bg_cfg.get("class_a_ring_std_max", 5.0))
    edge_dens_max_a = float(bg_cfg.get("class_a_edge_density_max", 0.02))
    ring_delta_max_a = float(bg_cfg.get("class_a_ring_delta_max", 10.0))
    min_conf_a = float(bg_cfg.get("class_a_min_ocr_conf", 60.0))

    ring_var_max_b = float(bg_cfg.get("class_b_ring_variance_max", 180.0))
    edge_dens_max_b = float(bg_cfg.get("class_b_edge_density_max", 0.12))

    reasons: List[str] = []
    gray = _ensure_gray_array(image)
    img_h, img_w = gray.shape[:2]
    s = dpi / 72.0

    tx0, ty0, tx1, ty1 = target_bbox_pt
    target_w_pt = tx1 - tx0
    target_h_pt = ty1 - ty0

    # 1. Validación de geometría básica
    if target_w_pt <= 0 or target_h_pt <= 0:
        return {
            "safety_classification": SAFETY_UNSAFE,
            "raster_class": RASTER_CLASS_C,
            "edit_eligible": False,
            "target_bbox_pt": target_bbox_pt,
            "allowed_patch_bbox_pt": target_bbox_pt,
            "allowed_patch_bbox_px": (0, 0, 0, 0),
            "reasons": [REASON_TARGET_SIZE_IMPLAUSIBLE],
            "metrics": {"error": "dimensiones_no_positivas"},
            "thresholds": {},
            "profile_name": profile.get("profile_name", "RASTER_PATCH_VERIFY_V0_1"),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }

    if target_h_pt < min_h_pt or target_h_pt > max_h_pt:
        reasons.append(REASON_TARGET_SIZE_IMPLAUSIBLE)

    # 2. Calcular caja de parche permitido
    px0_pt = tx0 - margin_pt
    py0_pt = ty0 - margin_pt
    px1_pt = tx1 + margin_pt
    py1_pt = ty1 + margin_pt
    allowed_patch_bbox_pt = (px0_pt, py0_pt, px1_pt, py1_pt)

    px0 = int(round(px0_pt * s))
    py0 = int(round(py0_pt * s))
    px1 = int(round(px1_pt * s))
    py1 = int(round(py1_pt * s))
    allowed_patch_bbox_px = (px0, py0, px1, py1)

    # Bounds check contra dimensiones de imagen
    if px0 < 0 or py0 < 0 or px1 > img_w or py1 > img_h:
        reasons.append(REASON_TARGET_OUT_OF_BOUNDS)

    # Coordenadas seguras clamped para análisis
    cx0 = max(0, px0)
    cy0 = max(0, py0)
    cx1 = min(img_w, px1)
    cy1 = min(img_h, py1)

    # 3. Structural Line & Graphics Clearance Check
    structure_info = verifier2.line_structure_in_region(gray, (cx0, cy0, cx1, cy1))
    has_structure = bool(structure_info.get("has_structure", False))
    if has_structure:
        reasons.append(REASON_PATCH_OVERLAPS_GRAPHIC)

    # 4. Border Ring Analysis
    rx0 = max(0, cx0 - ring_width_px)
    ry0 = max(0, cy0 - ring_width_px)
    rx1 = min(img_w, cx1 + ring_width_px)
    ry1 = min(img_h, cy1 + ring_width_px)

    ring_patch = gray[ry0:ry1, rx0:rx1]
    rh, rw = ring_patch.shape

    ring_mask = np.ones((rh, rw), dtype=bool)
    # Excluir la región interior del parche permitido
    inner_y0 = cy0 - ry0
    inner_y1 = cy1 - ry0
    inner_x0 = cx0 - rx0
    inner_x1 = cx1 - rx0
    ring_mask[inner_y0:inner_y1, inner_x0:inner_x1] = False

    ring_pixels = ring_patch[ring_mask]

    if ring_pixels.size > 0:
        # Consideramos fondo los píxeles claros del anillo (>= 180) para evitar tinta externa
        # Pero medimos la varianza total del anillo para detectar texturas o gradientes
        ring_mean = float(np.mean(ring_pixels))
        ring_std = float(np.std(ring_pixels))
        ring_var = float(ring_std ** 2)
        ring_min = float(np.min(ring_pixels))
        ring_max = float(np.max(ring_pixels))
        ring_range = ring_max - ring_min

        # Píxeles de fondo en el anillo (excluyendo tinta de vecinos o del propio texto)
        bg_ring_pixels = ring_pixels[ring_pixels >= 180]
        if bg_ring_pixels.size > 0:
            bg_ring_mean = float(np.mean(bg_ring_pixels))
            bg_ring_std = float(np.std(bg_ring_pixels))
            bg_ring_var = float(bg_ring_std ** 2)
        else:
            bg_ring_mean = ring_mean
            bg_ring_std = ring_std
            bg_ring_var = ring_var
    else:
        ring_mean = 255.0
        ring_std = 0.0
        ring_var = 0.0
        ring_min = 255.0
        ring_max = 255.0
        ring_range = 0.0
        bg_ring_mean = 255.0
        bg_ring_std = 0.0
        bg_ring_var = 0.0

    # 5. Local Gradient & Edge Density en los píxeles de fondo del anillo
    bg_ring_mask = ring_mask & (ring_patch >= 180)
    edge_density, mean_gradient = _compute_edge_density_and_gradient(ring_patch, bg_ring_mask)

    # 6. Candidate Background in Interior Patch
    interior_patch = gray[cy0:cy1, cx0:cx1]
    if interior_patch.size > 0:
        interior_bg = interior_patch[interior_patch >= 180]
        interior_bg_mean = float(np.mean(interior_bg)) if interior_bg.size > 0 else float(np.mean(interior_patch))
        interior_bg_std = float(np.std(interior_bg)) if interior_bg.size > 0 else float(np.std(interior_patch))
    else:
        interior_bg_mean = bg_ring_mean
        interior_bg_std = 0.0

    ring_delta = abs(interior_bg_mean - bg_ring_mean)

    # 7. Evaluación de Umbrales
    if ocr_confidence < 40.0:
        reasons.append(REASON_OCR_CONFIDENCE_LOW)
    elif ocr_confidence < min_conf_a:
        reasons.append(REASON_OCR_CONFIDENCE_MARGINAL)

    # Usar varianza del fondo del anillo para evaluar textura/ruido del soporte
    if bg_ring_var > ring_var_max_a:
        if bg_ring_var > ring_var_max_b:
            reasons.append(REASON_BG_TOO_COMPLEX)
        else:
            reasons.append(REASON_RING_VARIANCE_EXCEEDED)

    if edge_density > edge_dens_max_a:
        reasons.append(REASON_EDGE_DENSITY_EXCEEDED)

    if ring_delta > ring_delta_max_a:
        reasons.append(REASON_BACKGROUND_MISMATCH)

    if abs(skew_deg) > 1.5:
        reasons.append(REASON_PAGE_SKEW_DETECTED)

    # 8. Determinación de Clase y Seguridad
    # Jerarquía: si hay falla estructural o textura excesiva -> CLASS C (UNSAFE)
    is_class_c = (
        has_structure
        or REASON_TARGET_OUT_OF_BOUNDS in reasons
        or REASON_TARGET_SIZE_IMPLAUSIBLE in reasons
        or REASON_OCR_CONFIDENCE_LOW in reasons
        or REASON_PAGE_SKEW_DETECTED in reasons
        or bg_ring_var > ring_var_max_b
        or edge_density > edge_dens_max_b
    )


    if is_class_c:
        safety = SAFETY_UNSAFE
        raster_class = RASTER_CLASS_C
        edit_eligible = False
    elif (
        bg_ring_var > ring_var_max_a
        or edge_density > edge_dens_max_a
        or ring_delta > ring_delta_max_a
        or REASON_OCR_CONFIDENCE_MARGINAL in reasons
    ):
        # Fondo moderado, gradiente o ruido -> CLASS B (UNCERTAIN)
        safety = SAFETY_UNCERTAIN
        raster_class = RASTER_CLASS_B
        edit_eligible = False
    else:
        # Todo cumple criterios de Clase A -> CLASS A (SAFE)
        safety = SAFETY_SAFE
        raster_class = RASTER_CLASS_A
        edit_eligible = True
        reasons = [REASON_SAFE_UNIFORM]

    metrics = {
        "ring_mean": round(ring_mean, 2),
        "ring_std": round(ring_std, 2),
        "ring_variance": round(ring_var, 2),
        "ring_range": round(ring_range, 2),
        "bg_ring_mean": round(bg_ring_mean, 2),
        "bg_ring_std": round(bg_ring_std, 2),
        "interior_bg_mean": round(interior_bg_mean, 2),
        "interior_bg_std": round(interior_bg_std, 2),
        "ring_delta": round(ring_delta, 2),
        "edge_density": round(edge_density, 4),
        "mean_gradient": round(mean_gradient, 2),
        "has_structure": has_structure,
        "ocr_confidence": round(ocr_confidence, 1),
        "target_size_pt": (round(target_w_pt, 2), round(target_h_pt, 2)),
    }

    thresholds = {
        "class_a_ring_variance_max": ring_var_max_a,
        "class_a_ring_std_max": ring_std_max_a,
        "class_a_edge_density_max": edge_dens_max_a,
        "class_a_ring_delta_max": ring_delta_max_a,
        "class_a_min_ocr_conf": min_conf_a,
        "class_b_ring_variance_max": ring_var_max_b,
        "class_b_edge_density_max": edge_dens_max_b,
        "margin_pt": margin_pt,
    }

    return {
        "safety_classification": safety,
        "raster_class": raster_class,
        "edit_eligible": edit_eligible,
        "target_bbox_pt": tuple(round(v, 2) for v in target_bbox_pt),
        "allowed_patch_bbox_pt": tuple(round(v, 2) for v in allowed_patch_bbox_pt),
        "allowed_patch_bbox_px": allowed_patch_bbox_px,
        "reasons": reasons,
        "metrics": metrics,
        "thresholds": thresholds,
        "profile_name": profile.get("profile_name", "RASTER_PATCH_VERIFY_V0_1"),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }

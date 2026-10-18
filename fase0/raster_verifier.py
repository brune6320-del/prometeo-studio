"""
PROMETEO · FASE 0 · PHYSICAL RASTER PATCH VERIFIER (§4, §19, §20, §21, §23, §24, §25)
─────────────────────────────────────────────────────────────────────────────────────
Implementa el verificador físico y el modelo de doble autoridad para parches raster:

  PHYSICAL CHECKS (Containment + Ring Stability + Background + Neighbor Preservation)
  +
  SEMANTIC READBACK (Independent OCR: new_text observed, old_text absent)
  → GLOBAL VERDICT (PASS / FAILED / HONEST_REJECT)

INVARIANTES ABSOLUTAS:
  1. ORIGINAL IMMUTABLE: El original debe permanecer bit-identical.
  2. OCR RESULT != PHYSICAL VERIFICATION: OCR solo mide observación semántica,
     nunca contención física ni preservación de fondo/gráficos.
  3. Contaminación fuera de allowed_patch_bbox produce FAIL incondicional.
  4. Doble autoridad: physical_pass AND semantic_pass requeridos para PASS global.
  5. Ataques adversariales (No-op, Tamper outside, False semantic, False physical)
     deben ser detectados deterministamente.
"""
from __future__ import annotations

import datetime
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pymupdf
from PIL import Image

try:
    from ocr_provider import OCRProvider, TesseractOCRProvider
    from raster_classifier import (
        load_verifier_profile,
        RASTER_CLASS_A,
    )
    from raster_operations import RasterReplaceText
    import verifier2
except ImportError:
    from fase0.ocr_provider import OCRProvider, TesseractOCRProvider
    from fase0.raster_classifier import (
        load_verifier_profile,
        RASTER_CLASS_A,
    )
    from fase0.raster_operations import RasterReplaceText
    from fase0 import verifier2

# Failure Reason Codes Formalizados (ORDEN 137 §26)
FAIL_OUTSIDE_CONTAMINATION = "OUTSIDE_PATCH_CONTAMINATION"
FAIL_NO_OP_DETECTED = "NO_OP_DETECTED"
FAIL_BORDER_RING_INSTABILITY = "BORDER_RING_INSTABILITY"
FAIL_BG_RECONSTRUCTION = "BACKGROUND_RECONSTRUCTION_FAILED"
FAIL_NEW_TEXT_NOT_CONFIRMED = "NEW_TEXT_NOT_CONFIRMED"
FAIL_OLD_TEXT_STILL_PRESENT = "OLD_TEXT_STILL_PRESENT"
FAIL_OCR_CONFIDENCE_LOW = "OCR_CONFIDENCE_TOO_LOW"
FAIL_TAMPER_DETECTED = "TAMPER_DETECTED"
FAIL_STRUCTURAL_CONTAMINATION = "STRUCTURAL_CONTAMINATION"
FAIL_UNSUPPORTED_STRUCTURE = "UNSUPPORTED_RASTER_STRUCTURE"
FAIL_PREFLIGHT_REJECTED = "PREFLIGHT_SAFETY_REJECTED"


def compute_physical_diff(
    before: np.ndarray,
    after: np.ndarray,
    allowed_patch_px: Tuple[int, int, int, int],
    intensity_tol: int = 20,
) -> Dict[str, Any]:
    """
    Calcula el diff físico pixel a pixel entre la página antes y después de la edición.
    Mide estrictamente la contención dentro de allowed_patch_px.
    """
    if before.shape != after.shape:
        raise ValueError(f"Discrepancia en dimensiones: before {before.shape} vs after {after.shape}")

    h, w = before.shape[:2]
    px0, py0, px1, py1 = allowed_patch_px
    px0, py0 = max(0, px0), max(0, py0)
    px1, py1 = min(w, px1), min(h, py1)

    diff_matrix = np.abs(after.astype(np.int16) - before.astype(np.int16))
    changed_mask = diff_matrix > intensity_tol
    changed_pixel_count = int(np.sum(changed_mask))

    allowed_mask = np.zeros((h, w), dtype=bool)
    allowed_mask[py0:py1, px0:px1] = True

    outside_changed_mask = changed_mask & ~allowed_mask
    outside_changed_pixel_count = int(np.sum(outside_changed_mask))

    inside_changed_mask = changed_mask & allowed_mask
    inside_changed_pixel_count = int(np.sum(inside_changed_mask))

    outside_deltas = diff_matrix[~allowed_mask]
    max_outside_delta = int(np.max(outside_deltas)) if outside_deltas.size > 0 else 0
    mean_outside_delta = float(np.mean(outside_deltas)) if outside_deltas.size > 0 else 0.0

    # Bounding box del cambio total
    ys, xs = np.where(changed_mask)
    if len(xs) > 0:
        change_bbox_px = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    else:
        change_bbox_px = (0, 0, 0, 0)

    containment_pass = (outside_changed_pixel_count == 0)

    return {
        "changed_pixel_count": changed_pixel_count,
        "inside_patch_changed_pixel_count": inside_changed_pixel_count,
        "outside_patch_changed_pixel_count": outside_changed_pixel_count,
        "max_outside_delta": max_outside_delta,
        "mean_outside_delta": round(mean_outside_delta, 4),
        "change_bbox_px": change_bbox_px,
        "allowed_patch_bbox_px": (px0, py0, px1, py1),
        "containment_pass": containment_pass,
    }


def verify_border_ring_stability(
    before: np.ndarray,
    after: np.ndarray,
    allowed_patch_px: Tuple[int, int, int, int],
    ring_width_px: int = 8,
    mae_max: float = 2.5,
    max_delta_threshold: float = 20.0,
) -> Dict[str, Any]:
    """
    Verifica que el anillo perimetral alrededor de allowed_patch_px permanezca
    materialmente estable entre el render original y el resultado exportado.
    """
    h, w = before.shape[:2]
    px0, py0, px1, py1 = allowed_patch_px

    rx0, ry0 = max(0, px0 - ring_width_px), max(0, py0 - ring_width_px)
    rx1, ry1 = min(w, px1 + ring_width_px), min(h, py1 + ring_width_px)

    ring_mask = np.ones((ry1 - ry0, rx1 - rx0), dtype=bool)
    iy0, iy1 = max(0, py0 - ry0), min(ry1 - ry0, py1 - ry0)
    ix0, ix1 = max(0, px0 - rx0), min(rx1 - rx0, px1 - rx0)
    ring_mask[iy0:iy1, ix0:ix1] = False

    before_ring = before[ry0:ry1, rx0:rx1][ring_mask]
    after_ring = after[ry0:ry1, rx0:rx1][ring_mask]

    if before_ring.size == 0:
        return {
            "border_ring_mae": 0.0,
            "border_ring_max_delta": 0.0,
            "border_ring_pass": True,
            "ring_pixels_count": 0,
        }

    deltas = np.abs(after_ring.astype(np.int16) - before_ring.astype(np.int16))
    mae = float(np.mean(deltas))
    max_delta = float(np.max(deltas))
    ring_pass = (mae <= mae_max) and (max_delta <= max_delta_threshold)

    return {
        "border_ring_mae": round(mae, 3),
        "border_ring_max_delta": round(max_delta, 2),
        "border_ring_pass": ring_pass,
        "ring_pixels_count": int(before_ring.size),
    }


def verify_background_reconstruction_quality(
    after: np.ndarray,
    target_rect_px: Tuple[int, int, int, int],
    allowed_patch_px: Tuple[int, int, int, int],
    ring_width_px: int = 8,
    residual_max: float = 15.0,
) -> Dict[str, Any]:
    """
    Verifica que el fondo reconstruido en la zona del texto modificado sea
    físicamente coherente con el fondo circundante del anillo perimetral.
    """
    h, w = after.shape[:2]
    px0, py0, px1, py1 = allowed_patch_px
    tx0, ty0, tx1, ty1 = target_rect_px

    rx0, ry0 = max(0, px0 - ring_width_px), max(0, py0 - ring_width_px)
    rx1, ry1 = min(w, px1 + ring_width_px), min(h, py1 + ring_width_px)

    ring_mask = np.ones((ry1 - ry0, rx1 - rx0), dtype=bool)
    iy0, iy1 = max(0, py0 - ry0), min(ry1 - ry0, py1 - ry0)
    ix0, ix1 = max(0, px0 - rx0), min(rx1 - rx0, px1 - rx0)
    ring_mask[iy0:iy1, ix0:ix1] = False

    ring_vals = after[ry0:ry1, rx0:rx1][ring_mask]
    bg_ring = ring_vals[ring_vals >= 180] if np.any(ring_vals >= 180) else ring_vals

    ring_bg_mean = float(np.mean(bg_ring)) if bg_ring.size > 0 else 255.0

    target_vals = after[max(0, ty0):min(h, ty1), max(0, tx0):min(w, tx1)]
    target_bg = target_vals[target_vals >= 180] if np.any(target_vals >= 180) else target_vals
    target_bg_mean = float(np.mean(target_bg)) if target_bg.size > 0 else 255.0

    residual = abs(target_bg_mean - ring_bg_mean)
    bg_pass = residual <= residual_max

    return {
        "ring_bg_mean": round(ring_bg_mean, 2),
        "target_bg_mean": round(target_bg_mean, 2),
        "background_residual": round(residual, 2),
        "background_pass": bg_pass,
    }


def verify_semantic_readback(
    after: np.ndarray,
    expected_text: str,
    old_text: str,
    region_px: Tuple[int, int, int, int],
    provider: Optional[OCRProvider] = None,
    min_confidence: float = 50.0,
    cer_max: float = 0.34,
) -> Dict[str, Any]:
    """
    Ejecuta el readback OCR secundario e independiente sobre el documento exportado.
    Garantiza que el texto esperado sea observado y el texto anterior haya desaparecido.
    """
    if provider is None:
        provider = TesseractOCRProvider()

    img_pil = Image.fromarray(after, "L")
    readback_raw = verifier2.ocr_readback(
        provider=provider,
        image=img_pil,
        expected_text=expected_text,
        region_px=region_px,
    )

    found = bool(readback_raw.get("found", False))
    best = readback_raw.get("best") or {}
    observed_text = best.get("text", "")
    conf = float(best.get("conf", 0.0))
    cer = float(best.get("cer", 1.0))

    new_text_observed = found and (cer <= cer_max)
    # El texto anterior no debe aparecer en la línea observada de la región
    old_lower = old_text.strip().lower()
    obs_lower = observed_text.strip().lower()
    old_text_absent = (old_lower not in obs_lower) if old_lower else True
    confidence_pass = conf >= min_confidence

    semantic_pass = new_text_observed and old_text_absent and confidence_pass

    return {
        "semantic_pass": semantic_pass,
        "new_text_observed": new_text_observed,
        "old_text_absent": old_text_absent,
        "confidence_pass": confidence_pass,
        "observed_text": observed_text,
        "cer": round(cer, 4),
        "confidence": round(conf, 1),
        "provider": provider.name,
    }


def verify_raster_patch(
    source_pdf_bytes: bytes,
    exported_pdf_bytes: bytes,
    op: RasterReplaceText,
    dpi: float = 300.0,
    ocr_provider: Optional[OCRProvider] = None,
    profile_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    VERIFICADOR FÍSICO Y MODELO DE DOBLE AUTORIDAD PARA PARCHES RASTER.
    Reabre materialmente ambos documentos y mide todas las dimensiones.
    """
    profile = load_verifier_profile(profile_path)
    phys_cfg = profile.get("physical_verifier", {})
    sem_cfg = profile.get("semantic_readback", {})
    geom_cfg = profile.get("geometry", {})

    intensity_tol = int(phys_cfg.get("outside_pixel_intensity_tol", 20))
    ring_width_px = int(geom_cfg.get("ring_width_px", 8))
    mae_max = float(phys_cfg.get("border_ring_mae_max", 2.5))
    max_delta_thresh = float(phys_cfg.get("border_ring_max_delta", 20.0))
    residual_max = float(phys_cfg.get("background_residual_max", 15.0))
    min_sem_conf = float(sem_cfg.get("min_confidence", 50.0))
    cer_max = float(sem_cfg.get("cer_max", 0.34))

    reasons: List[str] = []
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"

    # 1. Reabrir físicamente ambos PDFs y renderizar en espacio canónico
    src_doc = pymupdf.open(stream=source_pdf_bytes, filetype="pdf")
    exp_doc = pymupdf.open(stream=exported_pdf_bytes, filetype="pdf")

    if op.page < 0 or op.page >= len(src_doc) or op.page >= len(exp_doc):
        src_doc.close()
        exp_doc.close()
        return {
            "profile": profile.get("profile_name", "RASTER_PATCH_VERIFY_V0_1"),
            "status": "FAILED",
            "physical_pass": False,
            "semantic_pass": False,
            "reasons": [FAIL_UNSUPPORTED_STRUCTURE],
            "metrics": {"error": "page_index_out_of_range"},
            "timestamp": timestamp,
        }

    src_pix = src_doc[op.page].get_pixmap(dpi=int(dpi), colorspace=pymupdf.csGRAY)
    exp_pix = exp_doc[op.page].get_pixmap(dpi=int(dpi), colorspace=pymupdf.csGRAY)

    before_np = np.frombuffer(src_pix.samples, dtype=np.uint8).reshape(src_pix.height, src_pix.width).copy()
    after_np = np.frombuffer(exp_pix.samples, dtype=np.uint8).reshape(exp_pix.height, exp_pix.width).copy()

    src_doc.close()
    exp_doc.close()

    s = dpi / 72.0
    tx0, ty0, tx1, ty1 = [int(round(v * s)) for v in op.target_bbox]
    px0, py0, px1, py1 = [int(round(v * s)) for v in op.allowed_patch_bbox]

    # 2. Physical Pixel Diff & Containment
    diff_res = compute_physical_diff(
        before=before_np,
        after=after_np,
        allowed_patch_px=(px0, py0, px1, py1),
        intensity_tol=intensity_tol,
    )

    # Detección de Ataque No-Op: el archivo cambió metadata pero los píxeles están idénticos
    if diff_res["changed_pixel_count"] == 0:
        reasons.append(FAIL_NO_OP_DETECTED)

    # Detección de Contaminación Exterior (Tamper fuera del patch)
    if not diff_res["containment_pass"]:
        reasons.append(FAIL_OUTSIDE_CONTAMINATION)

    # 3. Border Ring Stability Check
    ring_res = verify_border_ring_stability(
        before=before_np,
        after=after_np,
        allowed_patch_px=(px0, py0, px1, py1),
        ring_width_px=ring_width_px,
        mae_max=mae_max,
        max_delta_threshold=max_delta_thresh,
    )
    if not ring_res["border_ring_pass"]:
        reasons.append(FAIL_BORDER_RING_INSTABILITY)

    # 4. Background Reconstruction Check
    bg_res = verify_background_reconstruction_quality(
        after=after_np,
        target_rect_px=(tx0, ty0, tx1, ty1),
        allowed_patch_px=(px0, py0, px1, py1),
        ring_width_px=ring_width_px,
        residual_max=residual_max,
    )
    if not bg_res["background_pass"]:
        reasons.append(FAIL_BG_RECONSTRUCTION)

    # Veredicto Físico
    physical_pass = (
        diff_res["containment_pass"]
        and diff_res["changed_pixel_count"] > 0
        and ring_res["border_ring_pass"]
        and bg_res["background_pass"]
    )

    # 5. Semantic OCR Readback (Secondary Check)
    # Región de lectura alrededor del patch permitido con margen
    readback_region_px = (
        max(0, px0 - int(20 * s)),
        max(0, py0 - int(10 * s)),
        min(after_np.shape[1], px1 + int(40 * s)),
        min(after_np.shape[0], py1 + int(10 * s)),
    )
    readback_res = verify_semantic_readback(
        after=after_np,
        expected_text=op.new_text,
        old_text=op.old_observed_text,
        region_px=readback_region_px,
        provider=ocr_provider,
        min_confidence=min_sem_conf,
        cer_max=cer_max,
    )

    if not readback_res["new_text_observed"]:
        reasons.append(FAIL_NEW_TEXT_NOT_CONFIRMED)
    if not readback_res["old_text_absent"]:
        reasons.append(FAIL_OLD_TEXT_STILL_PRESENT)
    if not readback_res["confidence_pass"]:
        reasons.append(FAIL_OCR_CONFIDENCE_LOW)

    semantic_pass = readback_res["semantic_pass"]

    # 6. Double Authority Model: Global Verdict
    global_pass = physical_pass and semantic_pass
    status = "PASS" if global_pass else "FAILED"

    # Invariante de Hash Original
    src_hash = hashlib.sha256(source_pdf_bytes).hexdigest()
    exp_hash = hashlib.sha256(exported_pdf_bytes).hexdigest()

    metrics = {
        "changed_pixel_count": diff_res["changed_pixel_count"],
        "outside_patch_changed_pixel_count": diff_res["outside_patch_changed_pixel_count"],
        "max_outside_delta": diff_res["max_outside_delta"],
        "border_ring_mae": ring_res["border_ring_mae"],
        "border_ring_max_delta": ring_res["border_ring_max_delta"],
        "background_residual": bg_res["background_residual"],
        "readback_cer": readback_res["cer"],
        "readback_confidence": readback_res["confidence"],
    }

    evidence = {
        "source_sha256": src_hash,
        "exported_sha256": exp_hash,
        "dpi": dpi,
        "change_bbox_px": diff_res["change_bbox_px"],
        "allowed_patch_bbox_px": (px0, py0, px1, py1),
        "observed_readback_text": readback_res["observed_text"],
    }

    return {
        "profile": profile.get("profile_name", "RASTER_PATCH_VERIFY_V0_1"),
        "status": status,
        "physical_pass": physical_pass,
        "semantic_pass": semantic_pass,
        "containment": diff_res,
        "border_ring": ring_res,
        "background": bg_res,
        "ocr_readback": readback_res,
        "metrics": metrics,
        "evidence": evidence,
        "reasons": reasons,
        "timestamp": timestamp,
    }

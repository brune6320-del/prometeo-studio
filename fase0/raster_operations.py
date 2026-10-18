"""
PROMETEO · FASE 0 · RASTER MUTATION & REPLACEMENT OPERATION (§10, §11, §12, §16)
─────────────────────────────────────────────────────────────────────────────────
Define el tipo de operación RasterReplaceText, su contrato de preflight y la
estrategia de mutación física conservadora.

REGLAS CRÍTICAS:
  1. No reutilizar ReplaceText born-digital fingiendo que ambas operaciones son iguales.
  2. No usar 'white rectangle a ciegas'. El fondo solo se reconstruye si pasa el
     Safety Classifier de Clase A.
  3. La mutación está confinada 100% a ALLOWED_PATCH_MASK. Cualquier cambio material
     fuera de esa máscara produce FAIL.
  4. La tipografía nueva se etiqueta explícitamente como APPROXIMATED_FONT.
  5. Se genera un paquete de evidencia pre-edit estructurado.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import io
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pymupdf
from PIL import Image

try:
    from render import FontBook
except ImportError:
    from fase0.render import FontBook

try:
    from raster_classifier import (
        classify_raster_target,
        load_verifier_profile,
        RASTER_CLASS_A,
        SAFETY_SAFE,
        REASON_SAFE_UNIFORM,
    )
except ImportError:
    from fase0.raster_classifier import (
        classify_raster_target,
        load_verifier_profile,
        RASTER_CLASS_A,
        SAFETY_SAFE,
        REASON_SAFE_UNIFORM,
    )

DPI = 300.0
INK_BOX_RATIO = 0.76
DESCENDER_RATIO = 0.22


@dataclasses.dataclass
class RasterReplaceText:
    """Operación canónica de reemplazo de texto en páginas raster."""
    document_id: str
    page: int
    observation_id: str
    old_observed_text: str
    new_text: str
    target_bbox: Tuple[float, float, float, float]
    allowed_patch_bbox: Tuple[float, float, float, float]
    background_class: str = RASTER_CLASS_A
    font_family: str = "helv"
    font_size_pt: Optional[float] = None
    verification_profile: str = "RASTER_PATCH_VERIFY_V0_1"
    provenance: Optional[Dict[str, Any]] = None
    applied_at: Optional[str] = None
    patch_id: Optional[str] = None

    def __post_init__(self):
        if not self.patch_id:
            self.patch_id = f"rpatch_{uuid.uuid4().hex[:10]}"
        if not self.applied_at:
            self.applied_at = datetime.datetime.utcnow().isoformat() + "Z"

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def _dummy_fontbook() -> FontBook:
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    return FontBook(doc, page)


def render_approximated_text_patch(
    text: str,
    size_pt: float,
    dpi: float = DPI,
    font_name: str = "helv",
) -> Tuple[np.ndarray, float, float]:
    """
    Renderiza texto determinista dentro de un patch bitmap a la resolución indicada.
    Devuelve (grayscale_array, baseline_y_px, width_px).
    """
    fb = _dummy_fontbook()
    font = fb.font_for(font_name)
    width_pt = font.text_length(text, fontsize=size_pt)
    pad = size_pt * 0.2
    page_w = width_pt + 2 * pad
    page_h = size_pt * 1.5

    doc = pymupdf.open()
    page = doc.new_page(width=page_w, height=page_h)
    fb_doc = FontBook(doc, page)
    baseline_y_pt = size_pt * 1.15
    fb_doc.write(page, (pad, baseline_y_pt), text, font_name, size_pt, 0)
    pix = page.get_pixmap(dpi=int(dpi), colorspace=pymupdf.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()

    s = dpi / 72.0
    baseline_y_px = baseline_y_pt * s
    width_px = width_pt * s
    return arr, baseline_y_px, width_px


def reconstruct_class_a_background(
    image: np.ndarray,
    target_rect_px: Tuple[int, int, int, int],
    allowed_patch_px: Tuple[int, int, int, int],
    ring_width_px: int = 8,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Reconstruye el fondo para CLASS A de forma estrictamente conservadora:
    obtiene el valor robusto del color de fondo del anillo exterior y rellena
    la región de tinta anterior, preservando los píxeles circundantes.
    """
    h, w = image.shape[:2]
    tx0, ty0, tx1, ty1 = target_rect_px
    px0, py0, px1, py1 = allowed_patch_px

    # Extraer anillo exterior al parche permitido
    rx0, ry0 = max(0, px0 - ring_width_px), max(0, py0 - ring_width_px)
    rx1, ry1 = min(w, px1 + ring_width_px), min(h, py1 + ring_width_px)

    ring_patch = image[ry0:ry1, rx0:rx1]
    rh, rw = ring_patch.shape

    ring_mask = np.ones((rh, rw), dtype=bool)
    inner_y0, inner_y1 = max(0, py0 - ry0), min(rh, py1 - ry0)
    inner_x0, inner_x1 = max(0, px0 - rx0), min(rw, px1 - rx0)
    ring_mask[inner_y0:inner_y1, inner_x0:inner_x1] = False

    ring_vals = ring_patch[ring_mask]
    # Filtrar tinta exterior (asumimos fondo claro >= 180 si es scan de texto oscuro)
    bg_vals = ring_vals[ring_vals >= 180] if np.any(ring_vals >= 180) else ring_vals

    if bg_vals.size > 0:
        fill_val = int(round(float(np.median(bg_vals))))
    else:
        fill_val = 255

    reconstructed = image.copy()
    # Rellenar estrictamente la caja del texto objetivo (clamped a allowed patch)
    fx0, fy0 = max(px0, tx0), max(py0, ty0)
    fx1, fy1 = min(px1, tx1), min(py1, ty1)
    reconstructed[fy0:fy1, fx0:fx1] = fill_val

    meta = {
        "fill_color": fill_val,
        "strategy": "robust_median_ring_fill",
        "erased_rect_px": (fx0, fy0, fx1, fy1),
    }
    return reconstructed, meta


def apply_raster_patch(
    image: np.ndarray,
    op: RasterReplaceText,
    dpi: float = DPI,
    profile_path: Optional[str] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Aplica materialmente un parche de texto sobre una imagen raster.
    Garantía: La mutación sólo altera píxeles dentro de allowed_patch_bbox.

    Returns:
        (after_np, patch_evidence_package)
    """
    profile = load_verifier_profile(profile_path)
    s = dpi / 72.0
    h, w = image.shape[:2]

    # Preflight Safety Classification
    safety_info = classify_raster_target(
        image=image,
        target_bbox_pt=op.target_bbox,
        ocr_confidence=op.provenance.get("confidence", 85.0) if op.provenance else 85.0,
        dpi=dpi,
        profile_path=profile_path,
    )

    if not safety_info["edit_eligible"]:
        raise ValueError(
            f"Preflight Safety Check RECHAZADO: clasificación {safety_info['safety_classification']} "
            f"({safety_info['raster_class']}), razones: {safety_info['reasons']}"
        )

    # Conversión a píxeles
    tx0, ty0, tx1, ty1 = [int(round(v * s)) for v in op.target_bbox]
    px0, py0, px1, py1 = [int(round(v * s)) for v in op.allowed_patch_bbox]

    # 1. Reconstrucción conservadora del fondo
    erased_img, bg_meta = reconstruct_class_a_background(
        image, (tx0, ty0, tx1, ty1), (px0, py0, px1, py1)
    )

    # 2. Estimación tipográfica y renderizado de texto aproximado
    target_h_pt = op.target_bbox[3] - op.target_bbox[1]
    font_size_pt = max(4.0, target_h_pt / INK_BOX_RATIO)
    target_w_pt = op.target_bbox[2] - op.target_bbox[0]

    # Ajustar tamaño para que el texto nuevo quepa dentro de la caja objetivo
    fb = _dummy_fontbook()
    font = fb.font_for("helv")
    raw_w_pt = font.text_length(op.new_text, fontsize=font_size_pt)
    max_w_pt = max(4.0, target_w_pt)
    if raw_w_pt > max_w_pt:
        font_size_pt = max(4.0, font_size_pt * (max_w_pt / raw_w_pt))

    patch_arr, base_in_patch, patch_w_px = render_approximated_text_patch(
        text=op.new_text,
        size_pt=font_size_pt,
        dpi=dpi,
        font_name="helv",
    )

    # Posicionar texto dentro de allowed_patch:
    # render_approximated_text_patch aplica pad = size_pt * 0.2 a la izquierda
    pad_pt = font_size_pt * 0.2
    pad_px = int(round(pad_pt * s))
    insert_x_px = tx0
    baseline_y_px = int(round((op.target_bbox[3] - DESCENDER_RATIO * font_size_pt) * s))
    y0 = int(round(baseline_y_px - base_in_patch))
    x0 = insert_x_px - pad_px


    # Componer tinta nueva estrictamente dentro de allowed_patch_bbox
    ink_mask = patch_arr < 200
    ph, pw = patch_arr.shape
    ys, xs = np.where(ink_mask)

    after = erased_img.copy()
    if len(xs) > 0:
        sub_y0 = max(py0, y0 + int(ys.min()))
        sub_y1 = min(py1, y0 + int(ys.max()) + 1)
        sub_x0 = max(px0, x0 + int(xs.min()))
        sub_x1 = min(px1, x0 + int(xs.max()) + 1)

        if sub_y1 > sub_y0 and sub_x1 > sub_x0:
            patch_sub = patch_arr[(sub_y0 - y0):(sub_y1 - y0), (sub_x0 - x0):(sub_x1 - x0)]
            ink_sub = patch_sub < 200
            target_region = after[sub_y0:sub_y1, sub_x0:sub_x1]
            # Mezclar tinta oscura (valor 25 o mínimo con píxel actual)
            target_region[ink_sub] = np.minimum(target_region[ink_sub], 25)

    evidence_package = {
        "patch_id": op.patch_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "operation": op.as_dict(),
        "preflight_safety": safety_info,
        "background_reconstruction": bg_meta,
        "typography": {
            "font_claim": "APPROXIMATED_FONT",
            "font_used": "Helvetica (helv)",
            "estimated_size_pt": round(font_size_pt, 2),
            "baseline_px": baseline_y_px,
            "color": "0 (black)",
        },
        "allowed_patch_rect_px": (px0, py0, px1, py1),
    }

    return after, evidence_package


def mutate_pdf_page_with_patch(
    pdf_bytes: bytes,
    page_idx: int,
    op: RasterReplaceText,
    dpi: float = DPI,
    profile_path: Optional[str] = None,
) -> Tuple[bytes, np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Aplica una mutación raster sobre una página PDF física existente.
    Garantía de salida: Conserva la geometría exacta de la página e incrusta
    el bitmap resultante de forma determinista y sin compresión con pérdidas.
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    if page_idx < 0 or page_idx >= len(doc):
        doc.close()
        raise IndexError(f"Índice de página {page_idx} fuera de rango (total {len(doc)})")

    page = doc[page_idx]
    page_w_pt = page.rect.width
    page_h_pt = page.rect.height

    # Renderizar página en espacio canónico
    pix = page.get_pixmap(dpi=int(dpi), colorspace=pymupdf.csGRAY)
    before_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()

    # Aplicar parche materialmente
    after_np, patch_evidence = apply_raster_patch(
        image=before_np,
        op=op,
        dpi=dpi,
        profile_path=profile_path,
    )

    # Reconstruir PDF preservando todas las demás páginas
    new_doc = pymupdf.open()
    for idx in range(len(doc)):
        if idx == page_idx:
            npage = new_doc.new_page(width=page_w_pt, height=page_h_pt)
            # Guardar after_np como PNG en memoria
            out_img = Image.fromarray(after_np, "L")
            buf = io.BytesIO()
            out_img.save(buf, format="PNG")
            npage.insert_image(npage.rect, stream=buf.getvalue())
        else:
            # Copiar página intacta
            new_doc.insert_pdf(doc, from_page=idx, to_page=idx)

    doc.close()
    out_bytes = new_doc.tobytes(garbage=3, deflate=True)
    new_doc.close()

    source_hash = hashlib.sha256(pdf_bytes).hexdigest()
    output_hash = hashlib.sha256(out_bytes).hexdigest()

    patch_evidence["source_sha256"] = source_hash
    patch_evidence["output_sha256"] = output_hash

    return out_bytes, before_np, after_np, patch_evidence


def apply_raster_transaction(
    pdf_bytes: bytes,
    ops: List[RasterReplaceText],
    dpi: float = DPI,
    profile_path: Optional[str] = None,
) -> Tuple[bytes, List[Dict[str, Any]]]:
    """
    ORDEN 137 §18 & §63: ATOMIC RASTER TRANSACTION
    Aplica una transacción atómica de múltiples parches raster.
    POLÍTICA: ATOMIC. Si cualquiera de las regiones es UNSAFE o falla preflight,
    ninguna mutación se materializa y se produce un rollback completo.
    """
    if not ops:
        return pdf_bytes, []

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages_imgs: Dict[int, np.ndarray] = {}

    # 1. Preflight Safety Check de TODAS las operaciones antes de cualquier mutación
    for op in ops:
        if op.page < 0 or op.page >= len(doc):
            doc.close()
            raise IndexError(f"Transacción abortada: índice de página {op.page} fuera de rango")

        if op.page not in pages_imgs:
            pix = doc[op.page].get_pixmap(dpi=int(dpi), colorspace=pymupdf.csGRAY)
            pages_imgs[op.page] = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()

        safety_info = classify_raster_target(
            image=pages_imgs[op.page],
            target_bbox_pt=op.target_bbox,
            ocr_confidence=op.provenance.get("confidence", 85.0) if op.provenance else 85.0,
            dpi=dpi,
            profile_path=profile_path,
        )
        if not safety_info["edit_eligible"]:
            doc.close()
            raise ValueError(
                f"Transacción ABORTADA (Atomic Rollback): la operación {op.observation_id} en página {op.page} "
                f"falló el preflight de seguridad ({safety_info['safety_classification']}, {safety_info['reasons']}). "
                f"Ningún cambio fue aplicado."
            )

    # 2. Todas las operaciones pasaron preflight: aplicar parches secuencialmente en las copias de imagen
    evidence_list: List[Dict[str, Any]] = []
    for op in ops:
        curr_img = pages_imgs[op.page]
        after_img, ev = apply_raster_patch(
            image=curr_img,
            op=op,
            dpi=dpi,
            profile_path=profile_path,
        )
        pages_imgs[op.page] = after_img
        evidence_list.append(ev)

    # 3. Reconstruir documento de salida
    new_doc = pymupdf.open()
    for idx in range(len(doc)):
        if idx in pages_imgs:
            page = doc[idx]
            npage = new_doc.new_page(width=page.rect.width, height=page.rect.height)
            out_img = Image.fromarray(pages_imgs[idx], "L")
            buf = io.BytesIO()
            out_img.save(buf, format="PNG")
            npage.insert_image(npage.rect, stream=buf.getvalue())
        else:
            new_doc.insert_pdf(doc, from_page=idx, to_page=idx)

    doc.close()
    out_bytes = new_doc.tobytes(garbage=3, deflate=True)
    new_doc.close()

    source_hash = hashlib.sha256(pdf_bytes).hexdigest()
    output_hash = hashlib.sha256(out_bytes).hexdigest()
    for ev in evidence_list:
        ev["source_sha256"] = source_hash
        ev["output_sha256"] = output_hash

    return out_bytes, evidence_list


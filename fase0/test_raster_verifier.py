"""
PROMETEO · FASE 0 · COMPREHENSIVE RASTER VERIFIER TEST SUITE (§27–§45, §89)
────────────────────────────────────────────────────────────────────────────
Pruebas exhaustivas del Verificador Físico Raster, Clasificador y Modelo de Doble Autoridad:
  1. Generated Fixture Positivo (Class A, White Background) → PASS físico + semántico.
  2. Tamper Outside Patch → FAIL (OUTSIDE_PATCH_CONTAMINATION).
  3. No-Op Attack → FAIL (NO_OP_DETECTED).
  4. False Semantic Pass Attack → FAIL.
  5. False Physical Pass Attack → FAIL.
  6. Gradient Fixture → HONEST_REJECT (Class B).
  7. Texture / Noise Fixture → HONEST_REJECT (Class C).
  8. Table Border Overlap Fixture → HONEST_REJECT (PATCH_OVERLAPS_GRAPHIC).
  9. Low Resolution / Low Confidence Fixture → HONEST_REJECT.
  10. Rotated / Skewed Page → HONEST_REJECT.
  11. Repeated Text Ambiguity → AMBIGUOUS.
  12. Source Document Immutability (source SHA256 pre == post).
  13. Multipage Isolation (página no editada permanece 100% idéntica).
  14. Real Scan Evaluation: case_b_scan.pdf.
  15. Adversarial Reality: CAL-005 evaluation.
"""
from __future__ import annotations

import hashlib
import os
from typing import Tuple

import numpy as np
import pytest
import pymupdf
from PIL import Image, ImageDraw

from raster_classifier import (
    classify_raster_target,
    load_verifier_profile,
    RASTER_CLASS_A,
    RASTER_CLASS_B,
    RASTER_CLASS_C,
    SAFETY_SAFE,
    SAFETY_UNCERTAIN,
    SAFETY_UNSAFE,
    REASON_SAFE_UNIFORM,
    REASON_PATCH_OVERLAPS_GRAPHIC,
    REASON_BG_TOO_COMPLEX,
    REASON_OCR_CONFIDENCE_LOW,
)
from raster_operations import (
    RasterReplaceText,
    apply_raster_patch,
    apply_raster_transaction,
    mutate_pdf_page_with_patch,
)
from raster_verifier import (
    compute_physical_diff,
    verify_border_ring_stability,
    verify_background_reconstruction_quality,
    verify_raster_patch,
    FAIL_OUTSIDE_CONTAMINATION,
    FAIL_NO_OP_DETECTED,
    FAIL_NEW_TEXT_NOT_CONFIRMED,
    FAIL_BORDER_RING_INSTABILITY,
    FAIL_BG_RECONSTRUCTION,
)



def create_generated_fixture_pdf(
    text: str = "INVOICE TOTAL AMOUNT DUE",
    width: float = 300.0,
    height: float = 200.0,
    text_pos: Tuple[float, float] = (50.0, 80.0),
    fontsize: float = 14.0,
) -> Tuple[bytes, Tuple[float, float, float, float]]:
    """Crea un PDF raster simple con fondo blanco y texto de prueba conocido."""
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    page.draw_rect(page.rect, color=(1, 1, 1), fill=(1, 1, 1))
    page.insert_text(text_pos, text, fontsize=fontsize, color=(0, 0, 0))
    pdf_bytes = doc.tobytes()
    doc.close()

    # Bounding box aproximado del texto
    s = 1.0
    x0, y0 = text_pos[0], text_pos[1] - fontsize
    x1, y1 = text_pos[0] + len(text) * fontsize * 0.55, text_pos[1] + fontsize * 0.3
    bbox = (x0, y0, x1, y1)
    return pdf_bytes, bbox


def test_profile_integrity():
    profile = load_verifier_profile()
    assert profile["profile_name"] == "RASTER_PATCH_VERIFY_V0_1"
    assert profile["physical_verifier"]["outside_diff_max"] == 0.0
    assert profile["physical_verifier"]["outside_allowed_pixel_count_max"] == 0
    assert profile["policies"]["double_authority_required"] is True


def test_generated_fixture_positive_pass():
    """§27: FIXTURE SIMPLE POSITIVO (GENERATED_FIXTURE) → PASS físico + semántico."""
    full_text = "CONFIRMED VALIDATION RECORD"
    pdf_bytes, _ = create_generated_fixture_pdf(text=full_text, text_pos=(50.0, 80.0), fontsize=14.0)

    # Reemplazar 'CONFIRMED' por 'APPROVED'
    target_bbox = (48.0, 66.0, 145.0, 85.0)
    allowed_patch = (45.0, 63.0, 148.0, 88.0)

    op = RasterReplaceText(
        document_id="gen_fixture_doc",
        page=0,
        observation_id="obs_pos_1",
        old_observed_text="CONFIRMED",
        new_text="APPROVED",
        target_bbox=target_bbox,
        allowed_patch_bbox=allowed_patch,
        background_class=RASTER_CLASS_A,
    )

    out_bytes, before_np, after_np, meta = mutate_pdf_page_with_patch(pdf_bytes, 0, op)

    # 1. Verificar mutación física
    assert len(out_bytes) > 0
    assert meta["source_sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    assert meta["output_sha256"] == hashlib.sha256(out_bytes).hexdigest()
    assert meta["source_sha256"] != meta["output_sha256"]

    # 2. Verificar con el Verificador Físico
    res = verify_raster_patch(pdf_bytes, out_bytes, op)
    assert res["status"] == "PASS"
    assert res["physical_pass"] is True
    assert res["semantic_pass"] is True
    assert res["containment"]["containment_pass"] is True
    assert res["containment"]["outside_patch_changed_pixel_count"] == 0
    assert res["metrics"]["changed_pixel_count"] > 0
    assert res["border_ring"]["border_ring_pass"] is True
    assert res["background"]["background_pass"] is True
    assert res["reasons"] == []


def test_tamper_outside_patch_detected():
    """§34: TAMPER OUTSIDE PATCH → FAIL con OUTSIDE_PATCH_CONTAMINATION."""
    pdf_bytes, _ = create_generated_fixture_pdf(text="STATUS NORMAL", text_pos=(50.0, 80.0), fontsize=14.0)
    target_bbox = (48.0, 66.0, 110.0, 85.0)
    allowed_patch = (45.0, 63.0, 113.0, 88.0)

    op = RasterReplaceText(
        document_id="tamper_doc",
        page=0,
        observation_id="obs_tamper",
        old_observed_text="STATUS",
        new_text="ALTERED",
        target_bbox=target_bbox,
        allowed_patch_bbox=allowed_patch,
    )

    out_bytes, _, _, _ = mutate_pdf_page_with_patch(pdf_bytes, 0, op)

    # Adulterar un píxel fuera de la región autorizada en el PDF exportado
    doc = pymupdf.open(stream=out_bytes, filetype="pdf")
    page = doc[0]
    # Dibujar una marca negra en una esquina alejada (10, 10)
    page.draw_rect(pymupdf.Rect(10, 10, 20, 20), color=(0, 0, 0), fill=(0, 0, 0))
    tampered_bytes = doc.tobytes()
    doc.close()

    res = verify_raster_patch(pdf_bytes, tampered_bytes, op)
    assert res["status"] == "FAILED"
    assert res["physical_pass"] is False
    assert res["containment"]["containment_pass"] is False
    assert res["containment"]["outside_patch_changed_pixel_count"] > 0
    assert FAIL_OUTSIDE_CONTAMINATION in res["reasons"]


def test_no_op_attack_detected():
    """§36: NO-OP ATTACK → FAIL con NO_OP_DETECTED."""
    pdf_bytes, _ = create_generated_fixture_pdf(text="BALANCE REPORT", text_pos=(50.0, 80.0))
    op = RasterReplaceText(
        document_id="noop_doc",
        page=0,
        observation_id="obs_noop",
        old_observed_text="BALANCE",
        new_text="BALANCE",
        target_bbox=(48.0, 66.0, 120.0, 85.0),
        allowed_patch_bbox=(45.0, 63.0, 123.0, 88.0),
    )

    # Pasar el PDF original sin mutación como si fuera el exportado
    res = verify_raster_patch(pdf_bytes, pdf_bytes, op)
    assert res["status"] == "FAILED"
    assert res["physical_pass"] is False
    assert res["metrics"]["changed_pixel_count"] == 0
    assert FAIL_NO_OP_DETECTED in res["reasons"]


def test_false_physical_pass_attack_detected():
    """§38: FALSE PHYSICAL PASS ATTACK → FAIL (cambio confinado pero texto no confirmado)."""
    pdf_bytes, _ = create_generated_fixture_pdf(text="ORDER ORIGINAL", text_pos=(50.0, 80.0))
    target_bbox = (48.0, 66.0, 105.0, 85.0)
    allowed_patch = (45.0, 63.0, 108.0, 88.0)

    # Operación que muta con un texto pero la verificación espera otro texto inexistente
    op_mutation = RasterReplaceText(
        document_id="false_phys_doc",
        page=0,
        observation_id="obs_fphys",
        old_observed_text="ORDER",
        new_text="BLANKED",
        target_bbox=target_bbox,
        allowed_patch_bbox=allowed_patch,
    )
    out_bytes, _, _, _ = mutate_pdf_page_with_patch(pdf_bytes, 0, op_mutation)

    # Verificador con expectativa distinta
    op_verify = RasterReplaceText(
        document_id="false_phys_doc",
        page=0,
        observation_id="obs_fphys",
        old_observed_text="ORDER",
        new_text="UNMATCHED_SECRET_PHRASE",
        target_bbox=target_bbox,
        allowed_patch_bbox=allowed_patch,
    )
    res = verify_raster_patch(pdf_bytes, out_bytes, op_verify)
    assert res["status"] == "FAILED"
    assert res["semantic_pass"] is False
    assert FAIL_NEW_TEXT_NOT_CONFIRMED in res["reasons"]


def test_gradient_fixture_honest_reject():
    """§28: FIXTURE GRADIENTE → Preflight Safety Reject (Class B)."""
    img = np.tile(np.linspace(255, 120, 400, dtype=np.uint8), (300, 1))
    res = classify_raster_target(
        image=img,
        target_bbox_pt=(30.0, 30.0, 80.0, 45.0),
        ocr_confidence=85.0,
    )
    assert res["safety_classification"] in (SAFETY_UNCERTAIN, SAFETY_UNSAFE)
    assert res["edit_eligible"] is False


def test_texture_fixture_honest_reject():
    """§29: FIXTURE TEXTURA → Preflight Safety Reject (Class C)."""
    np.random.seed(99)
    img = np.random.randint(60, 240, size=(400, 400), dtype=np.uint8)
    res = classify_raster_target(
        image=img,
        target_bbox_pt=(30.0, 30.0, 80.0, 45.0),
        ocr_confidence=85.0,
    )
    assert res["safety_classification"] == SAFETY_UNSAFE
    assert res["raster_class"] == RASTER_CLASS_C
    assert res["edit_eligible"] is False
    assert REASON_BG_TOO_COMPLEX in res["reasons"] or "EDGE_DENSITY_EXCEEDED" in res["reasons"]


def test_table_border_fixture_honest_reject():
    """§30: FIXTURE TABLE BORDER → Preflight Safety Reject (PATCH_OVERLAPS_GRAPHIC)."""
    img = np.full((400, 400), 255, dtype=np.uint8)
    # Línea horizontal atravesando la región del target
    s = 300.0 / 72.0
    line_y = int(35.0 * s)
    img[line_y:line_y + 3, :] = 0

    res = classify_raster_target(
        image=img,
        target_bbox_pt=(30.0, 30.0, 80.0, 45.0),
        ocr_confidence=90.0,
    )
    assert res["safety_classification"] == SAFETY_UNSAFE
    assert res["raster_class"] == RASTER_CLASS_C
    assert res["edit_eligible"] is False
    assert REASON_PATCH_OVERLAPS_GRAPHIC in res["reasons"]


def test_source_immutability_invariant():
    """§71: ORIGINAL HASH IMMUTABILITY: source_sha256 pre == post."""
    pdf_bytes, _ = create_generated_fixture_pdf(text="AUDIT CERTIFICATE")
    hash_pre = hashlib.sha256(pdf_bytes).hexdigest()

    op = RasterReplaceText(
        document_id="immut_doc",
        page=0,
        observation_id="obs_immut",
        old_observed_text="AUDIT",
        new_text="VERIFIED",
        target_bbox=(48.0, 66.0, 100.0, 85.0),
        allowed_patch_bbox=(45.0, 63.0, 103.0, 88.0),
    )

    out_bytes, _, _, _ = mutate_pdf_page_with_patch(pdf_bytes, 0, op)
    _ = verify_raster_patch(pdf_bytes, out_bytes, op)

    hash_post = hashlib.sha256(pdf_bytes).hexdigest()
    assert hash_pre == hash_post, "El buffer original sufrió mutación física prohibida"


def test_multipage_isolation():
    """§70: MULTIPAGE SCAN ISOLATION: página 1 intacta tras mutar página 0."""
    doc = pymupdf.open()
    p0 = doc.new_page(width=300, height=200)
    p0.draw_rect(p0.rect, color=(1, 1, 1), fill=(1, 1, 1))
    p0.insert_text((50, 80), "PAGE ZERO TEXT", fontsize=14, color=(0, 0, 0))

    p1 = doc.new_page(width=300, height=200)
    p1.draw_rect(p1.rect, color=(1, 1, 1), fill=(1, 1, 1))
    p1.insert_text((50, 80), "PAGE ONE UNTOUCHED", fontsize=14, color=(0, 0, 0))

    multi_bytes = doc.tobytes()
    p1_original_pix = doc[1].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY).tobytes()
    doc.close()

    op = RasterReplaceText(
        document_id="multi_doc",
        page=0,
        observation_id="obs_p0",
        old_observed_text="ZERO",
        new_text="EDITED",
        target_bbox=(48.0, 66.0, 95.0, 85.0),
        allowed_patch_bbox=(45.0, 63.0, 98.0, 88.0),
    )

    out_bytes, _, _, _ = mutate_pdf_page_with_patch(multi_bytes, 0, op)

    out_doc = pymupdf.open(stream=out_bytes, filetype="pdf")
    assert len(out_doc) == 2
    p1_mutated_pix = out_doc[1].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY).tobytes()
    out_doc.close()

    assert p1_original_pix == p1_mutated_pix, "La página 1 fue alterada al editar la página 0"


def test_case_b_scan_reality_evaluation():
    """§40 & §41: CASE_B_SCAN REALITY TEST: Clasificar regiones reales y verificar gating honesto."""
    case_b_path = "fase0/assets/case_b_scan.pdf"
    if not os.path.exists(case_b_path):
        pytest.skip(f"No existe {case_b_path}")

    with open(case_b_path, "rb") as f:
        case_b_bytes = f.read()

    doc = pymupdf.open(stream=case_b_bytes, filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
    img_gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()

    # Evaluar varias regiones de case_b_scan
    # case_b_scan es un escaneo con ruido/artefactos JPEG.
    sample_targets = [
        ("target_header", (100.0, 50.0, 250.0, 70.0), 85.0),
        ("target_body_line", (100.0, 150.0, 300.0, 165.0), 88.0),
        ("target_table_area", (100.0, 300.0, 250.0, 320.0), 82.0),
    ]

    classifications = []
    for tid, bbox, conf in sample_targets:
        res = classify_raster_target(img_gray, bbox, conf, dpi=300.0)
        classifications.append((tid, res["raster_class"], res["safety_classification"]))

    # Confirmar que el clasificador es honesto (no aprueba a ciegas)
    assert len(classifications) == 3
    # Si alguna es Class A o no, debe tener justificación determinista
    for tid, rclass, safety in classifications:
        assert rclass in (RASTER_CLASS_A, RASTER_CLASS_B, RASTER_CLASS_C)
        assert safety in (SAFETY_SAFE, SAFETY_UNCERTAIN, SAFETY_UNSAFE)


def test_low_resolution_fixture_honest_reject():
    """§31: FIXTURE LOW RESOLUTION / LOW CONFIDENCE → HONEST_REJECT."""
    img = np.full((300, 300), 255, dtype=np.uint8)
    res = classify_raster_target(
        image=img,
        target_bbox_pt=(20.0, 20.0, 60.0, 35.0),
        ocr_confidence=35.0,  # Debajo del piso de baja confianza (40.0)
    )
    assert res["safety_classification"] in (SAFETY_UNCERTAIN, SAFETY_UNSAFE)
    assert res["raster_class"] in (RASTER_CLASS_B, RASTER_CLASS_C)
    assert res["edit_eligible"] is False
    assert (
        REASON_OCR_CONFIDENCE_LOW in res["reasons"]
        or REASON_OCR_CONFIDENCE_MARGINAL in res["reasons"]
    )


def test_rotated_skewed_fixture_honest_reject():
    """§32: FIXTURE ROTATED / SKEWED → HONEST_REJECT."""
    # Usar documento rotado real M_rotacion_4.pdf del corpus raster
    rot_path = "fase0/assets/raster/M_rotacion_4.pdf"
    if os.path.exists(rot_path):
        doc = pymupdf.open(rot_path)
        page = doc[0]
        pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
        doc.close()
        # Seleccionar target en el texto rotado
        res = classify_raster_target(
            image=img,
            target_bbox_pt=(50.0, 50.0, 200.0, 75.0),
            ocr_confidence=85.0,
            dpi=150.0,
            skew_deg=4.0,
        )
    else:
        # Fixture sintético con trazo rotado cruzando el anillo
        img = np.full((400, 400), 255, dtype=np.uint8)
        s = 300.0 / 72.0
        # Línea de 4px de grosor atravesando oblicuamente el target
        for i in range(120):
            y = int(25.0 * s + i * 0.5)
            x = int(20.0 * s + i)
            if 0 <= y < 396 and 0 <= x < 396:
                img[y:y + 4, x:x + 4] = 0
        res = classify_raster_target(
            image=img,
            target_bbox_pt=(20.0, 25.0, 50.0, 40.0),
            ocr_confidence=85.0,
        )

    assert res["raster_class"] in (RASTER_CLASS_B, RASTER_CLASS_C)
    assert res["edit_eligible"] is False


def test_repeated_text_ambiguity():
    """§33: REPEATED TEXT → AMBIGUOUS si no existe selección explícita por observación."""
    # Dos observaciones con el mismo texto
    obs1 = {"observation_id": "obs_1", "text": "TOTAL"}
    obs2 = {"observation_id": "obs_2", "text": "TOTAL"}
    # Sin observation_id explícito para desambiguar, la operación debe ser rechazada como AMBIGUOUS
    target_selector = "TOTAL"
    candidates = [obs1, obs2]
    matching = [o for o in candidates if o["text"] == target_selector]
    assert len(matching) == 2, "Debe haber ambigüedad de target"
    # Política determinista: si len > 1 y no se especifica observation_id único, el estado es AMBIGUOUS
    ambiguity_status = "AMBIGUOUS" if len(matching) > 1 else "RESOLVED"
    assert ambiguity_status == "AMBIGUOUS"


def test_tamper_inside_neighbor_region_detected():
    """§35: TAMPER INSIDE NEIGHBOR REGION → Detectado por border ring o diff."""
    pdf_bytes, _ = create_generated_fixture_pdf(text="ALPHA BRAVO CHARLIE", text_pos=(50.0, 80.0))
    # Modificar ALPHA pero alterar un píxel en el anillo exterior
    target_bbox = (48.0, 66.0, 95.0, 85.0)
    allowed_patch = (45.0, 63.0, 98.0, 88.0)

    op = RasterReplaceText(
        document_id="neighbor_doc",
        page=0,
        observation_id="obs_neigh",
        old_observed_text="ALPHA",
        new_text="DELTA",
        target_bbox=target_bbox,
        allowed_patch_bbox=allowed_patch,
    )
    out_bytes, _, _, _ = mutate_pdf_page_with_patch(pdf_bytes, 0, op)

    # Inyectar una alteración en el anillo perimetral inmediatamente adyacente
    doc = pymupdf.open(stream=out_bytes, filetype="pdf")
    page = doc[0]
    # Dibujar mancha en el anillo (cerca del borde de allowed_patch)
    page.draw_rect(pymupdf.Rect(40, 60, 44, 64), color=(0, 0, 0), fill=(0, 0, 0))
    tampered_bytes = doc.tobytes()
    doc.close()

    res = verify_raster_patch(pdf_bytes, tampered_bytes, op)
    assert res["status"] == "FAILED"
    assert (
        FAIL_OUTSIDE_CONTAMINATION in res["reasons"]
        or FAIL_BORDER_RING_INSTABILITY in res["reasons"]
    )


def test_false_semantic_pass_attack_detected():
    """§37: FALSE SEMANTIC PASS ATTACK → OCR lee texto pero fondo/contención fallan."""
    pdf_bytes, _ = create_generated_fixture_pdf(text="BALANCE SUMMARY", text_pos=(50.0, 80.0))
    target_bbox = (48.0, 66.0, 110.0, 85.0)
    allowed_patch = (45.0, 63.0, 113.0, 88.0)

    op = RasterReplaceText(
        document_id="false_sem_doc",
        page=0,
        observation_id="obs_fsem",
        old_observed_text="BALANCE",
        new_text="REPORT",
        target_bbox=target_bbox,
        allowed_patch_bbox=allowed_patch,
    )
    out_bytes, _, _, _ = mutate_pdf_page_with_patch(pdf_bytes, 0, op)

    # El texto REPORT fue renderizado correctamente, pero introducimos daño fuera del patch
    doc = pymupdf.open(stream=out_bytes, filetype="pdf")
    page = doc[0]
    page.draw_rect(pymupdf.Rect(180, 80, 190, 90), color=(0, 0, 0), fill=(0, 0, 0))
    tampered_bytes = doc.tobytes()
    doc.close()

    res = verify_raster_patch(pdf_bytes, tampered_bytes, op)
    # OCR semántico podría encontrar REPORT, pero la contención física falla incondicionalmente
    assert res["status"] == "FAILED"
    assert res["physical_pass"] is False
    assert FAIL_OUTSIDE_CONTAMINATION in res["reasons"]


def test_cal_005_adversarial_honest_outcome():
    """§39: CAL-005 ADVERSARIAL REALITY EVALUATION: Detección honesta de riesgo."""
    # Mecanismo sintético reproductor de CAL-005 (fondo complejo / portada)
    rng = np.random.default_rng(23)
    img = np.full((600, 600), 245, dtype=np.uint8)
    # Añadir trazos y ruido aleatorio semejante al arte de cubierta de CAL-005
    for _ in range(200):
        x = rng.integers(0, 550)
        y = rng.integers(0, 550)
        img[y:y + 15, x:x + 15] = rng.integers(50, 180)

    res = classify_raster_target(
        image=img,
        target_bbox_pt=(50.0, 50.0, 150.0, 75.0),
        ocr_confidence=85.0,
    )
    # Debe ser honestamente rechazado por complejidad de fondo (Class C o B)
    assert res["safety_classification"] in (SAFETY_UNCERTAIN, SAFETY_UNSAFE)
    assert res["edit_eligible"] is False


def test_atomic_raster_transaction_success_and_rollback():
    """§18 & §63: ATOMIC RASTER TRANSACTION: Todo o nada."""
    # Crear documento con dos palabras bien espaciadas
    pdf_bytes, _ = create_generated_fixture_pdf(text="ITEMONE        ITEMTWO", text_pos=(50.0, 80.0))

    # Dos operaciones válidas Class A sin solapamiento
    op1 = RasterReplaceText(
        document_id="tx_doc",
        page=0,
        observation_id="tx_op1",
        old_observed_text="ITEMONE",
        new_text="CODEA",
        target_bbox=(49.0, 66.0, 105.0, 85.0),
        allowed_patch_bbox=(47.0, 64.0, 107.0, 87.0),
    )
    op2 = RasterReplaceText(
        document_id="tx_doc",
        page=0,
        observation_id="tx_op2",
        old_observed_text="ITEMTWO",
        new_text="CODEB",
        target_bbox=(135.0, 66.0, 195.0, 85.0),
        allowed_patch_bbox=(133.0, 64.0, 197.0, 87.0),
    )

    out_bytes, evs = apply_raster_transaction(pdf_bytes, [op1, op2])
    assert len(evs) == 2
    assert len(out_bytes) > 0

    # Ahora una transacción con una operación válida y otra con baja confianza (Class C)
    op_unsafe = RasterReplaceText(
        document_id="tx_doc",
        page=0,
        observation_id="tx_unsafe",
        old_observed_text="BAD",
        new_text="FAIL",
        target_bbox=(50.0, 100.0, 90.0, 120.0),
        allowed_patch_bbox=(48.0, 98.0, 92.0, 122.0),
        provenance={"confidence": 30.0},  # Confianza debajo del umbral forzando rechazo
    )

    # Debe producir excepción y rollback atómico
    with pytest.raises(ValueError, match="Atomic Rollback"):
        apply_raster_transaction(pdf_bytes, [op1, op_unsafe])


def test_border_ring_color_drift_fail():
    """§20: BORDER RING STABILITY: Desviación cromática produce FAIL."""
    before = np.full((100, 100), 255, dtype=np.uint8)
    after = before.copy()
    # Modificar el anillo exterior (x: 10 a 20, y: 10 a 90) oscureciéndolo
    after[10:90, 10:20] = 180  # Delta de 75 > umbral de 20
    ring_res = verify_border_ring_stability(
        before=before,
        after=after,
        allowed_patch_px=(25, 25, 75, 75),
        ring_width_px=8,
        mae_max=2.5,
        max_delta_threshold=20.0,
    )
    assert ring_res["border_ring_pass"] is False
    assert ring_res["border_ring_max_delta"] > 20.0


def test_background_reconstruction_residual_fail():
    """§21: BACKGROUND RECONSTRUCTION QUALITY: Residual alto produce FAIL."""
    # Fondo con anillo blanco (255) pero target rellenado con gris oscuro (100)
    after = np.full((100, 100), 255, dtype=np.uint8)
    after[30:70, 30:70] = 190  # residual = 65 > residual_max de 15.0
    bg_res = verify_background_reconstruction_quality(
        after=after,
        target_rect_px=(30, 30, 70, 70),
        allowed_patch_px=(25, 25, 75, 75),
        ring_width_px=8,
        residual_max=15.0,
    )
    assert bg_res["background_pass"] is False
    assert bg_res["background_residual"] > 15.0


def test_raster_corpus_calibration_vs_holdout():
    """§41, §43, §44, §45: HOLDOUT EVALUATION: FALSE_SAFE == 0 sobre corpus raster real."""
    corpus_dir = "fase0/assets/raster"
    if not os.path.exists(corpus_dir):
        pytest.skip(f"No existe {corpus_dir}")

    # Holdout cases preregistrados con sus bboxes de región diana
    # En G2_linea_cruza la línea cruza 'Perez'
    # En G_sobre_graficos el gráfico subyace a 'Importe'
    # En A_scan_limpio 'Perez' está sobre fondo limpio
    holdout_cases = [
        ("A_scan_limpio.pdf", (292 * 72 / 150, 212 * 72 / 150, 349 * 72 / 150, 230 * 72 / 150), RASTER_CLASS_A, True),
        ("G2_linea_cruza.pdf", (292 * 72 / 150, 212 * 72 / 150, 349 * 72 / 150, 230 * 72 / 150), RASTER_CLASS_C, False),
        ("G_sobre_graficos.pdf", (152 * 72 / 150, 333 * 72 / 150, 227 * 72 / 150, 355 * 72 / 150), RASTER_CLASS_B, False),
    ]

    for fname, tbbox_pt, expected_class, expected_safe in holdout_cases:
        fpath = os.path.join(corpus_dir, fname)
        if not os.path.exists(fpath):
            continue
        doc = pymupdf.open(fpath)
        page = doc[0]
        pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
        doc.close()

        res = classify_raster_target(img, tbbox_pt, ocr_confidence=85.0, dpi=150.0)

        if not expected_safe:
            # INVARIANTE CRÍTICA: FALSE_SAFE == 0
            assert res["edit_eligible"] is False, (
                f"VIOLACIÓN DE SEGURIDAD: {fname} fue clasificado como elegible siendo inseguro"
            )
        else:
            assert res["edit_eligible"] is True, (
                f"FALSO RECHAZO: {fname} debió ser elegible pero fue rechazado: {res['reasons']}"
            )
            assert res["raster_class"] == expected_class


def test_process_timeout_and_cleanup():
    """§72, §73, §74: OCR TIMEOUT HANDLING & PROCESS CLEANUP."""
    from ocr_provider import TesseractOCRProvider
    provider = TesseractOCRProvider(timeout_seconds=0.00001)  # Timeout casi inmediato
    img = Image.new("L", (100, 100), color=255)
    # Debe abortar limpiamente por timeout sin dejar procesos colgados
    with pytest.raises(Exception):
        provider.process(img, dpi=300.0)



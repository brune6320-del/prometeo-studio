"""
Unit tests for Deterministic Background Safety Classifier (fase0/raster_classifier.py).
"""
import numpy as np
import pytest

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
    REASON_RING_VARIANCE_EXCEEDED,
    REASON_OCR_CONFIDENCE_LOW,
    REASON_TARGET_SIZE_IMPLAUSIBLE,
)


def test_profile_loading():
    profile = load_verifier_profile()
    assert profile["profile_name"] == "RASTER_PATCH_VERIFY_V0_1"
    assert profile["version"] == "0.1.0"
    assert "background_classifier" in profile
    assert profile["geometry"]["margin_pt"] == 3.0


def test_classify_uniform_white_background():
    from PIL import Image, ImageDraw
    img_pil = Image.new("L", (600, 600), 255)
    draw = ImageDraw.Draw(img_pil)
    draw.text((220, 220), "Sample Text", fill=0)
    img = np.array(img_pil)

    result = classify_raster_target(
        image=img,
        target_bbox_pt=(50.0, 50.0, 100.0, 60.0),
        ocr_confidence=92.0,
    )

    assert result["safety_classification"] == SAFETY_SAFE
    assert result["raster_class"] == RASTER_CLASS_A
    assert result["edit_eligible"] is True
    assert REASON_SAFE_UNIFORM in result["reasons"]
    assert result["metrics"]["ring_variance"] < 1.0


def test_classify_gradient_background():
    # Gradient from 255 to 100 across width
    gradient = np.linspace(255, 100, 600, dtype=np.float32)
    img = np.tile(gradient, (600, 1)).astype(np.uint8)

    result = classify_raster_target(
        image=img,
        target_bbox_pt=(50.0, 50.0, 100.0, 60.0),
        ocr_confidence=85.0,
        dpi=300.0,
    )

    # Gradient should trigger Class B (Uncertain) or Class C depending on variance
    assert result["safety_classification"] in (SAFETY_UNCERTAIN, SAFETY_UNSAFE)
    assert result["raster_class"] in (RASTER_CLASS_B, RASTER_CLASS_C)
    assert result["edit_eligible"] is False
    assert (
        REASON_RING_VARIANCE_EXCEEDED in result["reasons"]
        or REASON_BG_TOO_COMPLEX in result["reasons"]
        or "EDGE_DENSITY_EXCEEDED" in result["reasons"]
    )


def test_classify_high_texture_noise():
    # Random noise texture
    np.random.seed(42)
    img = np.random.randint(50, 250, size=(600, 600), dtype=np.uint8)

    result = classify_raster_target(
        image=img,
        target_bbox_pt=(50.0, 50.0, 100.0, 60.0),
        ocr_confidence=80.0,
        dpi=300.0,
    )

    assert result["safety_classification"] == SAFETY_UNSAFE
    assert result["raster_class"] == RASTER_CLASS_C
    assert result["edit_eligible"] is False
    assert (
        REASON_BG_TOO_COMPLEX in result["reasons"]
        or "EDGE_DENSITY_EXCEEDED" in result["reasons"]
    )


def test_classify_table_line_overlap():
    img = np.full((600, 600), 255, dtype=np.uint8)
    s = 300.0 / 72.0
    # Draw horizontal table line crossing through the target region
    y_line = int(55 * s)
    img[y_line:y_line + 3, :] = 0  # black line across the whole page

    result = classify_raster_target(
        image=img,
        target_bbox_pt=(50.0, 50.0, 100.0, 60.0),
        ocr_confidence=90.0,
        dpi=300.0,
    )

    assert result["safety_classification"] == SAFETY_UNSAFE
    assert result["raster_class"] == RASTER_CLASS_C
    assert result["edit_eligible"] is False
    assert REASON_PATCH_OVERLAPS_GRAPHIC in result["reasons"]


def test_classify_low_confidence_ocr():
    img = np.full((600, 600), 255, dtype=np.uint8)
    result = classify_raster_target(
        image=img,
        target_bbox_pt=(50.0, 50.0, 100.0, 60.0),
        ocr_confidence=30.0,  # Below 40.0
        dpi=300.0,
    )

    assert result["safety_classification"] == SAFETY_UNSAFE
    assert result["raster_class"] == RASTER_CLASS_C
    assert result["edit_eligible"] is False
    assert REASON_OCR_CONFIDENCE_LOW in result["reasons"]


def test_classify_invalid_geometry():
    img = np.full((600, 600), 255, dtype=np.uint8)
    # Inverted bbox: x1 < x0
    result = classify_raster_target(
        image=img,
        target_bbox_pt=(100.0, 50.0, 50.0, 60.0),
        ocr_confidence=90.0,
    )
    assert result["safety_classification"] == SAFETY_UNSAFE
    assert result["edit_eligible"] is False
    assert REASON_TARGET_SIZE_IMPLAUSIBLE in result["reasons"]

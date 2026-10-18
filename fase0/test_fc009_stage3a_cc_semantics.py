"""
FC-009 Stage 3A-3: Connected Component Runtime Semantics RED Contract.

Verifies the semantic contract of connected components features in Stage 3A:
- connected_components_count
- mean_cc_aspect_ratio
- max_cc_aspect_ratio

Ground truth is computed independently (via self-contained reference and explicit
fixture geometry) without any runtime dependency on scipy.
"""
import math
import numpy as np
import pytest

from verifier2 import extract_positive_text_features


def _ground_truth_connected_components(binary_dark: np.ndarray):
    """Self-contained 4-connectivity connected components reference in pure numpy/Python.

    Used to establish exact ground-truth independently of scipy or cv2 availability.
    Preserves historical scipy.ndimage.label(..., structure=None) 4-connectivity semantics.
    """
    h, w = binary_dark.shape
    visited = np.zeros((h, w), dtype=bool)
    components = []

    for r in range(h):
        for c in range(w):
            if binary_dark[r, c] and not visited[r, c]:
                q = [(r, c)]
                visited[r, c] = True
                min_r, max_r = r, r
                min_c, max_c = c, c

                head = 0
                while head < len(q):
                    cr, cc = q[head]
                    head += 1
                    min_r = min(min_r, cr)
                    max_r = max(max_r, cr)
                    min_c = min(min_c, cc)
                    max_c = max(max_c, cc)

                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < h and 0 <= nc < w:
                            if binary_dark[nr, nc] and not visited[nr, nc]:
                                visited[nr, nc] = True
                                q.append((nr, nc))

                comp_h = max_r - min_r + 1
                comp_w = max_c - min_c + 1
                aspect = float(comp_h) / max(float(comp_w), 1.0)
                components.append({"h": comp_h, "w": comp_w, "aspect": aspect})

    count = len(components)
    mean_aspect = float(np.mean([c["aspect"] for c in components])) if count > 0 else 0.0
    max_aspect = float(np.max([c["aspect"] for c in components])) if count > 0 else 0.0
    return count, mean_aspect, max_aspect, components


@pytest.fixture
def standard_three_component_fixture():
    """Standard synthetic fixture with 3 known, physically separated components:
    - Component A: width = 2, height = 10, aspect = 5.0
    - Component B: width = 4, height = 8,  aspect = 2.0
    - Component C: width = 3, height = 3,  aspect = 1.0
    Canvas: 30x30, white background (255), black foreground (0).
    """
    canvas = np.full((30, 30), 255, dtype=np.uint8)
    # Component A: r=2..12 (h=10), c=2..4 (w=2) -> aspect = 10.0 / 2.0 = 5.0
    canvas[2:12, 2:4] = 0
    # Component B: r=2..10 (h=8), c=8..12 (w=4) -> aspect = 8.0 / 4.0 = 2.0
    canvas[2:10, 8:12] = 0
    # Component C: r=2..5 (h=3), c=16..19 (w=3) -> aspect = 3.0 / 3.0 = 1.0
    canvas[2:5, 16:19] = 0

    return canvas, (0, 0, 30, 30)


# ---------------------------------------------------------------------------
# Mandatory Assertions: CC-01, CC-02, CC-03
# ---------------------------------------------------------------------------

def test_cc01_count_semantics(standard_three_component_fixture):
    """CC-01: Verifies that connected_components_count reflects actual 2D components (count == 3)."""
    canvas, rect_px = standard_three_component_fixture
    dark = (canvas <= 128)
    gt_count, _, _, _ = _ground_truth_connected_components(dark)
    assert gt_count == 3, "Test harness ground truth failure"

    res = extract_positive_text_features(canvas, rect_px=rect_px)
    feats = res["features"]

    # Semantic Contract: must equal 3
    assert feats["connected_components_count"] == 3, (
        f"Expected connected_components_count == 3, got {feats['connected_components_count']}"
    )


def test_cc02_mean_aspect_semantics(standard_three_component_fixture):
    """CC-02: Verifies mean_cc_aspect_ratio == mean([5.0, 2.0, 1.0]) = 2.6667 within tolerance."""
    canvas, rect_px = standard_three_component_fixture
    expected_mean = (5.0 + 2.0 + 1.0) / 3.0  # 2.666667

    res = extract_positive_text_features(canvas, rect_px=rect_px)
    feats = res["features"]

    assert feats["mean_cc_aspect_ratio"] == pytest.approx(expected_mean, rel=1e-2), (
        f"Expected mean_cc_aspect_ratio ≈ {expected_mean:.4f}, got {feats['mean_cc_aspect_ratio']}"
    )


def test_cc03_max_aspect_semantics(standard_three_component_fixture):
    """CC-03: Verifies max_cc_aspect_ratio == 5.0 within tolerance."""
    canvas, rect_px = standard_three_component_fixture
    expected_max = 5.0

    res = extract_positive_text_features(canvas, rect_px=rect_px)
    feats = res["features"]

    assert feats["max_cc_aspect_ratio"] == pytest.approx(expected_max, rel=1e-2), (
        f"Expected max_cc_aspect_ratio ≈ {expected_max:.4f}, got {feats['max_cc_aspect_ratio']}"
    )


# ---------------------------------------------------------------------------
# Additional Semantics: CC-04 to CC-08
# ---------------------------------------------------------------------------

def test_cc04_disconnected_components_remain_distinct():
    """CC-04: Verifies vertically separated components sharing horizontal columns remain distinct.

    A 1D vertical column projection merges them into 1 cluster, but 2D CC must recognize 2 components.
    """
    canvas = np.full((30, 30), 255, dtype=np.uint8)
    # Component 1: top, r=2..8 (h=6), c=5..10 (w=5)
    canvas[2:8, 5:10] = 0
    # Component 2: bottom, r=16..22 (h=6), c=5..10 (w=5)
    canvas[16:22, 5:10] = 0

    dark = (canvas <= 128)
    gt_count, _, _, _ = _ground_truth_connected_components(dark)
    assert gt_count == 2, "Ground truth must find 2 distinct components"

    res = extract_positive_text_features(canvas, rect_px=(0, 0, 30, 30))
    feats = res["features"]

    assert feats["connected_components_count"] == 2, (
        f"Expected connected_components_count == 2 for vertically stacked blocks, got {feats['connected_components_count']}"
    )


def test_cc05_touching_pixels_merge_components():
    """CC-05: Verifies that touching pixels merge into a single connected component."""
    canvas = np.full((30, 30), 255, dtype=np.uint8)
    # Block 1: r=5..15 (h=10), c=5..10 (w=5)
    canvas[5:15, 5:10] = 0
    # Block 2: r=5..15 (h=10), c=10..15 (w=5), touching directly along column 9/10 border
    canvas[5:15, 10:15] = 0

    # Merged block: h=10, w=10 -> aspect = 1.0
    dark = (canvas <= 128)
    gt_count, gt_mean, gt_max, _ = _ground_truth_connected_components(dark)
    assert gt_count == 1, "Touching blocks must merge into 1 component"
    assert gt_max == pytest.approx(1.0, rel=1e-2)

    res = extract_positive_text_features(canvas, rect_px=(0, 0, 30, 30))
    feats = res["features"]

    assert feats["connected_components_count"] == 1, (
        f"Expected 1 merged component, got {feats['connected_components_count']}"
    )
    assert feats["max_cc_aspect_ratio"] == pytest.approx(1.0, rel=1e-2), (
        f"Expected aspect ratio ≈ 1.0, got {feats['max_cc_aspect_ratio']}"
    )


def test_cc06_deterministic_repeated_execution(standard_three_component_fixture):
    """CC-06: Verifies deterministic repeated execution produces identical CC metrics."""
    canvas, rect_px = standard_three_component_fixture

    res1 = extract_positive_text_features(canvas, rect_px=rect_px)
    res2 = extract_positive_text_features(canvas, rect_px=rect_px)

    f1 = res1["features"]
    f2 = res2["features"]

    assert f1["connected_components_count"] == f2["connected_components_count"]
    assert f1["mean_cc_aspect_ratio"] == f2["mean_cc_aspect_ratio"]
    assert f1["max_cc_aspect_ratio"] == f2["max_cc_aspect_ratio"]


def test_cc07_no_nan_or_inf():
    """CC-07: Verifies no NaN or Inf is returned for edge cases (all white, all black, single pixel)."""
    # Case 1: All white (no dark pixels)
    white_canvas = np.full((20, 20), 255, dtype=np.uint8)
    res_w = extract_positive_text_features(white_canvas, rect_px=(0, 0, 20, 20))
    fw = res_w["features"]
    assert fw["connected_components_count"] == 0
    assert not math.isnan(fw["mean_cc_aspect_ratio"])
    assert not math.isinf(fw["mean_cc_aspect_ratio"])
    assert not math.isnan(fw["max_cc_aspect_ratio"])
    assert not math.isinf(fw["max_cc_aspect_ratio"])

    # Case 2: All black
    black_canvas = np.full((20, 20), 0, dtype=np.uint8)
    res_b = extract_positive_text_features(black_canvas, rect_px=(0, 0, 20, 20))
    fb = res_b["features"]
    assert not math.isnan(fb["mean_cc_aspect_ratio"])
    assert not math.isinf(fb["mean_cc_aspect_ratio"])

    # Case 3: Single isolated pixel
    dot_canvas = np.full((20, 20), 255, dtype=np.uint8)
    dot_canvas[10, 10] = 0
    res_d = extract_positive_text_features(dot_canvas, rect_px=(0, 0, 20, 20))
    fd = res_d["features"]
    assert not math.isnan(fd["mean_cc_aspect_ratio"])
    assert not math.isnan(fd["max_cc_aspect_ratio"])


def test_cc08_semantics_independent_of_scipy_availability():
    """CC-08: Verifies semantic contract is preserved regardless of whether scipy is installed.

    The contract states that for a known vertical stroke (h=20, w=2), aspect ratio is 10.0.
    In the current runtime without scipy, the fallback returns normalized width (2/30 ≈ 0.0667)
    rather than height/width aspect ratio (10.0), demonstrating the active runtime semantics debt.
    """
    canvas = np.full((30, 30), 255, dtype=np.uint8)
    # Vertical stroke: r=5..25 (h=20), c=5..7 (w=2) -> aspect = 20.0 / 2.0 = 10.0
    canvas[5:25, 5:7] = 0

    dark = (canvas <= 128)
    gt_count, _, gt_max, _ = _ground_truth_connected_components(dark)
    assert gt_count == 1, "Single stroke ground truth count must be 1"
    assert gt_max == pytest.approx(10.0, rel=1e-2), "Single stroke ground truth aspect must be 10.0"

    res = extract_positive_text_features(canvas, rect_px=(0, 0, 30, 30))
    feats = res["features"]

    # Semantic contract assertion: must reflect component geometry, not normalized width
    assert feats["connected_components_count"] == 1, (
        f"Expected connected_components_count == 1, got {feats['connected_components_count']}"
    )
    assert feats["max_cc_aspect_ratio"] == pytest.approx(10.0, rel=1e-2), (
        f"Contract violation: expected aspect ratio 10.0, got {feats['max_cc_aspect_ratio']}"
    )


def test_cc09_diagonal_connectivity_historical_scipy():
    """CC-09: Verifies historical 4-connectivity contract where diagonal pixels are distinct.

    Under historical scipy.ndimage.label(..., structure=None), default structure is
    generate_binary_structure(rank=2, connectivity=1), which is strictly 4-connected.
    Two purely diagonal pixels must yield connected_components_count == 2.
    """
    canvas = np.full((20, 20), 255, dtype=np.uint8)
    # Two purely diagonal pixels
    canvas[5, 5] = 0
    canvas[6, 6] = 0

    dark = (canvas <= 128)
    gt_count, _, _, _ = _ground_truth_connected_components(dark)
    assert gt_count == 2, "Historical 4-connectivity ground truth must treat diagonal pixels as 2 components"

    res = extract_positive_text_features(canvas, rect_px=(0, 0, 20, 20))
    feats = res["features"]

    # Semantic contract: must reflect 2 distinct 4-connected components
    assert feats["connected_components_count"] == 2, (
        f"Expected connected_components_count == 2 (4-connected), got {feats['connected_components_count']}"
    )

"""
PROMETEO · FASE 0B · VERIFIER 2.0 (§14)
───────────────────────────────────────
El verificador ya no comprueba solo "¿el texto está donde debe?".
Mide dimensiones independientes:

  · pixel contamination — cuántos píxeles CAMBIARON fuera de la región
    permitida (detecta daños colaterales del pipeline completo);
  · background similarity — el parche reparado debe parecerse al fondo
    que lo rodea (media/desviación del anillo vs la región);
  · OCR readback — un OCR externo re-lee la salida: el motor lee su
    propio trabajo con un lector imperfecto e independiente;
  · character error rate — del readback contra el texto esperado.
"""
from __future__ import annotations

from typing import Optional, Tuple

# ── Umbrales del gate (política explícita · una sola fuente) ─────────
# MÉTRICAS RUNTIME (sin ground truth — válidas en producción):
#   page_skew_deg, line_structure_in_region, ocr_readback,
#   pixel_contamination, background_similarity.
# MÉTRICAS CON GROUND TRUTH (solo benchmark/laboratorio, nunca runtime):
#   gt_error.size_err_pt / baseline_err_pt / bbox_iou en raster.py.
SKEW_MAX_DEG = 1.5      # rotación de página detectable ANTES de editar
BG_MIN_SCORE = 0.75     # antes 0.5: aceptaba parches visualmente obvios
CONTAM_MAX = 0.002      # fracción de píxeles cambiados fuera de región
SIZE_MIN_PT = 4.0       # tipografía mínima plausible
SIZE_RATIO = (0.5, 2.0) # tamaño estimado vs mediana de líneas vecinas


def page_skew_deg(ocr_page) -> float:
    """Ángulo dominante del texto (grados) desde los centros de las
    palabras OCR: mediana de la pendiente por línea. EVIDENCIA RUNTIME
    — del propio documento, sin ground truth. Una página rotada (M/C
    del benchmark) infla las cajas y desalinea baselines: se detecta
    aquí y se rechaza ANTES de editar."""
    import math
    import statistics
    angles = []
    for line in ocr_page.lines():
        if len(line) < 3:
            continue
        xs = [(w.bbox_px[0] + w.bbox_px[2]) / 2 for w in line]
        ys = [w.bbox_px[3] for w in line]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = sum((x - mx) ** 2 for x in xs)
        if den < 1.0:
            continue
        angles.append(math.degrees(math.atan(num / den)))
    if not angles:
        return 0.0
    return float(statistics.median(angles))


def _longest_true_run(bool_row) -> int:
    import numpy as np
    if bool_row.size == 0:
        return 0
    padded = np.concatenate(([False], bool_row, [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    if changes.size < 2:
        return 0
    runs = changes[1::2] - changes[0::2]
    return int(runs.max()) if runs.size else 0


def line_structure_in_region(img, rect_px: Tuple[int, int, int, int],
                             min_frac: float = 0.35, min_px: int = 60,
                             dark: int = 128, min_strokes: int = 2) -> dict:
    """Detecta estructuras NO-textuales (líneas de tabla, bordes,
    subrayados) dentro de la región que sería reparada. EVIDENCIA
    RUNTIME: rachas de tinta demasiado largas para ser glifos.
    Reparar rectangularmente una región con estructura DESTRUYE
    información → el gate de clearance debe impedirlo."""
    import numpy as np
    h, w = img.shape[:2]
    x0, y0, x1, y1 = rect_px
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(w, int(x1)), min(h, int(y1))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return {"has_structure": False, "reason": "region_degenerate"}
    reg = img[y0:y1, x0:x1] < dark
    rh, rw = reg.shape
    # un glifo no produce rachas de 35 % de la región ni de 60 px
    lh = min(rw, max(int(min_frac * rw), min_px))
    lv = min(rh, max(int(min_frac * rh), min_px))
    h_rows = sum(1 for r in reg if _longest_true_run(r) >= lh)
    v_cols = sum(1 for c in reg.T if _longest_true_run(c) >= lv)
    has = h_rows >= min_strokes or v_cols >= min_strokes
    kind = ("h" if h_rows >= min_strokes else "") + \
           ("v" if v_cols >= min_strokes else "")
    return {"has_structure": bool(has), "kind": kind or None,
            "h_line_rows": int(h_rows), "v_line_cols": int(v_cols),
            "threshold_px": {"h": lh, "v": lv}}


def extract_positive_text_features(local_region,
                                   rect_px: Tuple[int, int, int, int],
                                   span: Optional[dict] = None,
                                   global_img: Optional[any] = None,
                                   ocr_page: Optional[any] = None,
                                   ocr_provenance: Optional[dict] = None,
                                   pad_margin_px: int = 15,
                                   dark: int = 128) -> dict:
    """Extrae observables morfológicos y de contexto para Stage 3A (Observation Only).

    Esta función es puramente observacional y no posee autoridad de decisión de clearance
    (DECISION_AUTHORITY = NONE).
    """
    import numpy as np

    x0, y0, x1, y1 = rect_px
    x0, y0 = int(x0), int(y0)
    x1, y1 = int(x1), int(y1)

    # 1. Normalizar local_region a máscara booleana (True = tinta oscura)
    if hasattr(local_region, "shape"):
        if local_region.ndim == 2:
            reg_dark = local_region < dark if local_region.dtype != bool else local_region
        else:
            reg_dark = local_region[:, :, 0] < dark
    else:
        reg_dark = np.zeros((max(y1 - y0, 0), max(x1 - x0, 0)), dtype=bool)

    rh, rw = reg_dark.shape

    # 2. Safety observations: outside continuity
    outside_cols = 0
    max_outside_run = 0
    global_available = bool(global_img is not None and hasattr(global_img, "shape"))

    if global_available and rh > 0 and rw > 0:
        gh, gw = global_img.shape[:2]
        gx0, gy0 = max(0, x0), max(0, y0)
        gx1, gy1 = min(gw, x1), min(gh, y1)

        for cx in range(gx0, gx1):
            local_cx = cx - x0
            if local_cx < 0 or local_cx >= rw:
                continue
            col_local = reg_dark[:, local_cx]
            if not np.any(col_local):
                continue

            run_top = 0
            if gy0 > 0 and col_local[0]:
                y_curr = gy0 - 1
                while y_curr >= max(0, gy0 - pad_margin_px):
                    val = global_img[y_curr, cx] < dark if global_img.ndim == 2 else global_img[y_curr, cx, 0] < dark
                    if val:
                        run_top += 1
                        y_curr -= 1
                    else:
                        break

            run_bottom = 0
            if gy1 < gh and col_local[-1]:
                y_curr = gy1
                while y_curr < min(gh, gy1 + pad_margin_px):
                    val = global_img[y_curr, cx] < dark if global_img.ndim == 2 else global_img[y_curr, cx, 0] < dark
                    if val:
                        run_bottom += 1
                        y_curr += 1
                    else:
                        break

            outside_run = max(run_top, run_bottom)
            if outside_run >= pad_margin_px:
                outside_cols += 1
            if outside_run > max_outside_run:
                max_outside_run = outside_run

    local_v_runs = [_longest_true_run(col) for col in reg_dark.T] if rw > 0 else []
    local_v_cols = sum(1 for r in local_v_runs if r >= min(rh, 20))

    safety_obs = {
        "outside_continuity_cols": int(outside_cols),
        "max_outside_run_px": int(max_outside_run),
        "global_context_available": bool(global_available),
        "local_v_cols": int(local_v_cols),
        "rect_px": (x0, y0, x1, y1),
    }

    # 3. Normalization parameters
    text_content = str(span.get("text", "")) if (span and isinstance(span, dict)) else ""
    char_count = len(text_content.strip())
    span_w = max(float(x1 - x0), 1.0)
    span_h = max(float(y1 - y0), 1.0)
    est_char_w = span_w / max(float(char_count), 1.0) if char_count > 0 else max(float(rw), 1.0)

    normalization = {
        "span_width_px": float(span_w),
        "span_height_px": float(span_h),
        "char_count": int(char_count),
        "estimated_char_width_px": float(est_char_w),
    }

    # 4. Feature: envelope_confinement_ratio
    total_ink = int(np.sum(reg_dark))
    if total_ink == 0 or rh <= 0:
        envelope_confinement_ratio = 1.0
    else:
        m_top = max(1, int(0.05 * rh))
        m_bot = max(1, int(0.05 * rh))
        ink_margins = int(np.sum(reg_dark[:m_top, :])) + int(np.sum(reg_dark[rh - m_bot:, :]))
        envelope_confinement_ratio = float(np.clip(1.0 - (float(ink_margins) / float(total_ink)), 0.0, 1.0))

    # 5. Feature: gutter_ink_density
    gutter_ink_density = 0.0
    if ocr_page is not None and hasattr(ocr_page, "words") and rh > 0 and rw > 0:
        words_in_rect = []
        try:
            page_words = ocr_page.words if isinstance(ocr_page.words, list) else ocr_page.words()
            for w in page_words:
                if hasattr(w, "bbox_px") and len(w.bbox_px) >= 4:
                    wx0, wy0, wx1, wy1 = w.bbox_px
                    if not (wx1 <= x0 or wx0 >= x1 or wy1 <= y0 or wy0 >= y1):
                        words_in_rect.append((wx0, wy0, wx1, wy1))
        except Exception:
            pass

        if len(words_in_rect) >= 2:
            words_in_rect.sort(key=lambda b: b[0])
            gutter_dark_pixels = 0
            gutter_total_pixels = 0
            for i in range(len(words_in_rect) - 1):
                gx0 = max(0, int(words_in_rect[i][2] - x0))
                gx1 = min(rw, int(words_in_rect[i + 1][0] - x0))
                if gx1 > gx0:
                    gutter_dark_pixels += int(np.sum(reg_dark[:, gx0:gx1]))
                    gutter_total_pixels += (gx1 - gx0) * rh
            if gutter_total_pixels > 0:
                gutter_ink_density = float(np.clip(float(gutter_dark_pixels) / float(gutter_total_pixels), 0.0, 1.0))

    # 6. Feature: vertical clusters & spacing
    clusters = []
    in_cluster = False
    c_start = 0
    stroke_threshold = max(int(0.25 * rh), 5) if rh > 0 else 5
    for cx, r in enumerate(local_v_runs):
        if r >= stroke_threshold:
            if not in_cluster:
                c_start = cx
                in_cluster = True
        else:
            if in_cluster:
                clusters.append((c_start, cx - 1))
                in_cluster = False
    if in_cluster:
        clusters.append((c_start, len(local_v_runs) - 1))

    observed_clusters_count = len(clusters)
    widths = [float(c[1] - c[0] + 1) for c in clusters]
    norm_widths = [w / max(est_char_w, 1.0) for w in widths]
    spacings = [float(clusters[i + 1][0] - clusters[i][1]) for i in range(len(clusters) - 1)]
    norm_spacings = [s / max(est_char_w, 1.0) for s in spacings]

    # 7. Feature: observed_glyph_modulation_score
    col_ink = np.sum(reg_dark, axis=0).astype(float) if rw > 0 else np.array([])
    if len(col_ink) == 0 or np.sum(col_ink) == 0:
        observed_glyph_modulation_score = 0.0
    else:
        observed_glyph_modulation_score = float(np.clip(np.std(col_ink) / (np.mean(col_ink) + 1e-6), 0.0, 10.0))

    # 8. Feature: connected components (OpenCV connectivity=4 explícito)
    cc_count = 0
    mean_aspect_ratio = 0.0
    max_aspect_ratio = 0.0
    if rh > 0 and rw > 0 and total_ink > 0:
        import cv2
        img_u8 = reg_dark.astype(np.uint8)
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(img_u8, connectivity=4)
        cc_count = int(n_labels - 1)
        if cc_count > 0:
            aspect_ratios = [
                float(stats[lbl, cv2.CC_STAT_HEIGHT]) / max(float(stats[lbl, cv2.CC_STAT_WIDTH]), 1.0)
                for lbl in range(1, n_labels)
            ]
            if aspect_ratios:
                mean_aspect_ratio = float(np.mean(aspect_ratios))
                max_aspect_ratio = float(np.max(aspect_ratios))

    features = {
        "envelope_confinement_ratio": float(envelope_confinement_ratio),
        "gutter_ink_density": float(gutter_ink_density),
        "observed_clusters_count": int(observed_clusters_count),
        "normalized_cluster_widths": norm_widths,
        "normalized_cluster_spacings": norm_spacings,
        "observed_glyph_modulation_score": float(observed_glyph_modulation_score),
        "connected_components_count": int(cc_count),
        "mean_cc_aspect_ratio": float(mean_aspect_ratio),
        "max_cc_aspect_ratio": float(max_aspect_ratio),
    }

    evidence_trace = {
        "status": "PROTECTED_STRUCTURE" if outside_cols >= 1 and max_outside_run >= pad_margin_px else "AMBIGUOUS",
        "decision_authority": "NONE",
        "stage": "3A_FEATURE_EXTRACTION_ONLY",
    }

    return {
        "features": features,
        "normalization": normalization,
        "safety_observations": safety_obs,
        "evidence_trace": evidence_trace,
    }


def vertical_structure_assessment(local_region,
                                  rect_px: Tuple[int, int, int, int],
                                  span: Optional[dict] = None,
                                  global_img: Optional[any] = None,
                                  ocr_page: Optional[any] = None,
                                  ocr_provenance: Optional[dict] = None,
                                  pad_margin_px: int = 15,
                                  dark: int = 128) -> dict:
    """Evaluador triestado conservador de estructuras verticales (FC-009 Stage 1).

    Salida formal triestado:
      - PROTECTED_STRUCTURE: continuidad vertical exterior demostrada en global_img >= pad_margin_px.
      - AMBIGUOUS: no hay continuidad exterior, pero la evidencia actual no permite atribuir
        positivamente la tinta a tipografía en Runtime (honest reject conservador).
      - TEXT_COMPATIBLE: reservado para cuando exista mecanismo runtime demostrado de atribución positiva.

    Invariante de seguridad:
      has_structure = (status in ("PROTECTED_STRUCTURE", "AMBIGUOUS"))
    """
    import numpy as np

    x0, y0, x1, y1 = rect_px
    x0, y0 = int(x0), int(y0)
    x1, y1 = int(x1), int(y1)

    # Normalizar local_region a máscara booleana (True = tinta oscura)
    if hasattr(local_region, "shape"):
        if local_region.ndim == 2:
            reg_dark = local_region < dark if local_region.dtype != bool else local_region
        else:
            reg_dark = local_region[:, :, 0] < dark
    else:
        reg_dark = np.zeros((max(y1 - y0, 0), max(x1 - x0, 0)), dtype=bool)

    rh, rw = reg_dark.shape
    local_v_runs = [_longest_true_run(col) for col in reg_dark.T] if rw > 0 else []
    local_v_cols = sum(1 for r in local_v_runs if r >= min(rh, 20))

    outside_cols = 0
    max_outside_run = 0
    global_available = (global_img is not None and hasattr(global_img, "shape"))

    if global_available and rh > 0 and rw > 0:
        gh, gw = global_img.shape[:2]
        gx0, gy0 = max(0, x0), max(0, y0)
        gx1, gy1 = min(gw, x1), min(gh, y1)

        # Evaluar continuidad vertical por columna x en [gx0, gx1)
        for cx in range(gx0, gx1):
            local_cx = cx - x0
            if local_cx < 0 or local_cx >= rw:
                continue
            col_local = reg_dark[:, local_cx]
            if not np.any(col_local):
                continue

            # Verificar continuidad arriba (top margin: y0 - pad_margin_px .. y0)
            run_top = 0
            if gy0 > 0 and col_local[0]:  # Tinta toca el borde superior de rect_px
                y_curr = gy0 - 1
                while y_curr >= max(0, gy0 - pad_margin_px):
                    val = global_img[y_curr, cx] < dark if global_img.ndim == 2 else global_img[y_curr, cx, 0] < dark
                    if val:
                        run_top += 1
                        y_curr -= 1
                    else:
                        break

            # Verificar continuidad abajo (bottom margin: y1 .. y1 + pad_margin_px)
            run_bottom = 0
            if gy1 < gh and col_local[-1]:  # Tinta toca el borde inferior de rect_px
                y_curr = gy1
                while y_curr < min(gh, gy1 + pad_margin_px):
                    val = global_img[y_curr, cx] < dark if global_img.ndim == 2 else global_img[y_curr, cx, 0] < dark
                    if val:
                        run_bottom += 1
                        y_curr += 1
                    else:
                        break

            outside_run = max(run_top, run_bottom)
            if outside_run >= pad_margin_px:
                outside_cols += 1
            if outside_run > max_outside_run:
                max_outside_run = outside_run

    has_outside_continuity = (outside_cols >= 1 and max_outside_run >= pad_margin_px)

    if has_outside_continuity:
        status = "PROTECTED_STRUCTURE"
        has_structure = True
        reason = "outside_vertical_continuity"
    else:
        status = "AMBIGUOUS"
        has_structure = True
        reason = "insufficient_evidence_to_disambiguate"

    ambiguous_cols = local_v_cols if not has_outside_continuity else 0

    trace = {
        "outside_continuity_cols": int(outside_cols),
        "max_outside_run_px": int(max_outside_run),
        "local_v_cols": int(local_v_cols),
        "ambiguous_cols": int(ambiguous_cols),
        "rect_px": (x0, y0, x1, y1),
        "global_context_available": bool(global_available),
        "ocr_provenance_received": bool(ocr_provenance is not None),
    }

    return {
        "status": status,
        "has_structure": bool(has_structure),
        "reason": reason,
        "evidence_trace": trace,
    }


def pixel_contamination(before, after, allowed_px: Tuple[int, int, int, int],
                        tol: int = 25, margin: int = 8) -> dict:
    """Fracción de píxeles que cambiaron FUERA de la zona permitida."""
    import numpy as np
    h, w = before.shape
    diff = np.abs(after.astype(np.int16) - before.astype(np.int16)) > tol
    x0, y0, x1, y1 = allowed_px
    allowed = np.zeros((h, w), dtype=bool)
    allowed[max(0, y0 - margin):min(h, y1 + margin),
            max(0, x0 - margin):min(w, x1 + margin)] = True
    outside = diff & ~allowed
    n_out = int(outside.sum())
    n_out_possible = int((~allowed).sum())
    return {
        "changed_outside_px": n_out,
        "fraction_outside": n_out / max(n_out_possible, 1),
        "changed_inside_px": int((diff & allowed).sum()),
    }


def background_similarity(after, rect_px: Tuple[int, int, int, int],
                          ring_width: int = 6,
                          ink_threshold: int = 180) -> dict:
    """La región reparada vs su anillo — SOLO píxeles de fondo en AMBOS
    lados (la tinta del texto nuevo y de las líneas vecinas no es fondo
    y no debe contaminar la métrica)."""
    import numpy as np
    h, w = after.shape
    x0, y0, x1, y1 = rect_px
    X0, Y0 = max(0, x0 - ring_width), max(0, y0 - ring_width)
    X1, Y1 = min(w, x1 + ring_width), min(h, y1 + ring_width)
    region = after[y0:y1, x0:x1]
    ring_mask = np.ones((Y1 - Y0, X1 - X0), dtype=bool)
    ring_mask[(y0 - Y0):(y1 - Y0), (x0 - X0):(x1 - X0)] = False
    ring_vals = after[Y0:Y1, X0:X1][ring_mask]
    bg = region[region >= ink_threshold]
    ring_bg = ring_vals[ring_vals >= ink_threshold]
    rm = float(bg.mean()) if bg.size else 255.0
    rs = float(bg.std()) if bg.size else 0.0
    gm = float(ring_bg.mean()) if ring_bg.size else 255.0
    gs = float(ring_bg.std()) if ring_bg.size else 0.0
    return {
        "region_mean": round(rm, 2), "region_std": round(rs, 2),
        "ring_mean": round(gm, 2), "ring_std": round(gs, 2),
        "mean_diff": round(abs(rm - gm), 2),
        "score": round(max(0.0, 1.0 - abs(rm - gm) / 40.0), 3),
    }


def _cer(a: str, b: str) -> float:
    if not a:
        return 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / len(a)


def ocr_readback(provider, image, expected_text: str,
                 region_px: Optional[Tuple[int, int, int, int]] = None) -> dict:
    """Re-OCR de la salida: ¿el texto nuevo es recuperable? ¿dónde cae?

    Compara contra la LÍNEA agregada de la región (un reemplazo largo
    son varias palabras del OCR, no una)."""
    page = provider.process(image, dpi=300.0)

    def in_region(w):
        if not region_px:
            return True
        cx = (w.bbox_px[0] + w.bbox_px[2]) / 2
        cy = (w.bbox_px[1] + w.bbox_px[3]) / 2
        return (region_px[0] - 40 <= cx <= region_px[2] + 60
                and region_px[1] - 30 <= cy <= region_px[3] + 30)

    words = [w for w in page.words if in_region(w)]
    words.sort(key=lambda w: (round(w.bbox_px[1] / 20), w.bbox_px[0]))
    line = " ".join(w.text for w in words)
    best = None
    if words:
        exp_l = expected_text.lower()
        line_l = line.lower()
        # contención: el esperado dentro de la línea leída ⇒ recuperación
        # exacta (los vecinos de la línea no son error del readback)
        cer = 0.0 if exp_l in line_l else _cer(exp_l, line_l)
        best = {"text": line,
                "conf": round(sum(w.conf for w in words) / len(words), 1),
                "bbox_px": (min(w.bbox_px[0] for w in words),
                            min(w.bbox_px[1] for w in words),
                            max(w.bbox_px[2] for w in words),
                            max(w.bbox_px[3] for w in words)),
                "cer": round(cer, 4)}
    found = best is not None and best["cer"] <= 0.34
    return {"found": found, "best": best}


# ── FC-009 STAGE 3A-4: OBSERVATIONAL EVIDENCE STATE BUILDER ──────────────────

_VALID_SOURCE_REPRESENTATION_CLASSES = frozenset({
    "TEXT_OPERATOR",
    "VECTOR_PATH_OPERATOR",
    "IMAGE_RASTER",
    "OCR_TEXT_LAYER",
    "MIXED",
    "UNKNOWN",
})


def _is_finite_numeric(val) -> bool:
    """Verifica si un valor es una medición numérica real y finita, excluyendo booleanos."""
    if isinstance(val, bool):
        return False
    try:
        import numpy as np
        if isinstance(val, np.bool_):
            return False
        numeric_types = (int, float, np.integer, np.floating)
    except ImportError:
        numeric_types = (int, float)

    if not isinstance(val, numeric_types):
        return False
    try:
        import math
        return math.isfinite(val)
    except (TypeError, ValueError):
        return False


def build_stage3_evidence_state(
    features: Optional[dict] = None,
    *,
    provenance_info: Optional[dict] = None,
    context_observations: Optional[dict] = None,
    span: Optional[dict] = None,
    **kwargs
) -> dict:
    """Construye el estado de evidencia observacional desacoplado (Stage 3A-4).

    Esta función es PURAMENTE OBSERVACIONAL.
    Invariantes absolutas de seguridad:
      - semantic_claim es incondicionalmente 'UNRESOLVED'.
      - decision_authority es incondicionalmente 'NONE'.
      - has_universal_evidence es incondicionalmente False.
      - SUFFICIENT nunca se emite en Stage 3A-4.
      - Prohibición estricta de TEXT_COMPATIBLE y STRONG.
    """
    # 1. Dimensión POSITIVE_TEXT_EVIDENCE
    candidate_signals = []
    language_context_candidate = None
    if features and isinstance(features, dict):
        cmr = features.get("cluster_modulation_ratio")
        if _is_finite_numeric(cmr) and cmr > 0:
            candidate_signals.append("cluster_modulation_observed")
    if context_observations and isinstance(context_observations, dict):
        if context_observations.get("language_context_candidate"):
            language_context_candidate = str(context_observations["language_context_candidate"])

    positive_text_evidence = {
        "candidate_signals": candidate_signals,
        "has_universal_evidence": False,
        "language_context_candidate": language_context_candidate,
    }

    # 2. Dimensión GRAPHIC_COUNTEREVIDENCE
    vert_cont = False
    ortho_grid = False
    repeated_x = False
    morph_anomaly = False
    details = []

    if context_observations and isinstance(context_observations, dict):
        vert_cont = context_observations.get("vertical_continuity_crossing_leading") is True
        ortho_grid = context_observations.get("orthogonal_grid_junction") is True
        repeated_x = context_observations.get("repeated_x_alignment") is True
        morph_anomaly = (
            context_observations.get("morphology_anomaly_observed") is True
            or context_observations.get("morphology_anomaly_candidate") is True
        )

    if features and isinstance(features, dict):
        aspect_ratio = features.get("max_cc_aspect_ratio")
        if _is_finite_numeric(aspect_ratio) and aspect_ratio > 20.0:
            morph_anomaly = True

    present = vert_cont or ortho_grid
    if vert_cont:
        details.append("vertical_continuity_crossing_leading")
    if ortho_grid:
        details.append("orthogonal_grid_junction")
    if repeated_x:
        details.append("repeated_x_alignment_observational_only")
    if morph_anomaly:
        details.append("morphology_anomaly_candidate")

    graphic_counterevidence = {
        "present": present,
        "vertical_continuity_crossing_leading": vert_cont,
        "orthogonal_grid_junction": ortho_grid,
        "repeated_x_alignment": repeated_x,
        "morphology_anomaly_candidate": morph_anomaly,
        "details": details,
    }

    # 3. Dimensión REPRESENTATION_PROVENANCE
    source_representation_class = "UNKNOWN"
    authoring_origin = "UNAVAILABLE"
    is_raster_only = False
    has_inv_text = False
    has_underlying_img = False

    if provenance_info and isinstance(provenance_info, dict):
        raw_src = provenance_info.get("source_representation_class")
        if isinstance(raw_src, str) and raw_src in _VALID_SOURCE_REPRESENTATION_CLASSES:
            source_representation_class = raw_src
        else:
            source_representation_class = "UNKNOWN"

        v_type = provenance_info.get("vector_item_type")
        has_inv_text = provenance_info.get("has_invisible_text_layer") is True
        has_underlying_img = provenance_info.get("has_underlying_image") is True

        if source_representation_class == "IMAGE_RASTER":
            is_raster_only = True
            authoring_origin = "UNAVAILABLE"
        elif source_representation_class == "VECTOR_PATH_OPERATOR":
            if v_type == "curve_outline":
                authoring_origin = "OUTLINED_OR_UNKNOWN"
            else:
                authoring_origin = "UNAVAILABLE"
        elif source_representation_class == "TEXT_OPERATOR":
            authoring_origin = "UNAVAILABLE"
        elif source_representation_class == "MIXED":
            authoring_origin = "UNAVAILABLE"

    representation_provenance = {
        "source_representation_class": source_representation_class,
        "authoring_origin": authoring_origin,
        "is_raster_only": is_raster_only,
    }

    # 4. Dimensión SUFFICIENCY & CONFLICT
    is_ocr_sandwich = (has_inv_text and has_underlying_img) or (
        source_representation_class == "MIXED" and (has_inv_text or has_underlying_img)
    )
    text_with_graphic_counter = (source_representation_class == "TEXT_OPERATOR" and present)
    evidence_conflict = bool(is_ocr_sandwich or text_with_graphic_counter)

    if evidence_conflict:
        evidence_sufficiency = "CONFLICTED"
    elif is_raster_only or (source_representation_class in ("IMAGE_RASTER", "UNKNOWN") and not present):
        evidence_sufficiency = "INSUFFICIENT"
    else:
        evidence_sufficiency = "PARTIAL"

    return {
        "positive_text_evidence": positive_text_evidence,
        "graphic_counterevidence": graphic_counterevidence,
        "representation_provenance": representation_provenance,
        "evidence_conflict": evidence_conflict,
        "evidence_sufficiency": evidence_sufficiency,
        "semantic_claim": "UNRESOLVED",
        "decision_authority": "NONE",
    }


def evaluate_stage3_authority_preconditions(
    evidence_state: Optional[dict] = None,
    **kwargs
) -> dict:
    """Evalúa las precondiciones de autoridad para Stage 3B (Stage 3B-0).

    Arquitectura Deny-by-Default:
      EVIDENCE (Stage 3A-4)
        ↓
      AUTHORITY PRECONDITIONS (Stage 3B-0)
        ↓
      AUTHORITY DECISION (Stage 3B futuro)
        ↓
      RUNTIME ACTION (Stage 3B futuro)

    Invariantes Epistemológicos:
      - authority_candidate es incondicionalmente False.
      - authority_level es incondicionalmente 'NONE'.
      - decision_authority es incondicionalmente 'NONE'.
      - No otorga autoridad de ejecución runtime.
      - Ausencia de contraevidencia NO confiere autoridad positiva.
      - Salida estrictamente determinista y serializable a JSON.
      - Sin puntuaciones, sin probabilidades, sin floats 0-1, sin umbrales agregados.
      - Prohibición estricta de términos de autorización anticipada.
    """
    if evidence_state is None or not isinstance(evidence_state, dict):
        evidence_state = build_stage3_evidence_state()

    pos_ev = evidence_state.get("positive_text_evidence") or {}
    graph_ev = evidence_state.get("graphic_counterevidence") or {}
    rep_prov = evidence_state.get("representation_provenance") or {}

    candidate_signals = pos_ev.get("candidate_signals") or []
    lang_candidate = pos_ev.get("language_context_candidate")
    src_class = rep_prov.get("source_representation_class", "UNKNOWN")
    authoring_origin = rep_prov.get("authoring_origin", "UNAVAILABLE")

    evidence_conflict = bool(evidence_state.get("evidence_conflict") is True)
    evidence_sufficiency = str(evidence_state.get("evidence_sufficiency", "INSUFFICIENT"))
    semantic_claim = str(evidence_state.get("semantic_claim", "UNRESOLVED"))

    conflict_present = bool(evidence_conflict or evidence_sufficiency == "CONFLICTED")
    ambiguity_present = bool(
        evidence_sufficiency in ("INSUFFICIENT", "CONFLICTED")
        or semantic_claim == "UNRESOLVED"
    )

    # Registro de requerimientos positivos observados
    positive_requirements_met = []
    if candidate_signals:
        if "cluster_modulation_observed" in candidate_signals:
            positive_requirements_met.append("FONT_METRIC_CANDIDATE_PRESENT")
    if lang_candidate:
        positive_requirements_met.append("LEXICAL_CONTEXT_PRESENT")
    if src_class == "TEXT_OPERATOR":
        positive_requirements_met.append("TEXT_REPRESENTATION_PRESENT")

    positive_requirements_missing = [
        "NO_VALIDATED_POSITIVE_TEXT_SIGNAL"
    ]

    # Evaluador de blockers en orden determinista
    blockers = []

    if evidence_sufficiency == "INSUFFICIENT":
        blockers.append("EVIDENCE_INSUFFICIENT")

    if conflict_present:
        blockers.append("EVIDENCE_CONFLICTED")

    if semantic_claim == "UNRESOLVED":
        blockers.append("SEMANTIC_CLAIM_UNRESOLVED")

    # Universal positive rule blocker (epistemic state invariant)
    blockers.append("NO_VALIDATED_POSITIVE_TEXT_SIGNAL")

    # Representation-only blocker
    is_representation_only = (
        src_class in ("TEXT_OPERATOR", "VECTOR_PATH_OPERATOR")
        and not candidate_signals
        and not lang_candidate
    )
    if is_representation_only:
        blockers.append("REPRESENTATION_ONLY")

    # Graphic counterevidence blocker
    if graph_ev.get("present") is True:
        blockers.append("GRAPHIC_COUNTEREVIDENCE_PRESENT")

    # Authoring origin blocker
    if authoring_origin == "UNAVAILABLE":
        blockers.append("AUTHORING_ORIGIN_UNAVAILABLE")

    # Runtime boundary blocker
    blockers.append("RUNTIME_INTEGRATION_FORBIDDEN")

    return {
        "authority_candidate": False,
        "authority_level": "NONE",
        "blocking_reasons": blockers,
        "positive_requirements_met": positive_requirements_met,
        "positive_requirements_missing": positive_requirements_missing,
        "conflict_present": conflict_present,
        "ambiguity_present": ambiguity_present,
        "decision_authority": "NONE",
    }

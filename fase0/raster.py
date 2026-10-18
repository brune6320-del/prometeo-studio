"""
PROMETEO · PRE-GATE · PIPELINE RASTER REAL (§7 + auditoría 0a09226)
────────────────────────────────────────────────────────────────────
El ciclo que NO estaba demostrado — sin ground truth alimentando al
sistema. El único dato externo es el OCR REAL:

  SCAN/IMAGEN → OCR real → bloques px → pt (geometry) →
  estimación tipográfica → PRE-GATES (skew/gráficos/tipografía, ANTES
  de mutar) → validate (políticas) → mask/reparación de fondo →
  texto determinista (misma Font que mide) → composición → export →
  VERIFY 2.1 (readback INDEPENDIENTE + contaminación + fondo) →
  política explícita de 7 dimensiones → clasificación.

El ground truth vectorial se usa EXCLUSIVAMENTE para medir el error
en el reporte (benchmark), nunca como entrada del pipeline.

POLÍTICA DE `ok` (PRE-GATE): ok=true SOLO si las 7 dimensiones pasan:
  text_ok ∧ geometry_ok ∧ background_ok ∧ contamination_ok ∧
  typography_ok ∧ graphics_clearance_ok ∧ readback_ok
  · readback_ok exige independence_level ≠ NONE (el verificador no
    puede ser el mismo camino OCR que detectó).
  · geometry_ok=false → ok=false SIEMPRE en producción. El único
    escape es mode="experimental" → ok_experimental=true, ok=false.
  · Los rechazos de pre-gate ocurren ANTES de escribir un solo byte.

Clasificación: PASS / HONEST_REJECT (con reject_reason).
SILENT_FAILURE / CRASH los clasifica el harness del Gate (gate_reality)
contra evidencia externa (gt / anotación humana) — el pipeline solo
puede garantizar sus dimensiones.
"""
from __future__ import annotations

import datetime
import hashlib
from typing import Dict, List, Optional, Tuple

import numpy as np
import pymupdf
from PIL import Image

from engine import _deterministic_id, _norm_text, sha256_file
from geometry import SpaceTransform
from ocr_provider import (JitterOCRProvider, OCRProvider,
                          TesseractOCRProvider, default_verifier_for,
                          independence_level)
from operations import ReplaceText, validate_replace
from repair import repair_region
from render import FontBook

DPI = 300.0
# Constante empírica: la caja de palabra de Tesseract abraza la TINTA
# (cap→descender observado ≈ 0.76 em en Helvetica 11pt). El error
# residual por fuente se MIDE por caso en el benchmark (caso H).
INK_BOX_RATIO = 0.76
DESCENDER_RATIO = 0.22
RIGHT_MARGIN_PT = 36.0

# ── FC-008 · localización multi-modo (CONGELADO por la matriz de
# falsificación evidence/CAL-005/fc008_matrix.txt — solo modos
# respaldados por la matriz; sin alta dinámica de modos) ─────────────
# Política: MISMO raster, matcher intacto. Si el modo primario acierta,
# el camino no cambia (T5). Si falla, se observan TODOS los modos
# restantes y la resolución es la política pura _resolve_localization:
# candidatos incompatibles → ambigüedad → HONEST_REJECT explícito.
FC008_MODES = ("--psm 6", "--psm 3", "--psm 11")
# Preferencia determinista del verificador: distinta config del modo
# que LOCALIZÓ (FC-006). Nunca promovida a STRONG; NONE jamás PASS.
VERIFIER_PREFERENCE = ("--psm 3", "--psm 11", "--psm 6")


def _bboxes_intersect(a, b) -> bool:
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    return ix > 0 and iy > 0


def _resolve_localization(candidates):
    """Política pura de resolución FC-008 (unit-testeada en T4).
    Selección por ORDEN CONGELADO (confidence es evidencia auxiliar,
    jamás el selector). Candidatos materialmente incompatibles sin
    evidencia suficiente → ambigüedad → HONEST_REJECT, nunca elección
    silenciosa."""
    if not candidates:
        return {"status": "not_found", "reason": "texto_no_encontrado_por_ocr",
                "chosen": None}
    order = {cfg: i for i, cfg in enumerate(FC008_MODES)}
    for i, a in enumerate(candidates):
        for b in candidates[i + 1:]:
            if not _bboxes_intersect(a["bbox_px"], b["bbox_px"]):
                return {"status": "ambiguous",
                        "reason": "ocr_localization_ambiguous",
                        "chosen": None,
                        "incompatible": [a["config"], b["config"]]}
    chosen = min(candidates, key=lambda c: order.get(c["config"], 99))
    return {"status": "localized", "reason": "orden_congelado",
            "chosen": chosen}

# mapa dimensión-fallida → razón de rechazo (orden = prioridad)
_REJECT_REASONS = [
    ("geometry_ok", "page_skew"),
    ("graphics_clearance_ok", "grafico_en_region"),
    ("typography_ok", "tipografia_implausible"),
    ("background_ok", "background"),
    ("contamination_ok", "contaminacion"),
    ("readback_ok", "readback"),
    ("text_ok", "texto"),
]


def _dummy_fontbook() -> FontBook:
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    return FontBook(doc, page)


def estimate_typography(line_words) -> Tuple[float, Tuple[float, float]]:
    """Estima (size_pt, baseline_pt) desde las cajas de tinta del OCR.
    Limitación declarada: sin font matching real (Fase 3). El ERROR de
    esta estimación se mide en el benchmark contra ground truth."""
    x0 = min(w.bbox_px[0] for w in line_words)
    y0 = min(w.bbox_px[1] for w in line_words)
    y1 = max(w.bbox_px[3] for w in line_words)
    h_px = y1 - y0
    size_px = h_px / INK_BOX_RATIO
    baseline_px = y1 - DESCENDER_RATIO * size_px
    s = DPI / 72.0
    return size_px / s, (x0 / s, baseline_px / s)


def build_span_from_ocr(line_words, transform: SpaceTransform,
                        page_width_pt: float, idx: int) -> Dict:
    size_pt, (origin_x, baseline_pt) = estimate_typography(line_words)
    x0 = min(w.bbox_px[0] for w in line_words)
    y0 = min(w.bbox_px[1] for w in line_words)
    x1 = max(w.bbox_px[2] for w in line_words)
    y1 = max(w.bbox_px[3] for w in line_words)
    text = " ".join(w.text for w in line_words)
    s = DPI / 72.0
    chars = []
    for w in line_words:   # posiciones por carácter: interpolación lineal
        span_w = (w.bbox_px[2] - w.bbox_px[0]) / max(len(w.text), 1)
        for k, c in enumerate(w.text):
            chars.append({"c": c, "origin_x": (w.bbox_px[0] + k * span_w) / s,
                          "bbox_x0": (w.bbox_px[0] + k * span_w) / s})
        chars.append({"c": " ", "origin_x": w.bbox_px[2] / s,
                      "bbox_x0": w.bbox_px[2] / s})
    clearance = page_width_pt - RIGHT_MARGIN_PT - origin_x
    return {
        "id": f"r{idx}", "page": 0, "text": text,
        "bbox": (x0 / s, y0 / s, x1 / s, y1 / s),
        "origin": (origin_x, baseline_pt),
        "size": size_pt, "font": "Helvetica", "color": 0,
        "clearance_pt": max(clearance, 1.0),
        "chars": chars,
        "ocr_line_text": text,
    }


def render_text_patch(fontbook: FontBook, text: str, size_pt: float,
                      dpi: float = DPI) -> Tuple[np.ndarray, float]:
    """Renderiza texto determinista con la MISMA Font que mide. Devuelve
    (grayscale array, baseline_y_dentro_del_patch)."""
    font = fontbook.font_for("helv")
    width_pt = font.text_length(text, fontsize=size_pt)
    pad = size_pt * 0.5
    page_w = width_pt + 2 * pad
    page_h = size_pt * 1.8
    doc = pymupdf.open()
    page = doc.new_page(width=page_w, height=page_h)
    fb = FontBook(doc, page)
    fb.write(page, (pad, size_pt * 1.25), text, "helv", size_pt, 0)
    pix = page.get_pixmap(dpi=int(dpi), colorspace=pymupdf.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    doc.close()
    return arr, size_pt * 1.25 * dpi / 72.0


# ── PRE-GATES: evidencia runtime del propio documento (sin GT) ───────

def _span_region_px(span: Dict) -> Tuple[int, int, int, int]:
    """Región SUPERCONJUNTO de cualquier reparación posterior
    (bbox del span ± 3pt): sobre ella corren los gates pre-mutación."""
    s = DPI / 72.0
    b = span["bbox"]
    return (int((b[0] - 3) * s), int((b[1] - 3) * s),
            int((b[2] + 3) * s), int((b[3] + 3) * s))


def _typography_gate(ocr_page, target_line, span: Dict) -> Dict:
    """El tamaño estimado debe ser plausible contra las OTRAS líneas
    de la misma página (mediana). Evidencia runtime: no hay gt_size."""
    import verifier2
    sizes: List[float] = []
    for ln in ocr_page.lines():
        if ln is target_line:
            continue
        try:
            sizes.append(estimate_typography(ln)[0])
        except Exception:
            pass
    if len(sizes) < 2 or float(np.median(sizes)) <= 0:
        return {"ok": True, "evidence": "insuficiente",
                "n_other_lines": len(sizes)}
    med = float(np.median(sizes))
    ratio = span["size"] / med
    ok = (verifier2.SIZE_MIN_PT <= span["size"]
          and verifier2.SIZE_RATIO[0] <= ratio <= verifier2.SIZE_RATIO[1])
    return {"ok": bool(ok), "median_other_pt": round(med, 2),
            "ratio": round(ratio, 3)}


def _measure_gt(gt_pdf: Optional[str], old: str, span: Dict) -> Optional[Dict]:
    """SOLO medición para benchmark. Nunca entra al pipeline."""
    if not gt_pdf:
        return None
    from engine import extract as engine_extract
    try:
        gm = engine_extract(gt_pdf)
        gspan = next((sp for p in gm["pages"] for sp in p["spans"]
                      if old in sp["text"]), None)
        if gspan:
            return {
                "size_est_pt": round(span["size"], 2),
                "size_gt_pt": round(gspan["size"], 2),
                "size_err_pt": round(abs(span["size"] - gspan["size"]), 2),
                "bbox_iou": round(_iou(span["bbox"], gspan["bbox"]), 3),
                "baseline_err_pt": round(
                    abs(span["origin"][1] - gspan["origin"][1]), 2),
            }
    except Exception as e:   # medición best-effort
        return {"error": str(e)}
    return None


def raster_edit(pdf_path: str, old: str, new: str, out_pdf: str,
                provider: Optional[OCRProvider] = None,
                strategy: str = "mean",
                gt_pdf: Optional[str] = None,
                verifier_provider: Optional[OCRProvider] = None,
                mode: str = "production") -> Dict:
    """Ciclo completo Clase B. provider=None → Tesseract real.
    verifier_provider=None → verificador con config/motor DISTINTO
    (independence_level ≥ WEAK; pasar el mismo detector → NONE y el
    readback NO puede aprobar). mode="experimental" solo puede salvar
    geometry_ok, jamás produce ok=true."""
    import verifier2

    provider = provider or TesseractOCRProvider()
    # verifier/independencia se deciden TRAS la localización (FC-006:
    # la config del verificador debe diferir del modo que LOCALIZÓ)

    report = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "source": pdf_path, "provider": provider.name,
        "strategy": strategy, "old": old, "new": new,
        "mode": mode.upper(),
        "ok": False, "ok_experimental": False,
        "classification": None, "reject_reason": None,
        "dimensions": {}, "stages": {},
    }

    def _reject(reason: str) -> Dict:
        report["classification"] = "HONEST_REJECT"
        report["reject_reason"] = reason
        return report

    # 1 · abrir y rasterizar (la imagen ES el documento)
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(dpi=int(DPI), colorspace=pymupdf.csGRAY)
    before = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width).copy()
    page_w_pt, page_h_pt = page.rect.width, page.rect.height
    doc.close()
    img = Image.fromarray(before, "L")

    # 2 · OCR REAL (la única fuente de conocimiento textual) — FC-008:
    #    localización multi-modo sobre el MISMO raster, modos congelados,
    #    matcher intacto, provenance completa. Primario acierta → camino
    #    inalterado. Primario falla → todos los modos restantes + política
    #    de ambigüedad.
    attempts = []           # [{config, found, n_words, ...}]
    hits = []               # [{config, per, obs, page, line}]
    for i, cfg in enumerate(FC008_MODES):
        obs = provider if i == 0 else TesseractOCRProvider(config=cfg)
        page_i = obs.process(img, DPI)
        line_i = page_i.find_line_containing(old)
        per = {"found": line_i is not None, "n_words": len(page_i.words)}
        if line_i is not None:
            b = (min(w.bbox_px[0] for w in line_i),
                 min(w.bbox_px[1] for w in line_i),
                 max(w.bbox_px[2] for w in line_i),
                 max(w.bbox_px[3] for w in line_i))
            per.update({"line_text": " ".join(w.text for w in line_i),
                        "bbox_px": tuple(round(v) for v in b),
                        "mean_conf": round(
                            sum(w.conf for w in line_i) / len(line_i), 1)})
            hits.append({"config": cfg, "bbox_px": per["bbox_px"],
                         "conf": per["mean_conf"], "per": per,
                         "obs": obs, "page": page_i, "line": line_i})
        attempts.append((cfg, per))
        if i == 0 and line_i is not None:
            break            # camino normal: no tocar (T5)
    resolution = _resolve_localization(
        [{"config": h["config"], "text": h["per"]["line_text"],
          "bbox_px": h["bbox_px"], "conf": h["conf"]} for h in hits])
    report["ocr_provenance"] = {
        "raster": {"dpi": int(DPI), "px": (int(img.width), int(img.height))},
        "modes_attempted": [cfg for cfg, _ in attempts],
        "per_mode": {cfg: per for cfg, per in attempts},
        "localizer_config": (resolution["chosen"] or {}).get("config"),
        "selection_reason": resolution["reason"],
        "ambiguity": (resolution.get("incompatible") and
                      {"incompatible_modes": resolution["incompatible"]}) or None,
    }
    if resolution["status"] == "not_found":
        report["stages"]["ocr"] = {"ok": False,
                                   "reason": "texto_no_encontrado_por_ocr",
                                   "n_words": attempts[-1][1]["n_words"]}
        return _reject("texto_no_encontrado_por_ocr")
    if resolution["status"] == "ambiguous":
        report["stages"]["ocr"] = {"ok": False,
                                   "reason": "ocr_localization_ambiguous"}
        return _reject("ocr_localization_ambiguous")
    hit = next(h for h in hits if h["config"] == resolution["chosen"]["config"])
    ocr_page, line = hit["page"], hit["line"]
    localizer_obs, localizer_cfg = hit["obs"], hit["config"]
    report["stages"]["ocr"] = {"ok": True,
                               "n_words": len(ocr_page.words)}

    # FC-006 + FC-008 · verificador independiente del modo localizador:
    # política determinista sobre el conjunto congelado. Mismo motor con
    # config distinta = WEAK (nunca promover a STRONG; NONE jamás PASS).
    if verifier_provider is not None:
        verifier = verifier_provider
    else:
        vcfg = next(c for c in VERIFIER_PREFERENCE if c != localizer_cfg)
        verifier = TesseractOCRProvider(config=vcfg)
    indep = independence_level(localizer_obs, verifier)
    report["verifier_provider"] = verifier.name
    report["ocr_provenance"]["independence"] = {
        "localizer_provider": localizer_obs.name,
        "localizer_config": localizer_cfg,
        "verifier_provider": verifier.name,
        "verifier_config": getattr(verifier, "config", None),
        "independence_level": indep,
    }

    # 3 · px → pt (única vía: geometry)
    t = SpaceTransform(page_w_pt, page_h_pt, dpi=DPI)
    span = build_span_from_ocr(line, t, page_w_pt, 0)
    report["gt_error"] = _measure_gt(gt_pdf, old, span)
    if old not in span["text"]:
        report["stages"]["match"] = {"ok": False,
                                     "ocr_line": span["text"]}
        return _reject("texto_no_en_ocr_line")

    # 4 · PRE-GATES — evidencia runtime, ANTES de cualquier mutación.
    #     Un rechazo aquí no escribe un solo byte del output.
    dims: Dict[str, bool] = {"text_ok": True}
    skew_deg = verifier2.page_skew_deg(ocr_page)
    dims["geometry_ok"] = abs(skew_deg) <= verifier2.SKEW_MAX_DEG
    rect_px = _span_region_px(span)
    structure = verifier2.line_structure_in_region(before, rect_px)
    local_region = before[
        max(0, int(rect_px[1])):min(before.shape[0], int(rect_px[3])),
        max(0, int(rect_px[0])):min(before.shape[1], int(rect_px[2]))
    ]
    v_assessment = verifier2.vertical_structure_assessment(
        local_region=local_region,
        rect_px=rect_px,
        span=span,
        global_img=before,
        ocr_page=ocr_page,
        ocr_provenance=report.get("ocr_provenance"),
    )
    dims["graphics_clearance_ok"] = not structure["has_structure"]
    typo = _typography_gate(ocr_page, line, span)
    dims["typography_ok"] = bool(typo["ok"])
    report["dimensions"] = dims
    report["gates"] = {"page_skew_deg": round(skew_deg, 3),
                       "structure": structure,
                       "vertical_structure_assessment": v_assessment,
                       "typography": typo}
    failed_pre = [d for d, v in dims.items() if not v]
    if failed_pre:
        # escape experimental: SOLO geometría, decidido aquí y al final
        if not (report["mode"] == "EXPERIMENTAL"
                and set(failed_pre) <= {"geometry_ok"}):
            for dim, reason in _REJECT_REASONS:
                if dim in failed_pre:
                    return _reject(reason)
        report["experimental_geom_override"] = True

    # 5 · validar (mismas políticas que born-digital)
    fb = _dummy_fontbook()
    op = ReplaceText(target_span_id=span["id"], old_text=old, new_text=new)
    verdict = validate_replace(op, span, measure=fb.measure, resolve=fb.resolve)
    report["stages"]["validate"] = verdict.as_dict()
    if not verdict.ok:
        return _reject(f"policy:{verdict.policy}")

    # 6 · reparar fondo + 7 · texto determinista
    after = before.copy()
    s = DPI / 72.0
    repair_px = (int(verdict.prefix_end_x_pt * s) - 2,
                 int(span["bbox"][1] * s) - 3,
                 int(span["bbox"][2] * s) + 3,
                 int(span["bbox"][3] * s) + 3)
    after = repair_region(after, repair_px, strategy)
    patch, base_in_patch = render_text_patch(fb, verdict.tail_text,
                                             verdict.final_size_pt)
    insert_x_px = int(verdict.insert_x_pt * s)
    baseline_px = int(span["origin"][1] * s)
    y0 = int(baseline_px - base_in_patch)
    x0 = insert_x_px - int(2 * s)
    # componer solo la tinta (evitar el fondo del parche vectorial)
    ink = patch < 200
    h, w = patch.shape
    ys, xs = np.where(ink)
    if len(xs):
        sub_y0 = max(0, y0 + ys.min())
        sub_y1 = min(after.shape[0], y0 + ys.max() + 1)
        sub_x0 = max(0, x0 + xs.min())
        sub_x1 = min(after.shape[1], x0 + xs.max() + 1)
        region = patch[(sub_y0 - y0):(sub_y1 - y0), (sub_x0 - x0):(sub_x1 - x0)]
        mask = region < 200
        target = after[sub_y0:sub_y1, sub_x0:sub_x1]
        target[mask] = np.minimum(target[mask], 25)   # tinta oscura
    report["stages"]["render"] = {"ok": True, "insert_px": (x0, y0),
                                  "repair_px": repair_px}

    # 8 · exportar PDF (imagen nueva, determinista)
    import io
    out_img = Image.fromarray(after, "L")
    buf = io.BytesIO()
    out_img.save(buf, "PNG")
    nd = pymupdf.open()
    npage = nd.new_page(width=page_w_pt, height=page_h_pt)
    npage.insert_image(npage.rect, stream=buf.getvalue())
    data = _deterministic_id(nd.tobytes(garbage=3, deflate=True))
    nd.close()
    with open(out_pdf, "wb") as f:
        f.write(data)
    report["output_sha256"] = hashlib.sha256(data).hexdigest()
    report["source_sha256"] = sha256_file(pdf_path)

    # 9 · VERIFY 2.1 — readback con el verificador INDEPENDIENTE
    new_region_px = (repair_px[0], repair_px[1],
                     max(repair_px[2], x0 + w), repair_px[3])
    readback = verifier2.ocr_readback(
        verifier, Image.fromarray(after, "L"), new,
        region_px=(verdict.insert_x_pt * s - 20, span["bbox"][1] * s - 10,
                   (verdict.insert_x_pt + verdict.needed_width_pt) * s + 20,
                   span["bbox"][3] * s + 10))
    readback["independence_level"] = indep
    contam = verifier2.pixel_contamination(before, after, new_region_px)
    bgsim = verifier2.background_similarity(after, repair_px)
    report["verify"] = {
        "readback": readback,
        "contamination": contam,
        "background": bgsim,
        "estimated_size_pt": round(span["size"], 2),
        "strategy": verdict.strategy,
        "policy": verdict.policy,
    }
    dims["readback_ok"] = bool(readback["found"]) and indep != "NONE"
    dims["contamination_ok"] = contam["fraction_outside"] <= verifier2.CONTAM_MAX
    dims["background_ok"] = bgsim["score"] >= verifier2.BG_MIN_SCORE

    # 10 · política explícita: ok solo si TODAS las dimensiones pasan
    failed = [d for d, v in dims.items() if not v]
    report["dimensions"] = dims
    if not failed:
        report["ok"] = True
        report["classification"] = "PASS"
    else:
        for dim, reason in _REJECT_REASONS:
            if dim in failed:
                reason = ("readback_no_independiente"
                          if dim == "readback_ok" and indep == "NONE"
                          else ("readback_no_recupera"
                                if dim == "readback_ok" else reason))
                _reject(reason)
                break
        # escape experimental: SOLO geometría, jamás confundible con ok
        # de producción (ok sigue en false; clasificación propia).
        if (report["mode"] == "EXPERIMENTAL"
                and set(failed) <= {"geometry_ok"}):
            report["ok_experimental"] = True
            report["classification"] = "EXPERIMENTAL_PASS"
    return report


def _iou(a, b) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / max(area_a + area_b - inter, 1e-6)

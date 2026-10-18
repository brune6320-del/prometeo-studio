"""
PROMETEO · FASE 0B · BENCHMARK (§22)
────────────────────────────────────
Matriz completa: casos adversariales A–O × estrategias de reparación.
NO esconde fallos: una celda roja aporta más información que diez
demos diseñadas para funcionar. Escribe:
  · assets/raster/benchmark.json   (datos crudos)
  · ../docs/03-fase0b-benchmark.md (tabla legible)
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fixtures_raster
from ocr_provider import JitterOCRProvider, TesseractOCRProvider
from raster import raster_edit
from repair import STRATEGIES

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "..", "docs")

K_NEW = "Alejandro Martinez de los Rios"   # corto → largo (§8 K)
L_OLD, L_NEW = "1.250,00", "OK"            # largo → corto (§8 L)


def run_matrix() -> list:
    data = fixtures_raster.build_all()
    rows = []

    jobs = []
    for case, paths in data.items():
        jobs.append((case, paths, "Perez", "Garcia", None))
    # variantes K y L sobre el scan limpio
    jobs.append(("K_corto_a_largo", data["A_scan_limpio"], "Perez", K_NEW, None))
    jobs.append(("L_largo_a_corto", data["A_scan_limpio"], L_OLD, L_NEW, None))

    for case, paths, old, new, prov in jobs:
        for strategy in STRATEGIES:
            provider = prov
            if case == "J_bbox_imperfecta":
                provider = JitterOCRProvider(TesseractOCRProvider(), sigma_px=3.0)
            out = os.path.join(HERE, "assets", "raster", f"out_{case}_{strategy}.pdf")
            t0 = time.time()
            try:
                rep = raster_edit(paths["pdf"], old, new, out,
                                  provider=provider, strategy=strategy,
                                  gt_pdf=paths["gt_pdf"])
            except Exception as e:
                rep = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            dt = time.time() - t0
            v = rep.get("verify", {})
            rb = v.get("readback", {})
            gt = rep.get("gt_error", {})
            rows.append({
                "case": case, "strategy": strategy, "latency_s": round(dt, 2),
                "ok": rep.get("ok", False),
                "classification": rep.get("classification"),
                "reject_reason": rep.get("reject_reason"),
                "independence": rb.get("independence_level"),
                "readback_cer": (rb.get("best") or {}).get("cer"),
                "readback_found": rb.get("found"),
                "contam_outside": (v.get("contamination", {}) or {}).get("fraction_outside"),
                "bg_score": (v.get("background", {}) or {}).get("score"),
                "bg_mean_diff": (v.get("background", {}) or {}).get("mean_diff"),
                "size_err_pt": gt.get("size_err_pt"),
                "baseline_err_pt": gt.get("baseline_err_pt"),
                "bbox_iou": gt.get("bbox_iou"),
                "error": rep.get("error"),
            })
            print(f"{case:20s} {strategy:6s} {rows[-1]['classification'] or '?':14s} "
                  f"razon={rows[-1]['reject_reason'] or '-'} "
                  f"CER={rows[-1]['readback_cer']} bg={rows[-1]['bg_score']} "
                  f"({dt:.1f}s)", flush=True)
    return rows


def to_markdown(rows: list) -> str:
    def cell(v, good=None, bad=None):
        if v is None:
            return "—"
        if isinstance(v, bool):
            return "✅" if v else "❌"
        if good is not None and v <= good:
            return f"✅ {v}"
        if bad is not None and v >= bad:
            return f"❌ {v}"
        return f"🟡 {v}"

    lines = [
        "# PROMETEO · Fase 0B · Benchmark raster",
        "",
        f"Generado: {time.strftime('%Y-%m-%d %H:%M')} · OCR: Tesseract (real) · "
        "ground truth usado SOLO para medir error, nunca como entrada.",
        "",
        "Política PRE-GATE: ok=true exige 7 dimensiones (texto, geometría, fondo,",
        "contaminación, tipografía, clearance de gráficos, readback independiente).",
        "HONEST_REJECT = rechazo limpio con causa — resultado válido, no fallo.",
        "",
        "| Caso | Estrategia | Clasificación | Razón rechazo | Independ. | CER readback | "
        "Contam. fuera | BG score | err tamaño pt | err baseline pt | IoU bbox | latencia |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        cls = r["classification"] or "CRASH"
        icon = {"PASS": "✅", "HONEST_REJECT": "🟠",
                "EXPERIMENTAL_PASS": "🟣"}.get(cls, "❌")
        lines.append(
            f"| {r['case']} | {r['strategy']} | {icon} {cls} "
            f"| {r['reject_reason'] or '—'} "
            f"| {r['independence'] or '—'} "
            f"| {cell(r['readback_cer'], good=0.05)} "
            f"| {cell(r['contam_outside'], good=0.002)} "
            f"| {cell(r['bg_score'])} "
            f"| {cell(r['size_err_pt'], good=1.0)} "
            f"| {cell(r['baseline_err_pt'], good=2.0)} "
            f"| {cell(r['bbox_iou'])} "
            f"| {r['latency_s']}s |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    rows = run_matrix()
    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(HERE, "assets", "raster", "benchmark.json"), "w") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    with open(os.path.join(DOCS, "03-fase0b-benchmark.md"), "w") as f:
        f.write(to_markdown(rows))
    from collections import Counter
    counts = Counter(r["classification"] or "CRASH" for r in rows)
    reasons = Counter(r["reject_reason"] for r in rows if r["reject_reason"])
    print(f"\n=== {dict(counts)} ===")
    print(f"=== razones de rechazo: {dict(reasons)} ===")
    silent = [r for r in rows if (r["classification"] or "CRASH") == "CRASH"]
    if silent:
        print(f"!!! {len(silent)} CRASH — inspeccionar")
    ok = sum(1 for r in rows if r["ok"])
    print(f"=== ok (PASS) {ok}/{len(rows)} ===")

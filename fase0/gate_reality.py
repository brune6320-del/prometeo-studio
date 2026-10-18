"""
PROMETEO · FASE 1A · HARNESS DEL GATE DE REALIDAD (preparación)
─────────────────────────────────────────────────────────────────
ESTADO: PREPARADO, NO EJECUTADO. El corpus real lo entrega el
usuario; este script NO inventa documentos y un resultado del gate
solo existe si hay manifest con documentos autorizados.

Qué hace cuando exista corpus (por cada objetivo de edición):
  E1 ingest      → hash, clase, páginas
  E2 percepción  → born-digital: rawdict · raster: OCR real
  E3 edición     → pipeline según clase (engine | raster_edit)
  E4 evidencia   → 7 dimensiones + pre-gates (ya endurecidos)
  E5 anotación   → comparación runtime vs ground truth HUMANO
  E6 clasificación → PASS / HONEST_REJECT / CRASH / SILENT_FAILURE

SILENT FAILURE = 0 — definición operativa:
  el pipeline dijo PASS pero (a) la anotación humana discrepa
  (baseline >2pt, tamaño >15%, texto esperado ausente) o (b) la
  valoración visual humana es ≤3/5. Cualquier SILENT_FAILURE
  reprueba el gate, sin importar el resto de números.

Este es un GATE PILOTO (≥20 documentos): responde "¿sobrevive el
núcleo fuera de sus fixtures?", NO valida estadísticamente PROMETEO
para producción. Si pasa, el corpus crece progresivamente.

Modos:
  python gate_reality.py --check          valida manifest + corpus
  python gate_reality.py --run            ejecuta el gate (requiere corpus)
  python gate_reality.py --selfcheck      valida el HARNESS con los
                                          fixtures sintéticos (no es el
                                          gate: solo demuestra el cableado)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(HERE, "reality_corpus")
MANIFEST = os.path.join(CORPUS_DIR, "manifest.json")
ANNOTATIONS = os.path.join(CORPUS_DIR, "annotations.json")
RESULTS_JSON = os.path.join(CORPUS_DIR, "reality_results.json")
RESULTS_MD = os.path.join(HERE, "..", "docs", "06-gate-realidad-resultados.md")

# severidad por clasificación (contexto de evidencia incluido en cada fila)
SEVERITY = {"PASS": 0, "HONEST_REJECT": 1,
            "SILENT_FAILURE": 3, "CRASH": 3}

# tolerancias de la comparación runtime vs anotación humana
ANN_BASELINE_TOL_PT = 2.0
ANN_SIZE_TOL_FRAC = 0.15


def load_manifest(path: str = MANIFEST) -> dict:
    if not os.path.exists(path):
        raise SystemExit(
            f"manifest no encontrado: {path}\n"
            f"Usa reality_corpus/manifest.example.json como plantilla. "
            "El corpus lo entrega el usuario — este harness no inventa "
            "documentos reales.")
    with open(path) as f:
        m = json.load(f)
    problems = []
    for d in m.get("documents", []):
        pdf = os.path.join(CORPUS_DIR, "docs", os.path.basename(d["path"]))
        if not os.path.exists(pdf):
            problems.append(f"documento ausente: {d['path']}")
        if not d.get("authorization"):
            problems.append(f"sin nota de autorización: {d['path']}")
        for t in d.get("targets", []):
            if not t.get("old") or not t.get("new"):
                problems.append(f"target inválido en {d['path']}")
    if problems:
        raise SystemExit("manifest inválido:\n  " + "\n  ".join(problems))
    return m


def run_target(doc: dict, target: dict, annotations: dict | None) -> dict:
    """Una edición → un registro E1–E6. Nunca lanza: todo queda clasificado."""
    import hashlib

    import raster as raster_mod
    from engine import sha256_file
    from raster import raster_edit

    pdf = os.path.join(CORPUS_DIR, "docs", os.path.basename(doc["path"]))
    out = os.path.join(CORPUS_DIR, "out",
                       f"out_{os.path.basename(pdf)}_{target['old'][:8]}.pdf")
    rec = {
        "doc": doc["path"], "class": doc.get("class", "raster"),
        "old": target["old"], "new": target["new"],
        "source_sha256": sha256_file(pdf),
        "t_start": time.time(),
    }
    try:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.exists(out):
            os.remove(out)
        # E3+E4: pipeline endurecido (pre-gates + 7 dimensiones + política)
        rep = raster_edit(pdf, target["old"], target["new"], out,
                          strategy=target.get("strategy", "mean"))
        rec["classification"] = rep["classification"]
        rec["reject_reason"] = rep["reject_reason"]
        rec["dimensions"] = rep["dimensions"]
        rec["gates"] = rep.get("gates", {})
        rec["verify"] = {k: rep["verify"].get(k) for k in
                         ("readback", "contamination", "background")} \
            if "verify" in rep else {}
        rec["output_sha256"] = rep.get("output_sha256")
        rec["output_path"] = out if rep.get("ok") else None
        # E5: anotación humana (fracción del corpus) → SILENT_FAILURE
        ann = (annotations or {}).get(
            f"{os.path.basename(doc['path'])}::{target['old']}")
        if ann and rec["classification"] == "PASS":
            rec["annotation_check"] = _vs_annotation(rep, ann)
            if rec["annotation_check"]["silent_failure"]:
                rec["classification"] = "SILENT_FAILURE"
        if ann and ann.get("visual_score") is not None \
                and rec["classification"] == "PASS" \
                and ann["visual_score"] <= 3:
            rec["classification"] = "SILENT_FAILURE"
            rec["annotation_check"] = {"silent_failure": True,
                                       "cause": "visual_score<=3",
                                       "visual_score": ann["visual_score"]}
    except Exception as e:
        rec["classification"] = "CRASH"
        rec["reject_reason"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc(limit=4)
    rec["severity"] = SEVERITY.get(rec["classification"], 3)
    rec["latency_s"] = round(time.time() - rec["t_start"], 2)
    return rec


def _vs_annotation(rep: dict, ann: dict) -> dict:
    """Runtime dijo PASS: ¿coincide con la anotación humana?
    Es la ÚNICA forma de detectar SILENT_FAILURE dentro del gate."""
    import verifier2
    est = rep["verify"]["readback"]["best"] if rep["verify"].get("readback") else None
    causes = []
    if ann.get("baseline_pt") is not None and est:
        # baseline humano vs readback del verificador (px→pt @300)
        rb_baseline_pt = (est["bbox_px"][3] / (300.0 / 72.0)) * 0.78
        if abs(rb_baseline_pt - ann["baseline_pt"]) > ANN_BASELINE_TOL_PT:
            causes.append("baseline_discrepa")
    if ann.get("size_pt") is not None:
        est_size = rep["verify"].get("estimated_size_pt")
        if est_size and abs(est_size - ann["size_pt"]) / ann["size_pt"] \
                > ANN_SIZE_TOL_FRAC:
            causes.append("size_discrepa")
    if ann.get("expected_text") and est:
        if ann["expected_text"].lower() not in (est.get("text") or "").lower():
            causes.append("texto_discrepa")
    return {"silent_failure": bool(causes), "causes": causes or None}


def aggregate(records: list) -> dict:
    from collections import Counter
    n = len(records)
    c = Counter(r["classification"] for r in records)
    agg = {
        "n_edits": n,
        "PASS": c.get("PASS", 0),
        "HONEST_REJECT": c.get("HONEST_REJECT", 0),
        "SILENT_FAILURE": c.get("SILENT_FAILURE", 0),
        "CRASH": c.get("CRASH", 0),
        "honest_reject_reasons": dict(Counter(
            r["reject_reason"] for r in records
            if r["classification"] == "HONEST_REJECT")),
        "gate_verdict": None,
        "scope": "PILOTO (≥20 docs) — NO es validación estadística "
                 "de producción; responde si el núcleo sobrevive fuera "
                 "de sus fixtures.",
    }
    if n:
        silent = agg["SILENT_FAILURE"] + agg["CRASH"]
        agg["gate_verdict"] = (
            "APROBADO" if silent == 0 and agg["PASS"] / n >= 0.70
            else "REPROBADO")
    return agg


def to_markdown(agg: dict, records: list) -> str:
    lines = [
        "# PROMETEO · Gate de Realidad · Resultados",
        "",
        f"Generado: {time.strftime('%Y-%m-%d %H:%M')} · "
        f"Ámbito: {agg['scope']}",
        "",
        f"**VEREDICTO: {agg['gate_verdict']}** · "
        f"ediciones={agg['n_edits']} · PASS={agg['PASS']} · "
        f"HONEST_REJECT={agg['HONEST_REJECT']} · "
        f"SILENT_FAILURE={agg['SILENT_FAILURE']} · CRASH={agg['CRASH']}",
        "",
        "SILENT_FAILURE=0 es condición necesaria; PASS≥70 % la otra. "
        "Un rechazo honesto con causa es un resultado válido.",
        "",
        "| doc | clase | old→new | clasificación | razón | severidad | "
        "evidencia (skew° / CER / bg / lat) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in records:
        g = r.get("gates") or {}
        v = r.get("verify") or {}
        rb = (v.get("readback") or {}).get("best") or {}
        ev = (f"{g.get('page_skew_deg', '—')} / {rb.get('cer', '—')} / "
              f"{(v.get('background') or {}).get('score', '—')} / "
              f"{r.get('latency_s', '—')}s")
        lines.append(
            f"| {os.path.basename(r['doc'])} | {r['class']} | "
            f"{r['old']}→{r['new']} | {r['classification']} | "
            f"{r.get('reject_reason') or '—'} | {r['severity']} | {ev} |")
    return "\n".join(lines) + "\n"


def run_gate() -> None:
    manifest = load_manifest()
    annotations = None
    if os.path.exists(ANNOTATIONS):
        with open(ANNOTATIONS) as f:
            annotations = json.load(f).get("annotations")
    records = []
    for doc in manifest["documents"]:
        for target in doc.get("targets", []):
            records.append(run_target(doc, target, annotations))
            r = records[-1]
            print(f"{os.path.basename(doc['path']):28s} "
                  f"{target['old'][:14]:14s} → {r['classification']}"
                  f"{' / ' + str(r.get('reject_reason')) if r.get('reject_reason') else ''}",
                  flush=True)
    agg = aggregate(records)
    with open(RESULTS_JSON, "w") as f:
        json.dump({"aggregate": agg, "records": records}, f,
                  indent=1, ensure_ascii=False)
    os.makedirs(os.path.dirname(RESULTS_MD), exist_ok=True)
    with open(RESULTS_MD, "w") as f:
        f.write(to_markdown(agg, records))
    print("\n" + json.dumps(agg, indent=2, ensure_ascii=False))
    print(f"\n→ {RESULTS_JSON}\n→ {RESULTS_MD}")


def selfcheck() -> None:
    """Valida el CABLEADO del harness con fixtures sintéticos.
    NO es el gate: demuestra que las cuatro clasificaciones se
    producen correctamente antes de tocar un documento real."""
    import fixtures_raster
    data = fixtures_raster.build_all()
    out_dir = os.path.join(CORPUS_DIR, "out")
    os.makedirs(out_dir, exist_ok=True)
    from raster import raster_edit

    cases = [
        ("A_scan_limpio", "Perez", "Garcia", "PASS", None),
        ("M_rotacion_4", "Perez", "Garcia", "HONEST_REJECT", "page_skew"),
        ("G2_linea_cruza", "Perez", "Garcia", "HONEST_REJECT",
         "grafico_en_region"),
        ("F_perspectiva", "Perez", "Garcia", "HONEST_REJECT",
         "texto_no_encontrado_por_ocr"),
    ]
    ok = True
    for case, old, new, want_cls, want_reason in cases:
        out = os.path.join(out_dir, f"selfcheck_{case}.pdf")
        rep = raster_edit(data[case]["pdf"], old, new, out)
        got = rep["classification"]
        got_r = rep.get("reject_reason")
        good = got == want_cls and (want_reason is None or got_r == want_reason)
        ok &= good
        print(f"  {case:20s} {got:14s} {got_r or '-':28s} "
              f"{'✓' if good else f'✗ esperaba {want_cls}/{want_reason}'}")
    # clasificación SILENT_FAILURE via anotación discordante
    rep = raster_edit(data["A_scan_limpio"]["pdf"], "Perez", "Garcia",
                      os.path.join(out_dir, "selfcheck_ann.pdf"))
    ann = {"expected_text": "TEXTO_QUE_NO_ESTA",
           "baseline_pt": 110.0, "size_pt": 11.0}
    chk = _vs_annotation(rep, ann)
    silent_ok = chk["silent_failure"] and "texto_discrepa" in chk["causes"]
    ok &= silent_ok
    print(f"  anotación discordante → silent_failure={chk['silent_failure']} "
          f"causas={chk['causes']} {'✓' if silent_ok else '✗'}")
    print("HARNESS " + ("OK — listo para el corpus real" if ok
                        else "FALLA — no ejecutar el gate"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        selfcheck()
    elif a.run:
        run_gate()
    else:
        load_manifest()   # --check (o uso sin argumentos)
        print("manifest válido — usa --run para ejecutar el gate")

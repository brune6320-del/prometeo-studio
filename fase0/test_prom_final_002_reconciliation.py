"""PROMETEO · PROM-FINAL-002 · custodia de la evidencia externa de Colab (C02/C03A/C03B).

Re-ejecuta el verificador independiente sin escribir nada y fija el estado terminal:
cualquier cambio en los bundles ingeridos, en AG277 RUN_001 o en la decisión rompe esta prueba.
"""

import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "fase0", "colab"))

import prom_final_002_reconcile as reconcile  # noqa: E402

AUDIT = os.path.join(REPO_ROOT, "fase0", "reality_corpus", "colab_returns",
                     "PROM_FINAL_002_RECONCILIATION_AUDIT.json")


def test_reconciliation_all_checks_pass_without_writing():
    audit = reconcile.main(write_audit=False)
    assert audit["checks_failed"] == [], audit["checks_failed"]
    assert audit["checks_total"] >= 142


def test_terminal_state_is_no_selection():
    audit = reconcile.main(write_audit=False)
    assert audit["PROM-C03B"]["recomputed_decision"] == "NO_SELECTION"
    assert audit["PROM-C03B"]["absolute_adequacy"] == {
        "QWEN3_VL_4B_INSTRUCT": "FAIL", "QWEN3_VL_8B_INSTRUCT_QUANTIZED": "FAIL"}
    assert audit["terminal"]["PROPOSED_SUCCESSOR_ASSESSOR_CONFIGURATION"] == "NONE"
    assert audit["PROM-C02"]["recomputed_decision"] == "SELECT_4B_BF16"
    assert audit["PROM-C03A"]["authority"] == "DIAGNOSTIC_ONLY_NO_MODEL_SELECTION_AUTHORITY"


def test_committed_audit_matches_fresh_recomputation():
    fresh = reconcile.main(write_audit=False)
    with open(AUDIT, encoding="utf-8") as f:
        committed = json.load(f)
    assert json.loads(json.dumps(fresh, ensure_ascii=False)) == committed


def test_ag277_run_001_untouched():
    audit = reconcile.main(write_audit=False)
    run = audit["AG277_RUN_001"]
    assert run["next_ordinal"] == 4
    assert run["assessors"] == ["MLX_VLM_QWEN2_VL_2B_INSTRUCT_4BIT"]
    assert len(run["results"]) == 3


def test_final_evidence_index_hashes():
    """Cada artefacto inmutable del índice existe y conserva su hash; los LOCAL_ONLY se
    comprueban solo si están en este disco; los LIVING pueden evolucionar tras el tag."""
    import hashlib
    with open(os.path.join(REPO_ROOT, "PROMETEO_FINAL_EVIDENCE_INDEX.json"), encoding="utf-8") as f:
        index = json.load(f)
    assert index["final_verdict"] == "PROMETEO_CANONICAL_CAMPAIGN_CLOSED"
    checked = 0
    for claim in index["claims"]:
        for art in claim["artifacts"]:
            path = os.path.join(REPO_ROOT, art["path"])
            if art["custody"] == "GIT_TRACKED_LIVING":
                continue
            if art["custody"] == "LOCAL_ONLY_GITIGNORED" and not os.path.exists(path):
                continue
            with open(path, "rb") as fh:
                assert hashlib.sha256(fh.read()).hexdigest() == art["sha256"], art["path"]
            checked += 1
    assert checked >= 58

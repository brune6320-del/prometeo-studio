"""PROMETEO PROM-C02 Full Selection Suite Acceptance Tests.
Validates the entire blind balanced multi-role synthetic assessor selection suite:
- Fixture count, distribution, balance, neutral naming, and zero leakage
- Container & pixel hash integrity and zero overlap with PROM-C01
- Answer key isolation and cryptographic suite freeze
- Majority aggregation, macro-F1, confusion matrix, and repeatability
- Eligibility gates, 0.03 margin, tiebreaker, and authority boundary
- AG277 custody and immutability invariants
"""

import hashlib
import json
import os
import re
import unittest

from fase0.colab.prom_c02.audit_leakage import audit_prom_c02_suite
from fase0.colab.prom_c02.prom_c02_diagnostics import (
    compute_bootstrap_delta_ci,
    compute_paired_comparison,
)
from fase0.colab.prom_c02.prom_c02_scorer import (
    aggregate_fixture_prediction,
    compute_model_metrics,
)
from fase0.colab.prom_c02.prom_c02_selection_gate import (
    apply_selection_decision_rule,
    evaluate_candidate_eligibility,
)
from fase0.colab.prom_c02.schema_validator import (
    validate_evaluation_result,
    validate_inference_result,
    validate_selection_decision,
)


class TestPromC02SelectionSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.prom_c02_dir = os.path.join(cls.repo_root, "fase0", "colab", "prom_c02")
        cls.fixtures_dir = os.path.join(cls.prom_c02_dir, "fixtures")
        cls.manifest_path = os.path.join(cls.prom_c02_dir, "PROM_C02_SUITE_MANIFEST_v0.1.json")
        cls.answer_key_path = os.path.join(cls.prom_c02_dir, "PROM_C02_ANSWER_KEY_v0.1.json")
        cls.prompt_path = os.path.join(cls.prom_c02_dir, "PROM_C02_PROMPT_v0.1.json")
        cls.policy_path = os.path.join(cls.prom_c02_dir, "PROM_C02_SELECTION_POLICY_v0.1.json")
        cls.protocol_path = os.path.join(cls.prom_c02_dir, "PROM_C02_SELECTION_PROTOCOL_v0.1.json")
        cls.registry_path = os.path.join(cls.prom_c02_dir, "PROM_C02_CANDIDATE_REGISTRY_v0.1.json")
        cls.notebook_path = os.path.join(cls.prom_c02_dir, "prometeo_prom_c02_selection_benchmark.ipynb")

        with open(cls.manifest_path, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)
        with open(cls.answer_key_path, "r", encoding="utf-8") as f:
            cls.answer_key_data = json.load(f)
        with open(cls.policy_path, "r", encoding="utf-8") as f:
            cls.policy = json.load(f)
        with open(cls.protocol_path, "r", encoding="utf-8") as f:
            cls.protocol = json.load(f)

    # 1. Fixture Count, Balance, and Neutral Naming
    def test_fixture_count_and_balance(self):
        fixtures = self.manifest["fixtures"]
        self.assertEqual(len(fixtures), 54, "Must have exactly 54 fixtures in manifest")

        # Verify disk presence
        disk_files = [f for f in os.listdir(self.fixtures_dir) if f.endswith(".png")]
        self.assertEqual(len(disk_files), 54, "Must have exactly 54 PNG fixture files on disk")

        # Verify neutral naming
        for idx, item in enumerate(fixtures, start=1):
            expected_id = f"F{idx:03d}"
            expected_fn = f"F{idx:03d}.png"
            self.assertEqual(item["fixture_id"], expected_id)
            self.assertEqual(item["filename"], expected_fn)
            self.assertRegex(item["filename"], r"^F\d{3}\.png$", "Filename must be strictly neutral Fxxx.png")

        # Verify balance across roles and difficulties from answer key
        ak = self.answer_key_data["answer_key"]
        self.assertEqual(len(ak), 54)
        role_counts = {}
        role_diff_counts = {}

        for fid, item in ak.items():
            r = item["role"]
            d = item["difficulty"]
            role_counts[r] = role_counts.get(r, 0) + 1
            pair = (r, d)
            role_diff_counts[pair] = role_diff_counts.get(pair, 0) + 1

        self.assertEqual(len(role_counts), 9, "Must have exactly 9 unique roles")
        for r, cnt in role_counts.items():
            self.assertEqual(cnt, 6, f"Role {r} must have exactly 6 fixtures")
            for diff in ["BASIC", "INTERMEDIATE", "ADVERSARIAL"]:
                c_diff = role_diff_counts.get((r, diff), 0)
                self.assertEqual(c_diff, 2, f"Role {r} with difficulty {diff} must have exactly 2 fixtures")

    # 2. Cryptographic Integrity and Zero Hash Duplicates
    def test_fixture_hashes_and_zero_leakage(self):
        png_hashes = set()
        pixel_hashes = set()

        for item in self.manifest["fixtures"]:
            fn = item["filename"]
            fp = os.path.join(self.fixtures_dir, fn)
            with open(fp, "rb") as f:
                raw = f.read()
            h = hashlib.sha256(raw).hexdigest()
            self.assertEqual(h, item["png_sha256"], f"Container hash mismatch for {fn}")

            png_hashes.add(h)
            pixel_hashes.add(item["pixel_content_sha256"])

        self.assertEqual(len(png_hashes), 54, "All 54 PNG container hashes must be strictly unique")
        self.assertEqual(len(pixel_hashes), 54, "All 54 pixel content hashes must be strictly unique")

    # 3. PROM-C01 Fixture Exclusion
    def test_prom_c01_fixture_exclusion(self):
        prom_c01_png_sha = "9d533446059d04bc09971ce9745e4334346ebaa41076f8745d24b6f125a2df60"
        prom_c01_pixel_sha = "4443f55cca72b3cd29b70e0194d181066c4447f889c256bcc0f70a6e809213aa"

        for item in self.manifest["fixtures"]:
            self.assertNotEqual(item["png_sha256"], prom_c01_png_sha, f"Fixture {item['filename']} matches PROM-C01 PNG hash")
            self.assertNotEqual(item["pixel_content_sha256"], prom_c01_pixel_sha, f"Fixture {item['filename']} matches PROM-C01 pixel hash")

        self.assertEqual(self.protocol["custody_invariants"]["prom_c01_fixture_status"], "SMOKE_TEST_ONLY_EXCLUDED")

    # 4. Answer Key Isolation
    def test_answer_key_isolation(self):
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest_raw = f.read()
        self.assertNotIn("ground_truth_role", manifest_raw, "Answer key leaked in manifest")
        self.assertNotIn("expected_role", manifest_raw, "Answer key leaked in manifest")

        with open(self.prompt_path, "r", encoding="utf-8") as f:
            prompt_raw = f.read()
        self.assertNotIn("answer_key", prompt_raw, "Answer key token in prompt")
        self.assertNotIn("expected_role", prompt_raw, "Answer key token in prompt")

        # Verify notebook Phase A does not contain answer key
        with open(self.notebook_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
        code_cells = [c for c in nb.get("cells", []) if c.get("cell_type") == "code"]
        phase_a_code = "".join("".join(c.get("source", [])) for c in code_cells[:5])
        self.assertNotIn("FROZEN_ANSWER_KEY", phase_a_code, "Answer key leaked in Phase A cells")

    # 5. Cryptographic Suite Freeze
    def test_frozen_suite_digests(self):
        frozen = self.protocol["frozen_digests"]

        def get_sha(p):
            with open(p, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(get_sha(self.manifest_path), frozen["suite_manifest_sha256"])
        self.assertEqual(get_sha(self.answer_key_path), frozen["answer_key_sha256"])
        self.assertEqual(get_sha(self.prompt_path), frozen["prompt_sha256"])
        self.assertEqual(get_sha(self.policy_path), frozen["selection_policy_sha256"])
        self.assertEqual(get_sha(self.registry_path), frozen["candidate_registry_sha256"])
        self.assertEqual(get_sha(self.notebook_path), frozen["notebook_sha256"])

        # Fixture digest set
        fix_hashes = sorted([f["png_sha256"] for f in self.manifest["fixtures"]])
        digest_set = hashlib.sha256("".join(fix_hashes).encode("utf-8")).hexdigest()
        self.assertEqual(digest_set, frozen["fixture_digest_set_sha256"])

    # 6. Scoring Engine & Majority Voting
    def test_majority_voting_and_repeatability(self):
        # 3/3 unanimous
        runs_3_3 = [
            {"role": "LINEAR_DIVIDER_ROLE", "confidence": "HIGH"},
            {"role": "LINEAR_DIVIDER_ROLE", "confidence": "HIGH"},
            {"role": "LINEAR_DIVIDER_ROLE", "confidence": "HIGH"}
        ]
        agg_3_3 = aggregate_fixture_prediction(runs_3_3)
        self.assertEqual(agg_3_3["canonical_prediction"], "LINEAR_DIVIDER_ROLE")
        self.assertTrue(agg_3_3["is_unanimous"])
        self.assertEqual(agg_3_3["status"], "CONSENSUS_UNANIMOUS")

        # 2/3 majority
        runs_2_3 = [
            {"role": "LINEAR_DIVIDER_ROLE", "confidence": "HIGH"},
            {"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "MEDIUM"},
            {"role": "LINEAR_DIVIDER_ROLE", "confidence": "MEDIUM"}
        ]
        agg_2_3 = aggregate_fixture_prediction(runs_2_3)
        self.assertEqual(agg_2_3["canonical_prediction"], "LINEAR_DIVIDER_ROLE")
        self.assertFalse(agg_2_3["is_unanimous"])
        self.assertEqual(agg_2_3["status"], "CONSENSUS_MAJORITY_2_OF_3")

        # 1/1/1 repeatability failure
        runs_1_1_1 = [
            {"role": "LINEAR_DIVIDER_ROLE", "confidence": "LOW"},
            {"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "LOW"},
            {"role": "TABLE_GRID_ROLE", "confidence": "LOW"}
        ]
        agg_1_1_1 = aggregate_fixture_prediction(runs_1_1_1)
        self.assertIsNone(agg_1_1_1["canonical_prediction"])
        self.assertFalse(agg_1_1_1["is_unanimous"])
        self.assertEqual(agg_1_1_1["status"], "REPEATABILITY_FAILURE")

    def test_macro_f1_and_confusion_matrix(self):
        ak = self.answer_key_data["answer_key"]
        # Perfect predictions
        perfect_preds = {fid: item["role"] for fid, item in ak.items()}
        perf_metrics = compute_model_metrics(perfect_preds, ak)
        self.assertEqual(perf_metrics["accuracy"], 1.0)
        self.assertEqual(perf_metrics["macro_f1"], 1.0)
        self.assertEqual(perf_metrics["macro_precision"], 1.0)
        self.assertEqual(perf_metrics["macro_recall"], 1.0)

        # Check confusion matrix dimensions
        cm = perf_metrics["confusion_matrix"]
        self.assertEqual(len(cm), 9)
        for row in cm:
            self.assertEqual(len(row), 9)
        # All off-diagonal elements 0
        for i in range(9):
            for j in range(9):
                if i == j:
                    self.assertEqual(cm[i][j], 6)
                else:
                    self.assertEqual(cm[i][j], 0)

    # 7. Selection Margin and Decision Rules
    def test_selection_decision_gate(self):
        margin = 0.03

        # Base summaries
        base_a = {
            "live_execution_success": 1.0,
            "strict_json_valid_rate": 1.0,
            "fixture_prediction_repeatability": 1.0,
            "unknown_roles_count": 0,
            "answer_key_exposed": False,
            "real_corpus_exposed": False,
            "semantic_metrics": {"macro_f1": 0.80}
        }
        base_b = {
            "live_execution_success": 1.0,
            "strict_json_valid_rate": 1.0,
            "fixture_prediction_repeatability": 1.0,
            "unknown_roles_count": 0,
            "answer_key_exposed": False,
            "real_corpus_exposed": False,
            "semantic_metrics": {"macro_f1": 0.80}
        }

        # Case 1: Equivalence (delta = 0.00 <= 0.03) -> selects 4B (tiebreaker)
        res = apply_selection_decision_rule(base_a, base_b, margin=margin)
        self.assertEqual(res["decision"], "SELECT_4B_BF16")
        self.assertTrue(res["tiebreaker_applied"])
        self.assertEqual(res["proposed_successor_assessor_configuration"], "QWEN3_VL_4B_INSTRUCT")

        # Case 2: Near equivalence (delta = +0.02 <= 0.03) -> selects 4B (tiebreaker)
        b_plus_2 = dict(base_b, semantic_metrics={"macro_f1": 0.82})
        res = apply_selection_decision_rule(base_a, b_plus_2, margin=margin)
        self.assertEqual(res["decision"], "SELECT_4B_BF16")
        self.assertTrue(res["tiebreaker_applied"])

        # Case 3: Significant 8B advantage (delta = +0.05 > 0.03) -> selects 8B
        b_plus_5 = dict(base_b, semantic_metrics={"macro_f1": 0.85})
        res = apply_selection_decision_rule(base_a, b_plus_5, margin=margin)
        self.assertEqual(res["decision"], "SELECT_8B_INT4")
        self.assertFalse(res["tiebreaker_applied"])
        self.assertEqual(res["proposed_successor_assessor_configuration"], "QWEN3_VL_8B_INSTRUCT_QUANTIZED")

        # Case 4: Significant 4B advantage (delta = -0.05 < -0.03) -> selects 4B
        b_minus_5 = dict(base_b, semantic_metrics={"macro_f1": 0.75})
        res = apply_selection_decision_rule(base_a, b_minus_5, margin=margin)
        self.assertEqual(res["decision"], "SELECT_4B_BF16")
        self.assertFalse(res["tiebreaker_applied"])

        # Case 5: 8B disqualified (e.g., repeatability < 0.95) -> selects 4B
        b_disq = dict(base_b, fixture_prediction_repeatability=0.90, semantic_metrics={"macro_f1": 0.95})
        res = apply_selection_decision_rule(base_a, b_disq, margin=margin)
        self.assertEqual(res["decision"], "SELECT_4B_BF16")
        self.assertFalse(res["candidate_b_eligible"])

        # Case 6: 4B disqualified -> selects 8B
        a_disq = dict(base_a, strict_json_valid_rate=0.95)
        res = apply_selection_decision_rule(a_disq, base_b, margin=margin)
        self.assertEqual(res["decision"], "SELECT_8B_INT4")
        self.assertFalse(res["candidate_a_eligible"])

        # Case 7: Both disqualified -> NO_SELECTION
        res = apply_selection_decision_rule(a_disq, b_disq, margin=margin)
        self.assertEqual(res["decision"], "NO_SELECTION")
        self.assertIsNone(res["proposed_successor_assessor_configuration"])

        # Authority boundary verified
        self.assertIn("Does NOT mutate AG277", res["authority_boundary_statement"])

    # 8. Anti-Leakage Audit
    def test_anti_leakage_audit(self):
        valid, errs = audit_prom_c02_suite(self.prom_c02_dir)
        self.assertTrue(valid, f"Anti-leakage audit failed: {errs}")

    # 9. AG277 Immutability and Ledger Custody
    def test_ag277_immutability(self):
        run_dir = os.path.join(self.repo_root, "fase0", "reality_corpus", "pass_b_runs", "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001")
        results_dir = os.path.join(run_dir, "results")
        h1 = "fb52d296fb0f756b8a8af1c2ac5c2a155a5c9aed24d45ca9546f2f8820d1f7b6"
        h2 = "88e9f15779c74a1209e6b249cc63c5df9d75b5247952c30dd8d3549a4ca249ae"
        h3 = "71e0ef96507d30ca255dc8625f13ae70defe50d99741d5159b0f1e1910c6b126"

        def get_sha(fname):
            p = os.path.join(results_dir, fname)
            with open(p, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(get_sha("00001.json"), h1, "AG277 context 1 mutated!")
        self.assertEqual(get_sha("00002.json"), h2, "AG277 context 2 mutated!")
        self.assertEqual(get_sha("00003.json"), h3, "AG277 context 3 mutated!")

        # Verify next ordinal is 4 and 00004.json does NOT exist
        self.assertFalse(os.path.exists(os.path.join(results_dir, "00004.json")), "00004.json must not exist")

        # Ledger check
        ledger_path = os.path.join(run_dir, "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001_DERIVED_LEDGER.jsonl")
        with open(ledger_path, "r", encoding="utf-8") as f:
            ledger_lines = [l for l in f.read().splitlines() if l.strip()]
        self.assertEqual(len(ledger_lines), 3, "AG277 context ledger must contain exactly 3 lines")

        # Active PASS B processes check: must be 0
        import subprocess
        ps_out = subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout
        pass_b_procs = [l for l in ps_out.splitlines() if "execute_pass_b_canonical" in l and "grep" not in l]
        self.assertEqual(len(pass_b_procs), 0, "No active PASS B processes allowed")


if __name__ == "__main__":
    unittest.main()

"""
Post-Execution Custody Verification Suite for FC-009 Stage 3B-2D1B2C1D.
Strictly non-corpus: audits only frozen evidence, hashes, and source immutability.
"""

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Frozen evidence paths
B2C1D_JOURNAL_PATH = REPO_ROOT / "fase0/reality_corpus/FC009_STAGE3B2D1B2C1D_DEV002_RECOVERY_RAW_JOURNAL.jsonl"
B2C1D_RESULTS_PATH = REPO_ROOT / "fase0/reality_corpus/FC009_STAGE3B2D1B2C1D_DEV002_RECOVERY_RAW_RESULTS.json"
B2C1D_RECEIPT_PATH = REPO_ROOT / "fase0/reality_corpus/FC009_STAGE3B2D1B2C1D_DEV002_RECOVERY_EXECUTION_RECEIPT.json"
B2C1D_AUDIT_PATH = REPO_ROOT / "fase0/reality_corpus/FC009_STAGE3B2D1B2C1D_DEV002_RECOVERY_EXECUTION_AUDIT.json"

# Expected B2C1D hashes
FROZEN_B2C1D_JOURNAL_SHA256 = "eb49fc76904067fb4a8d00c3aa5364bae7c51ef9a45fea4ae0c26b9ce48bb62b"
FROZEN_B2C1D_RESULTS_SHA256 = "5d69adb84fc07184465506abed31e0c0379067590efdbd92d5e1df838badf904"
FROZEN_B2C1D_RECEIPT_SHA256 = "7ecc8e9852f91877e6afaf63288647454641857372171ca4b428b6d677ad926c"
FROZEN_B2C1D_AUDIT_SHA256 = "13a9b145a0fee6e76ebe33485e121584fe552fba34057547507267261eff7504"

# Historical B2C1A names
B2C1A_FILENAMES = {
    "FC009_STAGE3B2D1B2C1_DEV002_RAW_JOURNAL.jsonl",
    "FC009_STAGE3B2D1B2C1_DEV002_RAW_RESULTS.json",
    "FC009_STAGE3B2D1B2C1_DEV002_EXECUTION_RECEIPT.json",
}

# Historical B2C1A hashes
FROZEN_B2C1A_JOURNAL_SHA256 = "7ce586bd1dd0e2a14954341639382ea88fbac4ed105affbfc79e3630683cfbba"
FROZEN_B2C1A_RESULTS_SHA256 = "5d75bb1aa858e79a07c2832818412bf48598a26ecd11717089901d3076fcac14"
FROZEN_B2C1A_RECEIPT_SHA256 = "43339e6f6daa1ea269e2c6250f735e6db849a64b6762633bb91075c47f1f7489"
FROZEN_B2C1A_AUDIT_SHA256 = "b3ca3d408bb7d8484f324ad64ddfa1984ae82e8d027dd79c91865b448ac1e146"
FROZEN_B2C1B_AUDIT_SHA256 = "27fd0ae3224a6fb4e97cd8b7af8de3c65a512d4075880fd3db45bc2ee618802d"

# Frozen source hashes
FROZEN_SUCCESSOR_BINDING_SHA256 = "410e6f8800019b7f9213b512bc20fed91d230bc31dd0ba951b0609086d7e9c0d"
FROZEN_SUCCESSOR_RUNNER_SHA256 = "0a3d929193aee2e96b840f9d5495607986b2785eddc08018b9390b0e56468892"
FROZEN_PACKET_BUILDER_SHA256 = "d80daf0ac03c355cbca7044ea9b653b4a9ffa1ab37ec037c111ef33cfc06af7f"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


# ── TEST 1: RECOVERY OUTPUTS EXISTENCE ─────────────────────────────────────────


def test_b2c1d_recovery_outputs_exist():
    """Requirement 1: All three B2C1D recovery outputs must exist post-execution."""
    assert B2C1D_JOURNAL_PATH.exists(), f"Missing {B2C1D_JOURNAL_PATH}"
    assert B2C1D_RESULTS_PATH.exists(), f"Missing {B2C1D_RESULTS_PATH}"
    assert B2C1D_RECEIPT_PATH.exists(), f"Missing {B2C1D_RECEIPT_PATH}"
    assert B2C1D_AUDIT_PATH.exists(), f"Missing {B2C1D_AUDIT_PATH}"


# ── TEST 2: OUTPUT PATHS DIFFER FROM B2C1A ─────────────────────────────────────


def test_b2c1d_output_paths_differ_from_b2c1a():
    """Requirement 2: B2C1D recovery output names must not collide with B2C1A raw outputs."""
    assert B2C1D_JOURNAL_PATH.name not in B2C1A_FILENAMES
    assert B2C1D_RESULTS_PATH.name not in B2C1A_FILENAMES
    assert B2C1D_RECEIPT_PATH.name not in B2C1A_FILENAMES

    assert "STAGE3B2D1B2C1D" in B2C1D_JOURNAL_PATH.name
    assert "STAGE3B2D1B2C1D" in B2C1D_RESULTS_PATH.name
    assert "STAGE3B2D1B2C1D" in B2C1D_RECEIPT_PATH.name


# ── TEST 3: RECOVERY OUTPUT HASHES ────────────────────────────────────────────


def test_b2c1d_output_hashes_match_frozen():
    """Requirement 3: B2C1D output hashes must match the frozen canonical values."""
    assert _sha256_file(B2C1D_JOURNAL_PATH) == FROZEN_B2C1D_JOURNAL_SHA256
    assert _sha256_file(B2C1D_RESULTS_PATH) == FROZEN_B2C1D_RESULTS_SHA256
    assert _sha256_file(B2C1D_RECEIPT_PATH) == FROZEN_B2C1D_RECEIPT_SHA256
    assert _sha256_file(B2C1D_AUDIT_PATH) == FROZEN_B2C1D_AUDIT_SHA256


# ── TEST 4: JOURNAL ENTRY COUNT AND ORDINALS ───────────────────────────────────


def test_recovery_journal_entries_and_ordinals():
    """Requirements 4, 5, 6: Journal must contain 176 entries with continuous ordinals 0..175 and no duplicates."""
    entries = []
    with open(B2C1D_JOURNAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    assert len(entries) == 176, f"Expected 176 journal entries, got {len(entries)}"

    ordinals = [e["execution_ordinal"] for e in entries]
    assert ordinals == list(range(176)), "Execution ordinals must be strictly 0..175"
    assert len(set(ordinals)) == 176, "Duplicate execution ordinals detected"

    for e in entries:
        assert e["technical_status"] == "TECHNICAL_EXECUTION_SUCCESS"
        assert e["m2_observation_status"] == "SUCCESS"
        assert e["m3_observation_status"] == "SUCCESS"
        assert e["packet_build_status"] == "SUCCESS"
        assert e["candidate_execution_status"] == "SUCCESS"
        assert e["exception"] is None


# ── TEST 5: RECEIPT STATUS ────────────────────────────────────────────────────


def test_recovery_receipt_reports_success():
    """Requirement 7: Execution receipt must record completed recovery with zero failures."""
    with open(B2C1D_RECEIPT_PATH, "r", encoding="utf-8") as f:
        receipt = json.load(f)

    assert receipt["stage"] == "Stage3B-2D1B2C1D"
    assert receipt["candidate_version"] == "H3DV2_DEV_002"
    assert receipt["status"] == "COMPLETED"
    assert receipt["total_attempted"] == 176
    assert receipt["successful_executions"] == 176
    assert receipt["technical_failures"] == 0
    assert receipt["journal_sha256"] == FROZEN_B2C1D_JOURNAL_SHA256
    assert receipt["results_sha256"] == FROZEN_B2C1D_RESULTS_SHA256


# ── TEST 6: RESULTS RECORD COUNT ──────────────────────────────────────────────


def test_recovery_results_record_count():
    """Requirement 8: Raw results file must contain exactly 176 evaluated records."""
    with open(B2C1D_RESULTS_PATH, "r", encoding="utf-8") as f:
        results = json.load(f)

    assert results["stage"] == "Stage3B-2D1B2C1D"
    assert results["candidate_version"] == "H3DV2_DEV_002"
    assert results["total_records_executed"] == 176
    assert results["technical_failure_count"] == 0
    assert len(results["raw_results"]) == 176

    ordinals = [r["execution_ordinal"] for r in results["raw_results"]]
    assert ordinals == list(range(176))


# ── TEST 7: LABEL ISOLATION AND FORBIDDEN FIELDS ──────────────────────────────


def test_label_isolation_and_no_leak_fields():
    """Requirements 9, 10: Raw evidence must contain zero label references or scoring fields."""
    forbidden = ["safe", "unsafe", "ground_truth", "groundtruth", "semantic_template", "scoring", "forensic_map"]

    def _scan(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                k_lower = str(k).lower()
                for term in forbidden:
                    assert term not in k_lower, f"Forbidden term '{term}' in key {path}.{k}"
                _scan(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                _scan(item, f"{path}[{idx}]")

    with open(B2C1D_RECEIPT_PATH, "r", encoding="utf-8") as f:
        _scan(json.load(f), "receipt")

    with open(B2C1D_RESULTS_PATH, "r", encoding="utf-8") as f:
        _scan(json.load(f), "results")

    with open(B2C1D_JOURNAL_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if line.strip():
                _scan(json.loads(line), f"journal_line_{idx}")


# ── TEST 8: SUCCESSOR CODE INTEGRITY ──────────────────────────────────────────


def test_successor_binding_and_runner_hashes_frozen():
    """Requirements 11, 12: Successor observer binding and runner must remain frozen."""
    binding_path = REPO_ROOT / "fase0/experiments/h3dv2_dev_002/integration/observer_bindings_b2c1c.py"
    runner_path = REPO_ROOT / "fase0/experiments/h3dv2_dev_002/integration/run_dev002_integration_b2c1c.py"

    assert _sha256_file(binding_path) == FROZEN_SUCCESSOR_BINDING_SHA256
    assert _sha256_file(runner_path) == FROZEN_SUCCESSOR_RUNNER_SHA256


# ── TEST 9: PACKET BUILDER AND RUNTIME INTEGRITY ──────────────────────────────


def test_packet_builder_and_runtime_frozen():
    """Requirement 13: Packet builder, candidate runtime, and selected rules must remain frozen."""
    pb_path = REPO_ROOT / "fase0/experiments/h3dv2_dev_002/integration/packet_builder.py"
    assert _sha256_file(pb_path) == FROZEN_PACKET_BUILDER_SHA256

    runtime_dir = REPO_ROOT / "fase0/experiments/h3dv2_dev_002/runtime"
    expected_runtime = {
        "__init__.py": "8c1ed607d8612aedcfc714ecca7fb6631b8263ecfecbacce03080820898b9a61",
        "candidate.py": "7474219ef79fb61de589726a7a3c8adb69e5bf3520ab87a818a9f618da7c5754",
        "ids.py": "19dad0a9cfeda967e2c798b5797cfeac26a8a709cbad4d5bffe00e89d2ea45b1",
        "lattice.py": "010f18ceba8ee20e8e1c2b63b625ea08b3e4b8241645d17a3434416b2cbe67f7",
        "schema.py": "280bc5e6a1a28b9aa55941cfdc0e48df32e574cf4f4b89af21eaee1d5344add0",
        "selected_rules.py": "0923edc53924d6f00b5a64d814d7e0301aa1b8b8fedcddf4b392024099d1732e",
        "serialization.py": "4deeb7a4e9d608776aa6057bc06896d9bcd2b637ab5f847afff588ad69c6a49a",
    }
    for fname, exp_hash in expected_runtime.items():
        fpath = runtime_dir / fname
        assert _sha256_file(fpath) == exp_hash, f"Runtime file {fname} modified"


# ── TEST 10: HISTORICAL B2C1A/B EVIDENCE INTEGRITY ────────────────────────────


def test_b2c1a_failure_evidence_intact():
    """Requirement 14: Historical B2C1A failure evidence and B2C1B forensic audit must remain intact."""
    evidence_map = {
        REPO_ROOT / "fase0/reality_corpus/FC009_STAGE3B2D1B2C1_DEV002_RAW_JOURNAL.jsonl": FROZEN_B2C1A_JOURNAL_SHA256,
        REPO_ROOT / "fase0/reality_corpus/FC009_STAGE3B2D1B2C1_DEV002_RAW_RESULTS.json": FROZEN_B2C1A_RESULTS_SHA256,
        REPO_ROOT / "fase0/reality_corpus/FC009_STAGE3B2D1B2C1_DEV002_EXECUTION_RECEIPT.json": FROZEN_B2C1A_RECEIPT_SHA256,
        REPO_ROOT / "fase0/reality_corpus/FC009_STAGE3B2D1B2C1A_DEV002_RAW_EXECUTION_AUDIT.json": FROZEN_B2C1A_AUDIT_SHA256,
        REPO_ROOT / "fase0/reality_corpus/FC009_STAGE3B2D1B2C1B_UNIVERSAL_M2_FAILURE_FORENSIC_AUDIT.json": FROZEN_B2C1B_AUDIT_SHA256,
    }
    for path, exp_sha in evidence_map.items():
        assert _sha256_file(path) == exp_sha, f"Historical failure evidence {path.name} mutated"

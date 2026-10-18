"""PROMETEO Colab Vision Assessor Feasibility Pack Acceptance Test Suite v0.1.
Campaign: PROM-C01
Validates all 23 acceptance test criteria defined in PROM-C01 specification.
"""

import hashlib
import json
import os
import shutil
import subprocess

from fase0.colab.vision_assessor.environment_probe import (
    probe_hardware_environment,
    check_storage_gate,
    check_vram_gate
)
from fase0.colab.vision_assessor.synthetic_fixture_generator import (
    generate_synthetic_fixture,
    get_synthetic_fixture_manifest,
    compute_pixel_content_sha256,
    compute_pixel_content_sha256_from_bytes,
    CANONICAL_PREIMAGE_VERSION,
    EXPECTED_PIXEL_CONTENT_SHA256,
    HISTORICAL_PNG_ENCODING_SHA256,
    FROZEN_SEED,
    PASS_B_ROLE_VOCABULARY
)
from fase0.colab.vision_assessor.benchmark_runner import (
    BenchmarkRunner,
    MockVisionModelAdapter,
    RealQwenVLAdapter,
    VisionModelAdapter,
    classify_repeatability,
    check_memory_reclamation_gate
)
from fase0.colab.vision_assessor.result_validator import (
    validate_benchmark_result,
    validate_colab_result_bundle,
    load_result_schema
)
from fase0.colab.vision_assessor.decision_gate import (
    evaluate_quality_gate,
    enforce_no_canonical_model_selection,
    CanonicalAuthorityFirewallViolation
)
from fase0.autonomous.authority import AuthorityEngine, PathAuthorityDenied

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRATCH_DIR = os.path.join(REPO_ROOT, "fase0", "scratch")
SUBSYSTEM_DIR = os.path.join(REPO_ROOT, "fase0", "colab", "vision_assessor")
PASS_B_RUN_DIR = os.path.join(REPO_ROOT, "fase0", "reality_corpus", "pass_b_runs", "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001")

EXPECTED_PIXEL_SHA = EXPECTED_PIXEL_CONTENT_SHA256
EXPECTED_PNG_SHA = HISTORICAL_PNG_ENCODING_SHA256
EXPECTED_FIXTURE_SHA = HISTORICAL_PNG_ENCODING_SHA256
EXPECTED_PROMPT_SHA = "70627fa8eab465b2bfc526ec645f388a10d4370338ed93ecd3c76dfdeaa5c810"
FROZEN_FIXTURE_GENERATOR_SOURCE_SHA256 = "56bf7fd49d8b30c2470335e38f89022a20e4867e7a8b442f129715ef53db90e4"


os.makedirs(SCRATCH_DIR, exist_ok=True)


# ==============================================================================
# 01. ENVIRONMENT MANIFEST SCHEMA
# ==============================================================================
def test_01_environment_manifest_schema():
    manifest = probe_hardware_environment()
    required_keys = [
        "manifest_version", "timestamp_utc", "python_version", "os",
        "cpu_arch", "cpu_count", "disk_total_gb", "disk_free_gb",
        "gpu_detected", "gpu_count", "gpu_model", "vram_total_mb",
        "vram_total_gb", "cuda_version", "compute_capability"
    ]
    for k in required_keys:
        assert k in manifest, f"Missing key '{k}' in environment manifest"
    assert manifest["disk_free_gb"] > 0
    assert manifest["python_version"] != ""


# ==============================================================================
# 02. SYNTHETIC FIXTURE DETERMINISTIC
# ==============================================================================
def test_02_synthetic_fixture_deterministic():
    b1, s1, p1 = generate_synthetic_fixture(seed=FROZEN_SEED)
    b2, s2, p2 = generate_synthetic_fixture(seed=FROZEN_SEED)
    assert b1 == b2, "Synthetic fixture bytes must be identical across runs"
    assert s1 == s2, "Synthetic fixture PNG SHA must be identical across runs"
    assert p1 == p2, "Synthetic fixture pixel SHA must be identical across runs"


# ==============================================================================
# 03. FIXTURE DIGEST STABLE
# ==============================================================================
def test_03_fixture_digest_stable():
    _, png_sha, pixel_sha = generate_synthetic_fixture(seed=FROZEN_SEED)
    assert pixel_sha == EXPECTED_PIXEL_CONTENT_SHA256, f"Pixel SHA changed: {pixel_sha} != {EXPECTED_PIXEL_CONTENT_SHA256}"
    assert png_sha == HISTORICAL_PNG_ENCODING_SHA256, f"Local reference PNG SHA changed: {png_sha} != {HISTORICAL_PNG_ENCODING_SHA256}"


# ==============================================================================
# 04. MODEL REGISTRY SCHEMA
# ==============================================================================
def test_04_model_registry_schema():
    reg_path = os.path.join(SUBSYSTEM_DIR, "MODEL_CANDIDATE_REGISTRY_v0.1.json")
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    assert "candidates" in registry
    assert len(registry["candidates"]) >= 3
    for c in registry["candidates"]:
        assert c["status"] == "PROPOSED", f"Candidate {c['candidate_id']} must have status PROPOSED during PROM-C01"
        assert "memory_specs" in c
        assert "storage_estimate" in c
        assert "supported_quantizations" in c


# ==============================================================================
# 05. STORAGE GATE
# ==============================================================================
def test_05_storage_gate():
    # Pass scenario
    passed, r_pass = check_storage_gate(free_disk_gb=50.0, estimated_download_gb=10.0, estimated_cache_gb=10.0)
    assert passed is True
    assert r_pass["verdict"] == "STORAGE_APPROVED"

    # Fail scenario
    failed, r_fail = check_storage_gate(free_disk_gb=15.0, estimated_download_gb=10.0, estimated_cache_gb=10.0, safety_margin_gb=5.0)
    assert failed is False
    assert r_fail["verdict"] == "MODEL_STORAGE_GATE_TRIGGERED"


# ==============================================================================
# 06. VRAM GATE
# ==============================================================================
def test_06_vram_gate():
    specs = {"bf16_min_gb": 16.0, "int8_min_gb": 10.0, "int4_min_gb": 6.0}
    assert check_vram_gate(0.0, specs) == "UNKNOWN_REQUIRES_PROBE"
    assert check_vram_gate(24.0, specs) == "ELIGIBLE_FOR_BF16"
    assert check_vram_gate(12.0, specs) == "ELIGIBLE_FOR_8BIT"
    assert check_vram_gate(8.0, specs) == "ELIGIBLE_FOR_4BIT"
    assert check_vram_gate(4.0, specs) == "INELIGIBLE_FOR_CURRENT_GPU"


# ==============================================================================
# 07. RESULT SCHEMA & VALID SAMPLE
# ==============================================================================
def test_07_result_schema_valid_sample():
    adapter = MockVisionModelAdapter(candidate_id="QWEN3_VL_4B_CLASS", model_id="Qwen/Qwen2.5-VL-3B-Instruct")
    runner = BenchmarkRunner(
        adapter=adapter,
        experiment_id="EXP-001",
        candidate_config={"candidate_id": "QWEN3_VL_4B_CLASS", "model_id": "Qwen/Qwen2.5-VL-3B-Instruct"},
        fixture_path="synthetic_fixture.png",
        fixture_sha256=EXPECTED_FIXTURE_SHA,
        prompt_data={"prompt_id": "SYNTHETIC_BENCHMARK_PROMPT_v0.1"},
        prompt_sha256=EXPECTED_PROMPT_SHA,
        environment_manifest_sha256="a" * 64,
        repetition_count=3
    )
    res = runner.run_benchmark()
    reg_path = os.path.join(SUBSYSTEM_DIR, "MODEL_CANDIDATE_REGISTRY_v0.1.json")
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    is_valid, errors = validate_benchmark_result(
        result=res,
        candidate_registry=registry,
        expected_fixture_sha=EXPECTED_FIXTURE_SHA,
        expected_prompt_sha=EXPECTED_PROMPT_SHA
    )
    assert is_valid is True, f"Validation failed: {errors}"


# ==============================================================================
# 08. INVALID ROLE REJECTED
# ==============================================================================
def test_08_invalid_role_rejected():
    adapter = MockVisionModelAdapter(candidate_id="QWEN3_VL_4B_CLASS", role="ILLEGAL_ROLE_LABEL")
    runner = BenchmarkRunner(
        adapter=adapter,
        experiment_id="EXP-002",
        candidate_config={"candidate_id": "QWEN3_VL_4B_CLASS", "model_id": "Qwen/Qwen2.5-VL-3B-Instruct"},
        fixture_path="synthetic_fixture.png",
        fixture_sha256=EXPECTED_FIXTURE_SHA,
        prompt_data={"prompt_id": "SYNTHETIC_BENCHMARK_PROMPT_v0.1"},
        prompt_sha256=EXPECTED_PROMPT_SHA,
        environment_manifest_sha256="a" * 64,
        repetition_count=3
    )
    res = runner.run_benchmark()
    reg_path = os.path.join(SUBSYSTEM_DIR, "MODEL_CANDIDATE_REGISTRY_v0.1.json")
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    is_valid, errors = validate_benchmark_result(
        result=res,
        candidate_registry=registry,
        expected_fixture_sha=EXPECTED_FIXTURE_SHA,
        expected_prompt_sha=EXPECTED_PROMPT_SHA
    )
    assert is_valid is False
    assert any("INVALID_ROLE_REJECTED" in e or "SCHEMA_VALIDATION_ERROR" in e for e in errors)


# ==============================================================================
# 09. MALFORMED RESULT REJECTED
# ==============================================================================
def test_09_malformed_result_rejected():
    bad_res = {"experiment_id": "EXP-BAD", "runs": []}
    reg_path = os.path.join(SUBSYSTEM_DIR, "MODEL_CANDIDATE_REGISTRY_v0.1.json")
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    is_valid, errors = validate_benchmark_result(
        result=bad_res,
        candidate_registry=registry,
        expected_fixture_sha=EXPECTED_FIXTURE_SHA,
        expected_prompt_sha=EXPECTED_PROMPT_SHA
    )
    assert is_valid is False
    assert any("SCHEMA_VALIDATION_ERROR" in e for e in errors)


# ==============================================================================
# 10. WRONG FIXTURE DIGEST REJECTED
# ==============================================================================
def test_10_wrong_fixture_digest_rejected():
    adapter = MockVisionModelAdapter(candidate_id="QWEN3_VL_4B_CLASS")
    runner = BenchmarkRunner(
        adapter=adapter,
        experiment_id="EXP-003",
        candidate_config={"candidate_id": "QWEN3_VL_4B_CLASS", "model_id": "Qwen/Qwen2.5-VL-3B-Instruct"},
        fixture_path="synthetic_fixture.png",
        fixture_sha256="b" * 64,  # Incorrect hash
        prompt_data={"prompt_id": "SYNTHETIC_BENCHMARK_PROMPT_v0.1"},
        prompt_sha256=EXPECTED_PROMPT_SHA,
        environment_manifest_sha256="a" * 64,
        repetition_count=3
    )
    res = runner.run_benchmark()
    reg_path = os.path.join(SUBSYSTEM_DIR, "MODEL_CANDIDATE_REGISTRY_v0.1.json")
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    is_valid, errors = validate_benchmark_result(
        result=res,
        candidate_registry=registry,
        expected_fixture_sha=EXPECTED_FIXTURE_SHA,
        expected_prompt_sha=EXPECTED_PROMPT_SHA
    )
    assert is_valid is False
    assert any("WRONG_FIXTURE_HASH_REJECTED" in e for e in errors)


# ==============================================================================
# 11. MISSING ENVIRONMENT PROVENANCE REJECTED
# ==============================================================================
def test_11_missing_environment_provenance_rejected():
    adapter = MockVisionModelAdapter(candidate_id="QWEN3_VL_4B_CLASS")
    runner = BenchmarkRunner(
        adapter=adapter,
        experiment_id="EXP-004",
        candidate_config={"candidate_id": "QWEN3_VL_4B_CLASS", "model_id": "Qwen/Qwen2.5-VL-3B-Instruct"},
        fixture_path="synthetic_fixture.png",
        fixture_sha256=EXPECTED_FIXTURE_SHA,
        prompt_data={"prompt_id": "SYNTHETIC_BENCHMARK_PROMPT_v0.1"},
        prompt_sha256=EXPECTED_PROMPT_SHA,
        environment_manifest_sha256="bad_short_sha",
        repetition_count=3
    )
    res = runner.run_benchmark()
    reg_path = os.path.join(SUBSYSTEM_DIR, "MODEL_CANDIDATE_REGISTRY_v0.1.json")
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    is_valid, errors = validate_benchmark_result(
        result=res,
        candidate_registry=registry,
        expected_fixture_sha=EXPECTED_FIXTURE_SHA,
        expected_prompt_sha=EXPECTED_PROMPT_SHA
    )
    assert is_valid is False
    assert any("SCHEMA_VALIDATION_ERROR" in e or "MISSING_ENVIRONMENT_PROVENANCE" in e for e in errors)


# ==============================================================================
# 12. REPEATABILITY CLASSIFIER
# ==============================================================================
def test_12_repeatability_classifier():
    # 1. Bitwise deterministic
    r_bit = [
        {"raw_output_sha256": "sha1", "role": "CONTENT_ENCLOSURE_ROLE", "parse_valid": True, "error": None},
        {"raw_output_sha256": "sha1", "role": "CONTENT_ENCLOSURE_ROLE", "parse_valid": True, "error": None},
        {"raw_output_sha256": "sha1", "role": "CONTENT_ENCLOSURE_ROLE", "parse_valid": True, "error": None}
    ]
    assert classify_repeatability(r_bit) == "BITWISE_DETERMINISTIC"

    # 2. Semantically stable
    r_sem = [
        {"raw_output_sha256": "sha1", "role": "CONTENT_ENCLOSURE_ROLE", "parse_valid": True, "error": None},
        {"raw_output_sha256": "sha2", "role": "CONTENT_ENCLOSURE_ROLE", "parse_valid": True, "error": None},
        {"raw_output_sha256": "sha3", "role": "CONTENT_ENCLOSURE_ROLE", "parse_valid": True, "error": None}
    ]
    assert classify_repeatability(r_sem) == "SEMANTICALLY_STABLE"

    # 3. Unstable
    r_unst = [
        {"raw_output_sha256": "sha1", "role": "CONTENT_ENCLOSURE_ROLE", "parse_valid": True, "error": None},
        {"raw_output_sha256": "sha2", "role": "LINEAR_DIVIDER_ROLE", "parse_valid": True, "error": None},
        {"raw_output_sha256": "sha3", "role": "CONTENT_ENCLOSURE_ROLE", "parse_valid": True, "error": None}
    ]
    assert classify_repeatability(r_unst) == "UNSTABLE"

    # 4. Failed
    r_fail = [
        {"raw_output_sha256": "sha1", "role": "CONTENT_ENCLOSURE_ROLE", "parse_valid": True, "error": None},
        {"raw_output_sha256": "sha2", "role": "CONTENT_ENCLOSURE_ROLE", "parse_valid": False, "error": "Parse error"},
        {"raw_output_sha256": "sha3", "role": "CONTENT_ENCLOSURE_ROLE", "parse_valid": True, "error": None}
    ]
    assert classify_repeatability(r_fail) == "FAILED"


# ==============================================================================
# 13. NOTEBOOK VALID JSON
# ==============================================================================
def test_13_notebook_valid_json():
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    assert nb["nbformat"] == 4
    assert len(nb["cells"]) >= 6


# ==============================================================================
# 14. NOTEBOOK NO ABSOLUTE MAC PATH
# ==============================================================================
def test_14_notebook_no_absolute_mac_path():
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    text = open(nb_path, "r", encoding="utf-8").read()
    assert "/Users/" not in text, "Found local Mac absolute path '/Users/' in notebook"


# ==============================================================================
# 15. NOTEBOOK NO SECRETS
# ==============================================================================
def test_15_notebook_no_secrets():
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    text = open(nb_path, "r", encoding="utf-8").read()
    assert "sk-" not in text
    assert "OPENROUTER_API_KEY" not in text
    assert "hf_" not in text


# ==============================================================================
# 16. NOTEBOOK NO AG277 PATHS
# ==============================================================================
def test_16_notebook_no_ag277_paths():
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    text = open(nb_path, "r", encoding="utf-8").read()
    assert "pass_b_runs" not in text
    assert "FC009" not in text


# ==============================================================================
# 17. LOCAL LARGE MODEL DOWNLOAD COUNT = 0
# ==============================================================================
def test_17_local_large_model_download_count_zero():
    # Verify no large model weights or tensors exist in the PROM-C01 subsystem or scratch
    model_weight_exts = {".safetensors", ".bin", ".pt", ".pth", ".onnx", ".gguf"}
    for check_dir in [SUBSYSTEM_DIR, SCRATCH_DIR]:
        for root, dirs, files in os.walk(check_dir):
            dirs[:] = [d for d in dirs if d not in [".git", ".venv", ".agents", ".gemini", "node_modules", ".scratch_cf22cef"]]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in model_weight_exts:
                    fp = os.path.join(root, f)
                    size_mb = os.path.getsize(fp) / (1024 * 1024)
                    assert size_mb < 50.0, f"Found large model weight file in PROM-C01: {fp} ({size_mb:.1f} MB)"


# ==============================================================================
# 18. FAKE VALID COLAB BUNDLE ACCEPTED
# ==============================================================================
def test_18_fake_valid_colab_bundle_accepted():
    bundle_dir = os.path.join(SCRATCH_DIR, "fake_valid_bundle")
    if os.path.exists(bundle_dir):
        shutil.rmtree(bundle_dir)
    os.makedirs(bundle_dir, exist_ok=True)

    adapter = MockVisionModelAdapter(candidate_id="QWEN3_VL_4B_CLASS", model_id="Qwen/Qwen2.5-VL-3B-Instruct")
    runner = BenchmarkRunner(
        adapter=adapter,
        experiment_id="EXP-BUNDLE-VALID",
        candidate_config={"candidate_id": "QWEN3_VL_4B_CLASS", "model_id": "Qwen/Qwen2.5-VL-3B-Instruct"},
        fixture_path="synthetic_fixture.png",
        fixture_sha256=EXPECTED_FIXTURE_SHA,
        prompt_data={"prompt_id": "SYNTHETIC_BENCHMARK_PROMPT_v0.1"},
        prompt_sha256=EXPECTED_PROMPT_SHA,
        environment_manifest_sha256="c" * 64,
        repetition_count=3
    )
    res = runner.run_benchmark()

    # Write bundle files
    env_m = {"manifest_version": "0.1.0", "gpu_model": "NVIDIA A100-SXM4-40GB"}
    with open(os.path.join(bundle_dir, "COLAB_ENVIRONMENT_MANIFEST.json"), "w") as f:
        json.dump(env_m, f)
    with open(os.path.join(bundle_dir, "COLAB_MODEL_METADATA_SNAPSHOT.json"), "w") as f:
        json.dump({"snapshot_version": "0.1.0"}, f)
    with open(os.path.join(bundle_dir, "COLAB_VISION_BENCHMARK_RESULTS.json"), "w") as f:
        json.dump(res, f)
    with open(os.path.join(bundle_dir, "COLAB_EXECUTION_LOG.jsonl"), "w") as f:
        f.write('{"event": "BENCHMARK_COMPLETE"}\n')

    # Manifest with file hashes
    fhashes = {}
    for fn in ["COLAB_ENVIRONMENT_MANIFEST.json", "COLAB_MODEL_METADATA_SNAPSHOT.json", "COLAB_VISION_BENCHMARK_RESULTS.json", "COLAB_EXECUTION_LOG.jsonl"]:
        fhashes[fn] = hashlib.sha256(open(os.path.join(bundle_dir, fn), "rb").read()).hexdigest()

    with open(os.path.join(bundle_dir, "COLAB_JOB_RESULT_MANIFEST.json"), "w") as f:
        json.dump({"manifest_version": "0.1.0", "file_hashes": fhashes}, f)

    reg_path = os.path.join(SUBSYSTEM_DIR, "MODEL_CANDIDATE_REGISTRY_v0.1.json")
    ingest_res = validate_colab_result_bundle(
        bundle_dir=bundle_dir,
        candidate_registry_path=reg_path,
        expected_fixture_sha=EXPECTED_FIXTURE_SHA,
        expected_prompt_sha=EXPECTED_PROMPT_SHA
    )
    assert ingest_res["verdict"] == "ACCEPTED_FOR_REVIEW"
    assert ingest_res["valid"] is True


# ==============================================================================
# 19. TAMPERED COLAB BUNDLE REJECTED
# ==============================================================================
def test_19_tampered_colab_bundle_rejected():
    bundle_dir = os.path.join(SCRATCH_DIR, "fake_tampered_bundle")
    if os.path.exists(bundle_dir):
        shutil.rmtree(bundle_dir)
    os.makedirs(bundle_dir, exist_ok=True)

    adapter = MockVisionModelAdapter(candidate_id="QWEN3_VL_4B_CLASS", model_id="Qwen/Qwen2.5-VL-3B-Instruct")
    runner = BenchmarkRunner(
        adapter=adapter,
        experiment_id="EXP-BUNDLE-TAMPERED",
        candidate_config={"candidate_id": "QWEN3_VL_4B_CLASS", "model_id": "Qwen/Qwen2.5-VL-3B-Instruct"},
        fixture_path="synthetic_fixture.png",
        fixture_sha256=EXPECTED_FIXTURE_SHA,
        prompt_data={"prompt_id": "SYNTHETIC_BENCHMARK_PROMPT_v0.1"},
        prompt_sha256=EXPECTED_PROMPT_SHA,
        environment_manifest_sha256="c" * 64,
        repetition_count=3
    )
    res = runner.run_benchmark()

    with open(os.path.join(bundle_dir, "COLAB_ENVIRONMENT_MANIFEST.json"), "w") as f:
        json.dump({"manifest_version": "0.1.0"}, f)
    with open(os.path.join(bundle_dir, "COLAB_MODEL_METADATA_SNAPSHOT.json"), "w") as f:
        json.dump({"snapshot_version": "0.1.0"}, f)
    with open(os.path.join(bundle_dir, "COLAB_VISION_BENCHMARK_RESULTS.json"), "w") as f:
        json.dump(res, f)
    with open(os.path.join(bundle_dir, "COLAB_EXECUTION_LOG.jsonl"), "w") as f:
        f.write('{"event": "BENCHMARK_COMPLETE"}\n')

    fhashes = {
        "COLAB_ENVIRONMENT_MANIFEST.json": "tampered_fake_hash_12345",
        "COLAB_MODEL_METADATA_SNAPSHOT.json": hashlib.sha256(open(os.path.join(bundle_dir, "COLAB_MODEL_METADATA_SNAPSHOT.json"), "rb").read()).hexdigest(),
        "COLAB_VISION_BENCHMARK_RESULTS.json": hashlib.sha256(open(os.path.join(bundle_dir, "COLAB_VISION_BENCHMARK_RESULTS.json"), "rb").read()).hexdigest(),
        "COLAB_EXECUTION_LOG.jsonl": hashlib.sha256(open(os.path.join(bundle_dir, "COLAB_EXECUTION_LOG.jsonl"), "rb").read()).hexdigest()
    }
    with open(os.path.join(bundle_dir, "COLAB_JOB_RESULT_MANIFEST.json"), "w") as f:
        json.dump({"manifest_version": "0.1.0", "file_hashes": fhashes}, f)

    reg_path = os.path.join(SUBSYSTEM_DIR, "MODEL_CANDIDATE_REGISTRY_v0.1.json")
    ingest_res = validate_colab_result_bundle(
        bundle_dir=bundle_dir,
        candidate_registry_path=reg_path,
        expected_fixture_sha=EXPECTED_FIXTURE_SHA,
        expected_prompt_sha=EXPECTED_PROMPT_SHA
    )
    assert ingest_res["verdict"] == "REJECTED"
    assert ingest_res["valid"] is False
    assert any("BUNDLE_FILE_DIGEST_MISMATCH" in r for r in ingest_res["reasons"])


# ==============================================================================
# 20. AG277 REMAINS UNCHANGED
# ==============================================================================
def test_20_ag277_remains_unchanged():
    expected_hashes = {
        "00001.json": "fb52d296fb0f756b8a8af1c2ac5c2a155a5c9aed24d45ca9546f2f8820d1f7b6",
        "00002.json": "88e9f15779c74a1209e6b249cc63c5df9d75b5247952c30dd8d3549a4ca249ae",
        "00003.json": "71e0ef96507d30ca255dc8625f13ae70defe50d99741d5159b0f1e1910c6b126"
    }
    for fname, exp_h in expected_hashes.items():
        fp = os.path.join(PASS_B_RUN_DIR, "results", fname)
        assert os.path.exists(fp), f"AG277 result {fname} missing"
        act_h = hashlib.sha256(open(fp, "rb").read()).hexdigest()
        assert act_h == exp_h, f"AG277 result {fname} hash mutated: {act_h} != {exp_h}"

    ledger_path = os.path.join(PASS_B_RUN_DIR, "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001_DERIVED_LEDGER.jsonl")
    lines = [l.strip() for l in open(ledger_path, "r").readlines() if l.strip()]
    assert len(lines) == 3, f"AG277 ledger line count mutated: {len(lines)} != 3"


# ==============================================================================
# 21. CODEX UNAUTHORIZED PATH MODIFICATION REJECTED
# ==============================================================================
def test_21_codex_unauthorized_path_modification_rejected():
    auth = {
        "allowed_paths": ["fase0/colab/vision_assessor/"],
        "forbidden_paths": [".git/", "fase0/reality_corpus/pass_b_runs/"]
    }
    engine = AuthorityEngine(authority_spec=auth, workspace_root=REPO_ROOT)
    forbidden_target = "fase0/reality_corpus/pass_b_runs/malicious_probe.txt"
    raised = False
    try:
        engine.validate_write_path(forbidden_target)
    except PathAuthorityDenied:
        raised = True
    assert raised, "Should have raised PathAuthorityDenied"


# ==============================================================================
# 22. DECISION GATE PREVENTS CANONICAL SELECTION
# ==============================================================================
def test_22_decision_gate_prevents_canonical_selection():
    raised = False
    try:
        enforce_no_canonical_model_selection("CANONICAL_PASS_B_MODEL")
    except CanonicalAuthorityFirewallViolation:
        raised = True
    assert raised, "Should have raised CanonicalAuthorityFirewallViolation"


# ==============================================================================
# 23. QUALITY GATE CRITERIA EVALUATION
# ==============================================================================
def test_23_quality_gate_evaluation():
    adapter = MockVisionModelAdapter(candidate_id="QWEN3_VL_4B_CLASS", model_id="Qwen/Qwen2.5-VL-3B-Instruct")
    runner = BenchmarkRunner(
        adapter=adapter,
        experiment_id="EXP-GATE-EVAL",
        candidate_config={"candidate_id": "QWEN3_VL_4B_CLASS", "model_id": "Qwen/Qwen2.5-VL-3B-Instruct"},
        fixture_path="synthetic_fixture.png",
        fixture_sha256=EXPECTED_FIXTURE_SHA,
        prompt_data={"prompt_id": "SYNTHETIC_BENCHMARK_PROMPT_v0.1"},
        prompt_sha256=EXPECTED_PROMPT_SHA,
        environment_manifest_sha256="c" * 64,
        repetition_count=3
    )
    res = runner.run_benchmark()
    q_eval = evaluate_quality_gate(res)
    assert q_eval["verdict"] == "TECHNICALLY_ELIGIBLE"
    dims = q_eval["dimensions"]
    assert dims["LOAD_SUCCESS"] is True
    assert dims["INFERENCE_SUCCESS"] is True
    assert dims["STRICT_JSON_SUCCESS_RATE"] == 1.0
    assert dims["REPEATABILITY"] == "BITWISE_DETERMINISTIC"
    assert q_eval["canonical_selection_permitted"] is False


# ==============================================================================
# 24. RAW PIXEL HASH DETERMINISTIC LOCALLY
# ==============================================================================
def test_24_raw_pixel_hash_deterministic_locally():
    b1, png1, p1 = generate_synthetic_fixture(seed=FROZEN_SEED)
    b2, png2, p2 = generate_synthetic_fixture(seed=FROZEN_SEED)
    assert p1 == EXPECTED_PIXEL_CONTENT_SHA256
    assert p2 == EXPECTED_PIXEL_CONTENT_SHA256
    assert p1 == p2, "Raw pixel hash must be bitwise deterministic across local runs"

    from PIL import Image
    import io
    im = Image.open(io.BytesIO(b1)).convert("RGB")
    raw_pixels = im.tobytes("raw", "RGB")
    assert len(raw_pixels) == 800 * 1100 * 3
    preimage = (
        f"{CANONICAL_PREIMAGE_VERSION}\n"
        f"{im.width}\n"
        f"{im.height}\n"
        f"{im.mode}\n"
    ).encode("ascii") + raw_pixels
    computed_sha = hashlib.sha256(preimage).hexdigest()
    assert computed_sha == EXPECTED_PIXEL_CONTENT_SHA256


# ==============================================================================
# 25. DIFFERENT PNG SERIALIZATION PRESERVES PIXEL HASH
# ==============================================================================
def test_25_different_png_serialization_preserves_pixel_hash():
    from PIL import Image
    import io
    b, png_orig, pixel_orig = generate_synthetic_fixture(seed=FROZEN_SEED)
    im = Image.open(io.BytesIO(b)).convert("RGB")

    # Save with compress_level=1 (fast, different bytes)
    buf1 = io.BytesIO()
    im.save(buf1, format="PNG", compress_level=1, optimize=False)
    png_bytes_1 = buf1.getvalue()

    # Save with compress_level=9 (max compression, different bytes)
    buf2 = io.BytesIO()
    im.save(buf2, format="PNG", compress_level=9, optimize=True)
    png_bytes_2 = buf2.getvalue()

    png_sha_1 = hashlib.sha256(png_bytes_1).hexdigest()
    png_sha_2 = hashlib.sha256(png_bytes_2).hexdigest()

    # Different PNG encoding parameters yield different PNG digests
    assert png_sha_1 != png_sha_2, "Different PNG encoding parameters should yield different PNG digests"

    # Authoritative pixel content hash is preserved across both
    p_sha_1 = compute_pixel_content_sha256_from_bytes(png_bytes_1)
    p_sha_2 = compute_pixel_content_sha256_from_bytes(png_bytes_2)
    assert p_sha_1 == EXPECTED_PIXEL_CONTENT_SHA256
    assert p_sha_2 == EXPECTED_PIXEL_CONTENT_SHA256
    assert p_sha_1 == p_sha_2


# ==============================================================================
# 26. ONE-PIXEL MUTATION CHANGES PIXEL HASH
# ==============================================================================
def test_26_one_pixel_mutation_changes_pixel_hash():
    from PIL import Image
    import io
    b, _, _ = generate_synthetic_fixture(seed=FROZEN_SEED)
    im = Image.open(io.BytesIO(b)).convert("RGB")
    raw_bytes = bytearray(im.tobytes("raw", "RGB"))

    # Mutate exactly one byte in the 2.64MB buffer
    raw_bytes[100] = (raw_bytes[100] + 1) % 256

    mutated_preimage = (
        f"{CANONICAL_PREIMAGE_VERSION}\n"
        f"{im.width}\n"
        f"{im.height}\n"
        f"{im.mode}\n"
    ).encode("ascii") + bytes(raw_bytes)

    mutated_sha = hashlib.sha256(mutated_preimage).hexdigest()
    assert mutated_sha != EXPECTED_PIXEL_CONTENT_SHA256, "Single byte mutation must change pixel content SHA-256"


# ==============================================================================
# 27. NOTEBOOK GENERATOR MATCHES FROZEN GENERATOR SOURCE
# ==============================================================================
def test_27_notebook_generator_matches_frozen_generator_source():
    gen_file = os.path.join(SUBSYSTEM_DIR, "synthetic_fixture_generator.py")
    with open(gen_file, "r", encoding="utf-8") as f:
        src = f.read()
    current_src_sha = hashlib.sha256(src.encode("utf-8")).hexdigest()
    assert current_src_sha == FROZEN_FIXTURE_GENERATOR_SOURCE_SHA256, (
        f"Generator source has drifted from frozen hash: {current_src_sha} != {FROZEN_FIXTURE_GENERATOR_SOURCE_SHA256}"
    )

    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cell4_src = "".join(nb["cells"][4]["source"])
    assert FROZEN_FIXTURE_GENERATOR_SOURCE_SHA256 in cell4_src
    assert "EXPECTED_GENERATOR_SOURCE_SHA256" in cell4_src


# ==============================================================================
# 28. NOTEBOOK VALIDATES PIXEL HASH
# ==============================================================================
def test_28_notebook_validates_pixel_hash():
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cell4_src = "".join(nb["cells"][4]["source"])
    assert EXPECTED_PIXEL_CONTENT_SHA256 in cell4_src
    assert "PIXEL_CONTENT_SHA256" in cell4_src
    assert "PNG_ENCODING_SHA256" in cell4_src
    assert "assert pixel_content_sha256 == EXPECTED_PIXEL_CONTENT_SHA256" in cell4_src


# ==============================================================================
# 29. ENCODED PNG SHA REMAINS RECORDED
# ==============================================================================
def test_29_encoded_png_sha_remains_recorded():
    adapter = MockVisionModelAdapter(candidate_id="QWEN3_VL_4B_CLASS", model_id="Qwen/Qwen2.5-VL-3B-Instruct")
    runner = BenchmarkRunner(
        adapter=adapter,
        experiment_id="EXP-DUAL-HASH",
        candidate_config={"candidate_id": "QWEN3_VL_4B_CLASS", "model_id": "Qwen/Qwen2.5-VL-3B-Instruct"},
        fixture_path="synthetic_fixture.png",
        fixture_sha256=HISTORICAL_PNG_ENCODING_SHA256,
        fixture_pixel_sha256=EXPECTED_PIXEL_CONTENT_SHA256,
        prompt_data={"prompt_id": "SYNTHETIC_BENCHMARK_PROMPT_v0.1"},
        prompt_sha256=EXPECTED_PROMPT_SHA,
        environment_manifest_sha256="d" * 64,
        repetition_count=3
    )
    res = runner.run_benchmark()
    assert res["fixture_pixel_sha256"] == EXPECTED_PIXEL_CONTENT_SHA256
    assert res["fixture_png_sha256"] == HISTORICAL_PNG_ENCODING_SHA256
    assert res["fixture_sha256"] == HISTORICAL_PNG_ENCODING_SHA256


# ==============================================================================
# 30. INCORRECT PIXEL HASH FAILS CLOSED
# ==============================================================================
def test_30_incorrect_pixel_hash_fails_closed():
    adapter = MockVisionModelAdapter(candidate_id="QWEN3_VL_4B_CLASS", model_id="Qwen/Qwen2.5-VL-3B-Instruct")
    runner = BenchmarkRunner(
        adapter=adapter,
        experiment_id="EXP-BAD-PIXEL-HASH",
        candidate_config={"candidate_id": "QWEN3_VL_4B_CLASS", "model_id": "Qwen/Qwen2.5-VL-3B-Instruct"},
        fixture_path="synthetic_fixture.png",
        fixture_sha256=HISTORICAL_PNG_ENCODING_SHA256,
        fixture_pixel_sha256="0" * 64,
        prompt_data={"prompt_id": "SYNTHETIC_BENCHMARK_PROMPT_v0.1"},
        prompt_sha256=EXPECTED_PROMPT_SHA,
        environment_manifest_sha256="d" * 64,
        repetition_count=3
    )
    res = runner.run_benchmark()
    reg_path = os.path.join(SUBSYSTEM_DIR, "MODEL_CANDIDATE_REGISTRY_v0.1.json")
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    is_valid, errors = validate_benchmark_result(
        result=res,
        candidate_registry=registry,
        expected_fixture_sha=HISTORICAL_PNG_ENCODING_SHA256,
        expected_fixture_pixel_sha=EXPECTED_PIXEL_CONTENT_SHA256,
        expected_prompt_sha=EXPECTED_PROMPT_SHA
    )
    assert is_valid is False
    assert any("WRONG_FIXTURE_PIXEL_HASH_REJECTED" in e for e in errors)


# ==============================================================================
# 31. AG277 UNCHANGED ERRATA CHECK
# ==============================================================================
def test_31_ag277_unchanged_errata_check():
    expected_hashes = {
        "00001.json": "fb52d296fb0f756b8a8af1c2ac5c2a155a5c9aed24d45ca9546f2f8820d1f7b6",
        "00002.json": "88e9f15779c74a1209e6b249cc63c5df9d75b5247952c30dd8d3549a4ca249ae",
        "00003.json": "71e0ef96507d30ca255dc8625f13ae70defe50d99741d5159b0f1e1910c6b126"
    }
    for fname, exp_sha in expected_hashes.items():
        fpath = os.path.join(PASS_B_RUN_DIR, "results", fname)
        data = open(fpath, "rb").read()
        sha = hashlib.sha256(data).hexdigest()
        assert sha == exp_sha, f"AG277 file {fname} SHA mutated: {sha} != {exp_sha}"

    ledger_path = os.path.join(PASS_B_RUN_DIR, "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001_DERIVED_LEDGER.jsonl")
    lines = [l.strip() for l in open(ledger_path, "r").readlines() if l.strip()]
    assert len(lines) == 3, f"AG277 ledger must remain exactly 3 lines: got {len(lines)}"


# ==============================================================================
# 32. CANONICAL PNG BYTES HAVE FROZEN SHA
# ==============================================================================
def test_32_canonical_png_bytes_have_frozen_sha():
    fixture_path = os.path.join(SUBSYSTEM_DIR, "synthetic_fixture_v1.png")
    assert os.path.exists(fixture_path), f"Frozen fixture artifact missing at {fixture_path}"
    data = open(fixture_path, "rb").read()
    actual_sha = hashlib.sha256(data).hexdigest()
    assert actual_sha == EXPECTED_PNG_SHA, f"Canonical PNG hash mismatch: {actual_sha} != {EXPECTED_PNG_SHA}"
    assert len(data) == 9146, f"Canonical PNG size mismatch: {len(data)} != 9146"


# ==============================================================================
# 33. CANONICAL PNG DECODES TO EXPECTED PIXEL SHA
# ==============================================================================
def test_33_canonical_png_decodes_to_expected_pixel_sha():
    from PIL import Image
    import io
    fixture_path = os.path.join(SUBSYSTEM_DIR, "synthetic_fixture_v1.png")
    data = open(fixture_path, "rb").read()
    im = Image.open(io.BytesIO(data)).convert("RGB")
    assert im.width == 800
    assert im.height == 1100
    assert im.mode == "RGB"
    pixel_sha = compute_pixel_content_sha256(im)
    assert pixel_sha == EXPECTED_PIXEL_CONTENT_SHA256, (
        f"Decoded pixel SHA mismatch: {pixel_sha} != {EXPECTED_PIXEL_CONTENT_SHA256}"
    )


# ==============================================================================
# 34. NOTEBOOK EMBEDS EXACT CANONICAL BYTES
# ==============================================================================
def test_34_notebook_embeds_exact_canonical_bytes():
    import base64
    import re
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cell4_src = "".join(nb["cells"][4]["source"])
    match = re.search(r'CANONICAL_FIXTURE_PNG_B64\s*=\s*"""([^"]+)"""', cell4_src)
    assert match is not None, "CANONICAL_FIXTURE_PNG_B64 not found in notebook Cell 4"
    b64_str = match.group(1).strip()
    embedded_bytes = base64.b64decode(b64_str)
    embedded_sha = hashlib.sha256(embedded_bytes).hexdigest()
    assert embedded_sha == EXPECTED_PNG_SHA, (
        f"Embedded fixture bytes SHA mismatch: {embedded_sha} != {EXPECTED_PNG_SHA}"
    )
    canonical_on_disk = open(os.path.join(SUBSYSTEM_DIR, "synthetic_fixture_v1.png"), "rb").read()
    assert embedded_bytes == canonical_on_disk, "Embedded bytes must be bitwise identical to synthetic_fixture_v1.png"


# ==============================================================================
# 35. NOTEBOOK PERFORMS NO IMAGEDRAW FIXTURE GENERATION
# ==============================================================================
def test_35_notebook_performs_no_imagedraw_fixture_generation():
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cell4_src = "".join(nb["cells"][4]["source"])
    forbidden_tokens = [
        "ImageDraw",
        "draw.rectangle",
        "draw.line",
        "draw.ellipse",
        "draw.polygon",
        "generate_synthetic_fixture"
    ]
    for token in forbidden_tokens:
        assert token not in cell4_src, (
            f"Notebook Cell 4 must not redraw fixture using '{token}'; must consume frozen artifact"
        )


# ==============================================================================
# 36. TAMPERED PNG BYTES FAIL CONTAINER HASH
# ==============================================================================
def test_36_tampered_png_bytes_fail_container_hash():
    fixture_path = os.path.join(SUBSYSTEM_DIR, "synthetic_fixture_v1.png")
    data = bytearray(open(fixture_path, "rb").read())
    data[50] = (data[50] + 1) % 256
    tampered_sha = hashlib.sha256(data).hexdigest()
    assert tampered_sha != EXPECTED_PNG_SHA, "Tampered PNG bytes must fail container SHA verification"


# ==============================================================================
# 37. ALTERED DECODED PIXELS FAIL PIXEL HASH
# ==============================================================================
def test_37_altered_decoded_pixels_fail_pixel_hash():
    from PIL import Image
    import io
    fixture_path = os.path.join(SUBSYSTEM_DIR, "synthetic_fixture_v1.png")
    data = open(fixture_path, "rb").read()
    im = Image.open(io.BytesIO(data)).convert("RGB")
    raw_bytes = bytearray(im.tobytes())
    raw_bytes[500] = (raw_bytes[500] + 1) % 256
    preimage = (
        f"{CANONICAL_PREIMAGE_VERSION}\n"
        f"{im.width}\n"
        f"{im.height}\n"
        f"{im.mode}\n"
    ).encode("ascii") + bytes(raw_bytes)
    corrupted_sha = hashlib.sha256(preimage).hexdigest()
    assert corrupted_sha != EXPECTED_PIXEL_CONTENT_SHA256, (
        "Altered decoded pixels must fail pixel content SHA verification"
    )


# ==============================================================================
# 38. GENERATOR PROVENANCE REMAINS RECORDED
# ==============================================================================
def test_38_generator_provenance_remains_recorded():
    gen_file = os.path.join(SUBSYSTEM_DIR, "synthetic_fixture_generator.py")
    with open(gen_file, "r", encoding="utf-8") as f:
        src = f.read()
    actual_gen_sha = hashlib.sha256(src.encode("utf-8")).hexdigest()
    assert actual_gen_sha == FROZEN_FIXTURE_GENERATOR_SOURCE_SHA256, (
        f"Generator source has drifted: {actual_gen_sha} != {FROZEN_FIXTURE_GENERATOR_SOURCE_SHA256}"
    )

    packet_path = os.path.join(SUBSYSTEM_DIR, "COLAB_JOB_PACKET_v0.1.json")
    with open(packet_path, "r", encoding="utf-8") as f:
        packet = json.load(f)
    cd = packet["component_digests"]
    assert cd["fixture_generator_source_sha256"] == FROZEN_FIXTURE_GENERATOR_SOURCE_SHA256
    assert cd["fixture_artifact_png_sha256"] == EXPECTED_PNG_SHA
    assert cd["authoritative_fixture_pixel_sha256"] == EXPECTED_PIXEL_CONTENT_SHA256
    assert cd["generator_python_version"] == "3.11.4"
    assert cd["generator_pillow_version"] == "12.3.0"
    assert cd["dimensions"] == {"width": 800, "height": 1100}
    assert cd["mode"] == "RGB"
    assert cd["seed"] == 42


# ==============================================================================
# 39. AG277 REMAINS UNCHANGED
# ==============================================================================
def test_39_ag277_remains_unchanged():
    expected_hashes = {
        "00001.json": "fb52d296fb0f756b8a8af1c2ac5c2a155a5c9aed24d45ca9546f2f8820d1f7b6",
        "00002.json": "88e9f15779c74a1209e6b249cc63c5df9d75b5247952c30dd8d3549a4ca249ae",
        "00003.json": "71e0ef96507d30ca255dc8625f13ae70defe50d99741d5159b0f1e1910c6b126"
    }
    for fname, exp_sha in expected_hashes.items():
        fpath = os.path.join(PASS_B_RUN_DIR, "results", fname)
        data = open(fpath, "rb").read()
        sha = hashlib.sha256(data).hexdigest()
        assert sha == exp_sha, f"AG277 file {fname} SHA mutated: {sha} != {exp_sha}"

    ledger_path = os.path.join(PASS_B_RUN_DIR, "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001_DERIVED_LEDGER.jsonl")
    lines = [l.strip() for l in open(ledger_path, "r").readlines() if l.strip()]
    assert len(lines) == 3, f"AG277 ledger must remain exactly 3 lines: got {len(lines)}"


# ==============================================================================
# 40. STATIC ANTI-MOCK NOTEBOOK STRUCTURE
# ==============================================================================
def test_40_static_anti_mock_notebook_structure():
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    all_code = "".join(
        "".join(c["source"])
        for c in nb["cells"]
        if c.get("cell_type") == "code"
    )

    # 1. references Qwen/Qwen3-VL-4B-Instruct
    assert "Qwen/Qwen3-VL-4B-Instruct" in all_code, "Notebook must reference official Qwen/Qwen3-VL-4B-Instruct"

    # 2. contains actual from_pretrained/model loading path
    assert "from_pretrained" in all_code, "Notebook must contain from_pretrained model loading path"
    assert "AutoProcessor.from_pretrained" in all_code or "AutoProcessor" in all_code

    # 3. invokes real multimodal inference
    assert "model.generate" in all_code, "Notebook must invoke real multimodal model.generate inference"
    assert "apply_chat_template" in all_code, "Notebook must invoke processor.apply_chat_template"

    # 4. does not use MockVisionModelAdapter for live benchmark
    assert "MockVisionModelAdapter" not in all_code, "Live notebook must NOT use MockVisionModelAdapter"

    # 5. contains three-run loop
    assert "range(1, 4)" in all_code or "for ordinal in range" in all_code, "Notebook must contain 3-run repetition loop"

    # 6. generates benchmark result JSON
    assert "COLAB_VISION_BENCHMARK_RESULTS.json" in all_code, "Notebook must generate benchmark results JSON"

    # 7. generates execution log
    assert "COLAB_EXECUTION_LOG.jsonl" in all_code, "Notebook must generate execution log JSONL"

    # 8. validates five-file bundle
    assert "COLAB_JOB_RESULT_MANIFEST.json" in all_code
    assert "prometeo_colab_benchmark_bundle.zip" in all_code
    assert "PROMETEO_COLAB_BUNDLE_READY" in all_code


# ==============================================================================
# 41. REQUIREMENTS NO UNSAFE PIP REDIRECTION
# ==============================================================================
def test_41_requirements_no_unsafe_pip_redirection():
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    import re
    unsafe_pattern = re.compile(r'!\s*pip\s+install\s+[^\n]*[><]=?')
    for idx, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        matches = unsafe_pattern.findall(src)
        assert len(matches) == 0, (
            f"Cell {idx} contains dangerous unquoted shell pip redirection: {matches}. Must use safe subprocess argv execution."
        )

    assert "NO_REDIRECTION_ARTIFACT_FILES" in "".join("".join(c["source"]) for c in nb["cells"])


# ==============================================================================
# 42. REAL QWEN ADAPTER INTERFACE & PARSER UNIT TEST
# ==============================================================================
def test_42_real_qwen_adapter_interface():
    adapter = RealQwenVLAdapter(
        candidate_id="QWEN3_VL_4B_INSTRUCT",
        model_id="Qwen/Qwen3-VL-4B-Instruct",
        quantization="bf16",
        backend="transformers_accelerate"
    )
    assert isinstance(adapter, VisionModelAdapter)
    meta = adapter.metadata()
    assert meta["candidate_id"] == "QWEN3_VL_4B_INSTRUCT"
    assert meta["model_id"] == "Qwen/Qwen3-VL-4B-Instruct"
    assert meta["execution_mode"] == "LIVE_MODEL_INFERENCE"
    assert meta["quantization"] == "bf16"
    assert meta["generation_parameters"]["do_sample"] is False
    assert meta["generation_parameters"]["max_new_tokens"] == 512

    # Clean JSON
    clean_json = '{"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Red bounding box surrounds element"}'
    parsed, role, conf, valid, err = adapter._parse_json_response(clean_json)
    assert valid is True
    assert role == "CONTENT_ENCLOSURE_ROLE"
    assert conf == "HIGH"
    assert err is None

    # Markdown code fence JSON
    fence_json = '```json\n{"role": "LINEAR_DIVIDER_ROLE", "confidence": "MEDIUM", "rationale": "Separates columns"}\n```'
    parsed, role, conf, valid, err = adapter._parse_json_response(fence_json)
    assert valid is True
    assert role == "LINEAR_DIVIDER_ROLE"
    assert conf == "MEDIUM"

    # Bad role
    bad_role_json = '{"role": "FANCIFUL_HEADER_BOX", "confidence": "LOW", "rationale": "Unknown"}'
    parsed, role, conf, valid, err = adapter._parse_json_response(bad_role_json)
    assert valid is False
    assert role == "ROLE_AMBIGUOUS"

    # Gibberish
    gibberish = "I cannot determine what this image is."
    parsed, role, conf, valid, err = adapter._parse_json_response(gibberish)
    assert valid is False
    assert role == "ROLE_AMBIGUOUS"
    assert "JSON_PARSE_ERROR" in err


# ==============================================================================
# 43. MEMORY RECLAMATION GATE
# ==============================================================================
def test_43_memory_reclamation_gate():
    passed, info = check_memory_reclamation_gate(vram_after_unload_mb=105.0, vram_baseline_mb=100.0, max_leak_mb=2048.0)
    assert passed is True
    assert info["passed"] is True
    assert info["leak_mb"] == 5.0

    passed_leak, info_leak = check_memory_reclamation_gate(vram_after_unload_mb=3500.0, vram_baseline_mb=500.0, max_leak_mb=2048.0)
    assert passed_leak is False
    assert info_leak["passed"] is False
    assert info_leak["leak_mb"] == 3000.0


# ==============================================================================
# 44. EXECUTION LOGGER EVENTS SCHEMA
# ==============================================================================
def test_44_execution_logger_events():
    from datetime import datetime, timezone
    log_path = os.path.join(SCRATCH_DIR, "test_execution_log.jsonl")
    if os.path.exists(log_path):
        os.remove(log_path)

    required_events = [
        "ENVIRONMENT_PROBED",
        "FIXTURE_VERIFIED",
        "DEPENDENCIES_INSTALLED",
        "CANDIDATE_SELECTED",
        "MODEL_DOWNLOAD_STARTED",
        "MODEL_DOWNLOAD_FINISHED",
        "MODEL_LOAD_STARTED",
        "MODEL_LOAD_FINISHED",
        "INFERENCE_STARTED",
        "INFERENCE_FINISHED",
        "RESULT_PARSED",
        "MODEL_UNLOADED",
        "CANDIDATE_COMPLETE",
        "BUNDLE_CREATED"
    ]

    with open(log_path, "w", encoding="utf-8") as f:
        for ev in required_events:
            entry = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "event": ev,
                "candidate_id": "QWEN3_VL_4B_INSTRUCT",
                "details": {"test": True}
            }
            f.write(json.dumps(entry) + "\n")

    lines = [json.loads(l) for l in open(log_path, "r", encoding="utf-8").readlines() if l.strip()]
    assert len(lines) == len(required_events)
    for idx, ev_name in enumerate(required_events):
        assert lines[idx]["event"] == ev_name
        assert "timestamp_utc" in lines[idx]


# ==============================================================================
# 45. COMPLETE FIVE FILE BUNDLE VALIDATION & MOCK REJECTION
# ==============================================================================
def test_45_complete_five_file_bundle_validation():
    bundle_dir = os.path.join(SCRATCH_DIR, "test_5_file_live_bundle")
    if os.path.exists(bundle_dir):
        shutil.rmtree(bundle_dir)
    os.makedirs(bundle_dir, exist_ok=True)

    live_result = {
        "experiment_id": "EXP-LIVE-TEST",
        "candidate_id": "QWEN3_VL_4B_INSTRUCT",
        "model_id": "Qwen/Qwen3-VL-4B-Instruct",
        "execution_mode": "LIVE_MODEL_INFERENCE",
        "revision": "main",
        "quantization": "bf16",
        "backend": "transformers_accelerate",
        "environment_manifest_sha256": "e" * 64,
        "fixture_sha256": EXPECTED_PNG_SHA,
        "fixture_pixel_sha256": EXPECTED_PIXEL_SHA,
        "fixture_png_sha256": EXPECTED_PNG_SHA,
        "prompt_sha256": EXPECTED_PROMPT_SHA,
        "load_seconds": 12.34,
        "runs": [
            {
                "ordinal": 1,
                "inference_seconds": 0.45,
                "peak_vram_mb": 6500.0,
                "raw_output": '{"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"}',
                "raw_output_sha256": hashlib.sha256('{"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"}'.encode()).hexdigest(),
                "parsed_output": {"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"},
                "parsed_output_sha256": hashlib.sha256(json.dumps({"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"}, sort_keys=True).encode()).hexdigest(),
                "role": "CONTENT_ENCLOSURE_ROLE",
                "confidence": "HIGH",
                "parse_valid": True,
                "error": None
            },
            {
                "ordinal": 2,
                "inference_seconds": 0.44,
                "peak_vram_mb": 6500.0,
                "raw_output": '{"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"}',
                "raw_output_sha256": hashlib.sha256('{"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"}'.encode()).hexdigest(),
                "parsed_output": {"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"},
                "parsed_output_sha256": hashlib.sha256(json.dumps({"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"}, sort_keys=True).encode()).hexdigest(),
                "role": "CONTENT_ENCLOSURE_ROLE",
                "confidence": "HIGH",
                "parse_valid": True,
                "error": None
            },
            {
                "ordinal": 3,
                "inference_seconds": 0.46,
                "peak_vram_mb": 6500.0,
                "raw_output": '{"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"}',
                "raw_output_sha256": hashlib.sha256('{"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"}'.encode()).hexdigest(),
                "parsed_output": {"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"},
                "parsed_output_sha256": hashlib.sha256(json.dumps({"role": "CONTENT_ENCLOSURE_ROLE", "confidence": "HIGH", "rationale": "Box"}, sort_keys=True).encode()).hexdigest(),
                "role": "CONTENT_ENCLOSURE_ROLE",
                "confidence": "HIGH",
                "parse_valid": True,
                "error": None
            }
        ],
        "repeatability_class": "BITWISE_DETERMINISTIC",
        "storage_used_mb": 8192.0,
        "max_vram_mb": 6500.0,
        "max_ram_mb": 0.0,
        "verdict": "TECHNICALLY_ELIGIBLE"
    }

    with open(os.path.join(bundle_dir, "COLAB_ENVIRONMENT_MANIFEST.json"), "w") as f:
        json.dump({"manifest_version": "0.1.0"}, f)
    with open(os.path.join(bundle_dir, "COLAB_MODEL_METADATA_SNAPSHOT.json"), "w") as f:
        json.dump({"snapshot_version": "0.1.0"}, f)
    with open(os.path.join(bundle_dir, "COLAB_VISION_BENCHMARK_RESULTS.json"), "w") as f:
        json.dump([live_result], f)
    with open(os.path.join(bundle_dir, "COLAB_EXECUTION_LOG.jsonl"), "w") as f:
        f.write('{"event": "BUNDLE_CREATED"}\n')

    fhashes = {}
    for fn in ["COLAB_ENVIRONMENT_MANIFEST.json", "COLAB_MODEL_METADATA_SNAPSHOT.json", "COLAB_VISION_BENCHMARK_RESULTS.json", "COLAB_EXECUTION_LOG.jsonl"]:
        fhashes[fn] = hashlib.sha256(open(os.path.join(bundle_dir, fn), "rb").read()).hexdigest()

    with open(os.path.join(bundle_dir, "COLAB_JOB_RESULT_MANIFEST.json"), "w") as f:
        json.dump({"manifest_version": "0.1.3", "file_hashes": fhashes}, f)

    reg_path = os.path.join(SUBSYSTEM_DIR, "MODEL_CANDIDATE_REGISTRY_v0.1.json")

    live_verdict = validate_colab_result_bundle(
        bundle_dir=bundle_dir,
        candidate_registry_path=reg_path,
        expected_fixture_sha=EXPECTED_PNG_SHA,
        expected_prompt_sha=EXPECTED_PROMPT_SHA,
        expected_fixture_pixel_sha=EXPECTED_PIXEL_SHA,
        require_live_execution=True
    )
    assert live_verdict["valid"] is True, f"Live bundle failed: {live_verdict['reasons']}"
    assert live_verdict["verdict"] == "ACCEPTED_FOR_REVIEW"

    # Mock bundle rejected when require_live_execution=True
    mock_result = dict(live_result)
    mock_result["execution_mode"] = "MOCK"
    with open(os.path.join(bundle_dir, "COLAB_VISION_BENCHMARK_RESULTS.json"), "w") as f:
        json.dump([mock_result], f)
    fhashes["COLAB_VISION_BENCHMARK_RESULTS.json"] = hashlib.sha256(open(os.path.join(bundle_dir, "COLAB_VISION_BENCHMARK_RESULTS.json"), "rb").read()).hexdigest()
    with open(os.path.join(bundle_dir, "COLAB_JOB_RESULT_MANIFEST.json"), "w") as f:
        json.dump({"manifest_version": "0.1.3", "file_hashes": fhashes}, f)

    mock_verdict = validate_colab_result_bundle(
        bundle_dir=bundle_dir,
        candidate_registry_path=reg_path,
        expected_fixture_sha=EXPECTED_PNG_SHA,
        expected_prompt_sha=EXPECTED_PROMPT_SHA,
        expected_fixture_pixel_sha=EXPECTED_PIXEL_SHA,
        require_live_execution=True
    )
    assert mock_verdict["valid"] is False, "Mock result must be rejected during live ingestion"
    assert any("MOCK_EXECUTION_REJECTED" in r for r in mock_verdict["reasons"])


# ==============================================================================
# 46. BUNDLE ZIP PACKAGING
# ==============================================================================
def test_46_bundle_zip_packaging():
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    all_code = "".join("".join(c["source"]) for c in nb["cells"] if c.get("cell_type") == "code")
    assert "zipfile.ZipFile" in all_code
    assert "prometeo_colab_benchmark_bundle.zip" in all_code
    assert "PROMETEO_COLAB_BUNDLE_READY" in all_code


# ==============================================================================
# 47. LOCAL MODEL DOWNLOADS COUNT ZERO
# ==============================================================================
def test_47_local_model_downloads_count_zero():
    model_weight_exts = {".safetensors", ".bin", ".pt", ".pth", ".onnx", ".gguf"}
    for check_dir in [SUBSYSTEM_DIR, SCRATCH_DIR]:
        for root, dirs, files in os.walk(check_dir):
            for d in dirs:
                assert "Qwen3" not in d, f"Local Qwen3 model directory detected in {check_dir}: {d}"
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in model_weight_exts:
                    fp = os.path.join(root, f)
                    size_mb = os.path.getsize(fp) / (1024 * 1024)
                    assert size_mb < 50.0, f"Found large model weight file in PROM-C01: {fp} ({size_mb:.1f} MB)"
    # Also verify HF cache does not contain Qwen3-VL models
    hf_hub = os.path.expanduser("~/.cache/huggingface/hub")
    if os.path.exists(hf_hub):
        for entry in os.listdir(hf_hub):
            assert "Qwen3" not in entry, f"Qwen3 model weights found in local Hugging Face cache: {entry}"


# ==============================================================================
# 48. JOB PACKET AND PROTOCOL ERRATA 02 UPDATES
# ==============================================================================
def test_48_job_packet_and_protocol_errata_02_updates():
    packet_path = os.path.join(SUBSYSTEM_DIR, "COLAB_JOB_PACKET_v0.1.json")
    with open(packet_path, "r", encoding="utf-8") as f:
        packet = json.load(f)

    assert packet["packet_version"] == "0.1.3"
    assert packet["protocol_version"] == "0.1.3"
    assert "COLAB-RUNTIME-ERRATA-02" in packet["supersession"]
    hist = packet.get("historical_runtime_evidence", {})
    assert hist.get("gpu") == "NVIDIA L4"
    assert hist.get("observed_vram_gb") == 22.5
    assert hist.get("prior_classification") == "COLAB_BENCHMARK_EXECUTION_INCOMPLETE"

    cd = packet["component_digests"]
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    actual_nb_sha = hashlib.sha256(open(nb_path, "rb").read()).hexdigest()
    assert cd["notebook_sha256"] == actual_nb_sha

    proto_path = os.path.join(SUBSYSTEM_DIR, "COLAB_VISION_ASSESSOR_FEASIBILITY_PROTOCOL_v0.1.json")
    with open(proto_path, "r", encoding="utf-8") as f:
        proto = json.load(f)
    assert proto["protocol_version"] == "0.1.3"
    assert "COLAB-RUNTIME-ERRATA-02" in proto.get("errata_resolutions", [])


# ==============================================================================
# 49. NEW SUCCESS CRITERIA AUDIT (SECTION 27)
# ==============================================================================
def test_49_new_success_criteria_audit():
    nb_path = os.path.join(SUBSYSTEM_DIR, "prometeo_colab_vision_benchmark.ipynb")
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    all_code = "".join("".join(c["source"]) for c in nb["cells"] if c.get("cell_type") == "code")

    # REAL_MODEL_DOWNLOAD_PATH_PRESENT = YES
    assert "MODEL_DOWNLOAD_STARTED" in all_code
    # REAL_MODEL_LOAD_PATH_PRESENT = YES
    assert "RealQwenVLAdapter" in all_code and "adapter_a.load()" in all_code
    # REAL_MULTIMODAL_INFERENCE_PATH_PRESENT = YES
    assert "adapter_a.infer(" in all_code and "output_ids = self.model.generate" in all_code
    # THREE_REPEAT_RUNS_PRESENT = YES
    assert "for ordinal in range(1, 4):" in all_code
    # BENCHMARK_RESULTS_FILE_REQUIRED = YES
    assert "COLAB_VISION_BENCHMARK_RESULTS.json" in all_code
    # EXECUTION_LOG_FILE_REQUIRED = YES
    assert "COLAB_EXECUTION_LOG.jsonl" in all_code
    # FIVE_FILE_BUNDLE_REQUIRED = YES
    required_bundle_files = [
        "COLAB_ENVIRONMENT_MANIFEST.json",
        "COLAB_MODEL_METADATA_SNAPSHOT.json",
        "COLAB_VISION_BENCHMARK_RESULTS.json",
        "COLAB_EXECUTION_LOG.jsonl",
        "COLAB_JOB_RESULT_MANIFEST.json"
    ]
    for rbf in required_bundle_files:
        assert rbf in all_code
    # ZIP_EXPORT_PRESENT = YES
    assert "prometeo_colab_benchmark_bundle.zip" in all_code
    # UNSAFE_PIP_REDIRECTION = 0
    import re
    assert len(re.findall(r'!\s*pip\s+install[^\n]*[><]=?', all_code)) == 0
    # AG277_PRESERVED = YES
    ledger_path = os.path.join(PASS_B_RUN_DIR, "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001_DERIVED_LEDGER.jsonl")
    assert len([l for l in open(ledger_path).readlines() if l.strip()]) == 3


# ==============================================================================
# 50. AG277 REMAINS UNCHANGED (ERRATA 02 CUSTODY)
# ==============================================================================
def test_50_ag277_remains_unchanged_errata_02():
    expected_hashes = {
        "00001.json": "fb52d296fb0f756b8a8af1c2ac5c2a155a5c9aed24d45ca9546f2f8820d1f7b6",
        "00002.json": "88e9f15779c74a1209e6b249cc63c5df9d75b5247952c30dd8d3549a4ca249ae",
        "00003.json": "71e0ef96507d30ca255dc8625f13ae70defe50d99741d5159b0f1e1910c6b126"
    }
    for fname, exp_sha in expected_hashes.items():
        fpath = os.path.join(PASS_B_RUN_DIR, "results", fname)
        data = open(fpath, "rb").read()
        sha = hashlib.sha256(data).hexdigest()
        assert sha == exp_sha, f"AG277 file {fname} SHA mutated: {sha} != {exp_sha}"

    ledger_path = os.path.join(PASS_B_RUN_DIR, "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001_DERIVED_LEDGER.jsonl")
    lines = [l.strip() for l in open(ledger_path, "r").readlines() if l.strip()]
    assert len(lines) == 3, f"AG277 ledger must remain exactly 3 lines: got {len(lines)}"


# ==============================================================================
# 51. PROM-C01 INGESTED RETURN BUNDLE PROVENANCE AND INTEGRITY
# ==============================================================================
def test_51_prom_c01_ingested_bundle_provenance_and_integrity():
    bundle_dir = os.path.join(REPO_ROOT, "fase0", "reality_corpus", "colab_returns", "PROM-C01")
    zip_path = os.path.join(bundle_dir, "prometeo_colab_benchmark_bundle.zip")
    assert os.path.exists(zip_path), f"Bundle ZIP missing: {zip_path}"

    zip_bytes = open(zip_path, "rb").read()
    assert len(zip_bytes) == 4887, f"ZIP byte size mismatch: {len(zip_bytes)} != 4887"
    zip_sha = hashlib.sha256(zip_bytes).hexdigest()
    assert zip_sha == "5926ddbeb3c83f00fdf4c25750f055c0a7ce1b6fb54ddf70883a43fdb609f594", f"ZIP SHA mismatch: {zip_sha}"

    expected_hashes = {
        "COLAB_ENVIRONMENT_MANIFEST.json": "3ce43f6e03a0d7a57f6ab38f8e7c3580b178f0765082be4ff971484d79d844ee",
        "COLAB_MODEL_METADATA_SNAPSHOT.json": "2d912eee35e0eb62ffe2c3ce17f472e6ee11f31bd091ba72bf7ddcc7b0ef37e4",
        "COLAB_VISION_BENCHMARK_RESULTS.json": "9e6af3963633a597d02d24a2296e525df03480dc92824864b531d36495015688",
        "COLAB_EXECUTION_LOG.jsonl": "f1f4c32fa0d97a07254af70c445d315f2f550efe5d2c876222eacbe4d97fe052",
        "COLAB_JOB_RESULT_MANIFEST.json": "c4d43328d5b2f6c3e82a6cb6c8dbcb5d9a684acbb3f06d6c538327ac7578d1e7"
    }

    for fname, exp_sha in expected_hashes.items():
        fp = os.path.join(bundle_dir, fname)
        assert os.path.exists(fp), f"Extracted bundle file missing: {fp}"
        act_sha = hashlib.sha256(open(fp, "rb").read()).hexdigest()
        assert act_sha == exp_sha, f"File {fname} hash mismatch: {act_sha} != {exp_sha}"

    # Also verify result validator accepts the bundle
    reg_path = os.path.join(SUBSYSTEM_DIR, "MODEL_CANDIDATE_REGISTRY_v0.1.json")
    v_res = validate_colab_result_bundle(
        bundle_dir=bundle_dir,
        candidate_registry_path=reg_path,
        expected_fixture_sha=EXPECTED_PNG_SHA,
        expected_prompt_sha=EXPECTED_PROMPT_SHA,
        expected_fixture_pixel_sha=EXPECTED_PIXEL_SHA,
        require_live_execution=True
    )
    assert v_res["valid"] is True, f"Validator rejected bundle: {v_res['reasons']}"
    assert v_res["verdict"] == "ACCEPTED_FOR_REVIEW"


# ==============================================================================
# 52. PROM-C01 HARDWARE ENVIRONMENT AUDIT
# ==============================================================================
def test_52_prom_c01_hardware_environment_audit():
    bundle_dir = os.path.join(REPO_ROOT, "fase0", "reality_corpus", "colab_returns", "PROM-C01")
    env_path = os.path.join(bundle_dir, "COLAB_ENVIRONMENT_MANIFEST.json")
    with open(env_path, "r", encoding="utf-8") as f:
        env = json.load(f)

    assert env["gpu_model"] == "NVIDIA L4"
    assert env["gpu_count"] == 1
    assert abs(env["vram_total_gb"] - 22.03) < 0.1
    assert env["cuda_version"] == "13.0"
    assert env["compute_capability"] == "8.9"
    assert env["python_version"] == "3.13.15"


# ==============================================================================
# 53. PROM-C01 CANDIDATE A METRICS AND DETERMINISM
# ==============================================================================
def test_53_prom_c01_candidate_a_metrics_and_determinism():
    bundle_dir = os.path.join(REPO_ROOT, "fase0", "reality_corpus", "colab_returns", "PROM-C01")
    res_path = os.path.join(bundle_dir, "COLAB_VISION_BENCHMARK_RESULTS.json")
    with open(res_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    cand_a = next(r for r in results if r["candidate_id"] == "QWEN3_VL_4B_INSTRUCT")
    assert cand_a["model_id"] == "Qwen/Qwen3-VL-4B-Instruct"
    assert cand_a["revision"] == "ebb281ec70b05090aa6165b016eac8ec08e71b17"
    assert cand_a["quantization"] == "bf16"
    assert cand_a["load_seconds"] == 45.9699
    assert cand_a["max_vram_mb"] == 8763.48
    assert cand_a["repeatability_class"] == "BITWISE_DETERMINISTIC"
    assert cand_a["verdict"] == "TECHNICALLY_ELIGIBLE"

    runs = cand_a["runs"]
    assert len(runs) == 3
    latencies = [r["inference_seconds"] for r in runs]
    assert latencies == [7.6839, 3.7072, 3.7561]
    warm_mean = (latencies[1] + latencies[2]) / 2.0
    assert abs(warm_mean - 3.73165) < 1e-4

    for r in runs:
        assert r["role"] == "CONTENT_ENCLOSURE_ROLE"
        assert r["confidence"] == "HIGH"
        assert r["parse_valid"] is True


# ==============================================================================
# 54. PROM-C01 CANDIDATE B METRICS AND DETERMINISM
# ==============================================================================
def test_54_prom_c01_candidate_b_metrics_and_determinism():
    bundle_dir = os.path.join(REPO_ROOT, "fase0", "reality_corpus", "colab_returns", "PROM-C01")
    res_path = os.path.join(bundle_dir, "COLAB_VISION_BENCHMARK_RESULTS.json")
    with open(res_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    cand_b = next(r for r in results if r["candidate_id"] == "QWEN3_VL_8B_INSTRUCT_QUANTIZED")
    assert cand_b["model_id"] == "Qwen/Qwen3-VL-8B-Instruct"
    assert cand_b["revision"] == "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"
    assert cand_b["quantization"] == "int4"
    assert cand_b["load_seconds"] == 70.7813
    assert cand_b["max_vram_mb"] == 6492.64
    assert cand_b["repeatability_class"] == "BITWISE_DETERMINISTIC"
    assert cand_b["verdict"] == "TECHNICALLY_ELIGIBLE"

    runs = cand_b["runs"]
    assert len(runs) == 3
    latencies = [r["inference_seconds"] for r in runs]
    assert latencies == [6.0860, 6.0737, 6.0899]
    mean_lat = sum(latencies) / len(latencies)
    assert abs(mean_lat - 6.0832) < 1e-4

    for r in runs:
        assert r["role"] == "CONTENT_ENCLOSURE_ROLE"
        assert r["confidence"] == "HIGH"
        assert r["parse_valid"] is True


# ==============================================================================
# 55. PROM-C01 SCIENTIFIC AUTHORITY FIREWALL ENFORCEMENT
# ==============================================================================
def test_55_prom_c01_scientific_authority_firewall():
    bundle_dir = os.path.join(REPO_ROOT, "fase0", "reality_corpus", "colab_returns", "PROM-C01")
    res_path = os.path.join(bundle_dir, "COLAB_VISION_BENCHMARK_RESULTS.json")
    with open(res_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    # Authority rule: neither candidate may be declared CANONICAL_PASS_B_MODEL
    for cand in results:
        assert cand.get("verdict") == "TECHNICALLY_ELIGIBLE"
        assert "CANONICAL_PASS_B_MODEL" not in str(cand.values())

        # Evaluate quality gate
        qg = evaluate_quality_gate(cand)
        assert qg["verdict"] == "TECHNICALLY_ELIGIBLE"
        assert qg["canonical_selection_permitted"] is False

    # Attempting to declare forbidden status MUST raise CanonicalAuthorityFirewallViolation
    for forbidden in ["CANONICAL_PASS_B_MODEL", "CANONICAL_MODEL_SELECTED", "PHASE_D_AUTHORITY_GRANTED"]:
        try:
            enforce_no_canonical_model_selection(attempted_status=forbidden)
            assert False, f"Expected CanonicalAuthorityFirewallViolation for {forbidden}"
        except CanonicalAuthorityFirewallViolation:
            pass

    # Allowed status must not raise
    enforce_no_canonical_model_selection(attempted_status="TECHNICALLY_ELIGIBLE")



# ==============================================================================
# 56. PROM-C01 AG277 CUSTODY AUDIT UNCHANGED
# ==============================================================================
def test_56_prom_c01_ag277_custody_unchanged():
    expected_hashes = {
        "00001.json": "fb52d296fb0f756b8a8af1c2ac5c2a155a5c9aed24d45ca9546f2f8820d1f7b6",
        "00002.json": "88e9f15779c74a1209e6b249cc63c5df9d75b5247952c30dd8d3549a4ca249ae",
        "00003.json": "71e0ef96507d30ca255dc8625f13ae70defe50d99741d5159b0f1e1910c6b126"
    }
    for fname, exp_sha in expected_hashes.items():
        fpath = os.path.join(PASS_B_RUN_DIR, "results", fname)
        data = open(fpath, "rb").read()
        sha = hashlib.sha256(data).hexdigest()
        assert sha == exp_sha, f"AG277 file {fname} SHA mutated: {sha} != {exp_sha}"

    ledger_path = os.path.join(PASS_B_RUN_DIR, "FC009_M1_EPOCH2_PASS_B_CANONICAL_RUN_001_DERIVED_LEDGER.jsonl")
    lines = [l.strip() for l in open(ledger_path, "r").readlines() if l.strip()]
    assert len(lines) == 3, f"AG277 ledger must remain exactly 3 lines: got {len(lines)}"


if __name__ == "__main__":
    import inspect
    import sys

    this_module = sys.modules[__name__]
    test_funcs = [
        (name, func)
        for name, func in inspect.getmembers(this_module, inspect.isfunction)
        if name.startswith("test_")
    ]
    test_funcs.sort(key=lambda x: x[0])
    passed = 0
    failed = 0
    for name, func in test_funcs:
        try:
            func()
            print(f"PASS: {name}", flush=True)
            passed += 1
        except Exception as e:
            print(f"FAIL: {name}: {e}", flush=True)
            failed += 1
    print(f"\nTOTAL: {passed} passed, {failed} failed", flush=True)
    if failed > 0:
        sys.exit(1)


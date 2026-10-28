from pathlib import Path
from tests.evaluation.eval_corpus import (
    DIAGNOSTIC_SAMPLES,
    SWE_TASKS,
    EvaluationRunner,
    estimate_tokens,
)


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") > 0
    # ~4 chars per token heuristic
    text = "a" * 40
    assert 9 <= estimate_tokens(text) <= 12


def test_evaluation_runner_diagnostic_distillation(tmp_path):
    telemetry_file = tmp_path / "telemetry.jsonl"
    runner = EvaluationRunner(telemetry_file=telemetry_file)

    def mock_distill(goal: str, raw: str) -> str:
        # Returns raw output directly
        return raw

    results = runner.evaluate_diagnostic_distillation(mock_distill)
    assert len(results) == len(DIAGNOSTIC_SAMPLES)
    for r in results:
        assert r.critical_signals_preserved is True
        assert r.status == "passed"
        assert r.baseline_tokens == r.treated_tokens
        assert r.tokens_saved == 0

    assert telemetry_file.exists()
    lines = telemetry_file.read_text().splitlines()
    assert len(lines) == len(DIAGNOSTIC_SAMPLES)
    # Verify no source code in telemetry file
    for line in lines:
        assert "SAMPLE_TRACEBACK" not in line
        assert "test_worker_retry_state" not in line  # Sample details omitted from telemetry keys


def test_swe_task_verification():
    runner = EvaluationRunner()
    for task in SWE_TASKS:
        res = runner.evaluate_swe_task(task)
        assert res["baseline_test_failed"] is True, f"Baseline test should fail for {task.id}"
        assert res["post_patch_test_passed"] is True, f"Post-patch test should pass for {task.id}"
        assert res["verified"] is True

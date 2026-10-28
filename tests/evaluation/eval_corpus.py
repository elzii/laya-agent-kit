"""Harness-neutral evaluation corpus and paired benchmark runner for Laya Agent Kit.

Measures:
1. Input tokens (to Laya and to host coding model)
2. Output tokens (distilled output returned to host coding model)
3. Latency (duration in milliseconds)
4. Task completion & behavioral correctness (via automated pytest)
5. Zero source code in telemetry logs (strict privacy model)
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def estimate_tokens(text: str) -> int:
    """Estimates tokens using standard 4-chars/token heuristic, or tiktoken if available."""
    if not text:
        return 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text, disallowed_special=()))
    except Exception:
        # Standard character-based approximation for code and English text
        return max(1, math.ceil(len(text) / 4.0))


@dataclass
class DiagnosticSample:
    id: str
    category: str
    goal: str
    raw_output: str
    critical_signals: List[str]  # Substrings that MUST be preserved in distilled output


@dataclass
class CodeRegionSample:
    id: str
    file_path: str
    task: str
    expected_line_ranges: List[tuple[int, int]]  # Target line intervals that should be covered


@dataclass
class SWETask:
    id: str
    description: str
    setup_files: Dict[str, str]  # path -> content
    failing_test_command: str     # Baseline test that MUST fail initially
    patch: Dict[str, str]         # path -> new_content (or replacement)
    passing_test_command: str     # Post-patch test that MUST pass


@dataclass
class BenchmarkRunResult:
    timestamp: float
    workload: str
    sample_id: str
    baseline_tokens: int
    treated_tokens: int
    tokens_saved: int
    savings_pct: float
    duration_ms: float
    critical_signals_preserved: bool
    status: str
    error: Optional[str] = None


# --- 1. Realistic Diagnostic Workloads ---

SAMPLE_TRACEBACK = """============================= test session starts ==============================
platform darwin -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0
rootdir: /workspace/project
configfile: pyproject.toml
collected 14 items

tests/test_api.py ..........                                             [ 71%]
tests/test_worker.py .F..                                                [100%]

=================================== FAILURES ===================================
___________________________ test_worker_retry_state ____________________________

    def test_worker_retry_state():
        worker = SyncWorker(max_retries=3)
        job = {"id": "job-123", "uuid": UUID("c9bf9e57-1685-4c89-bafb-ff5af830be8a")}
>       result = worker.serialize_job_state(job)

tests/test_worker.py:45: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
src/worker.py:112: in serialize_job_state
    return json.dumps(envelope)
/usr/local/lib/python3.11/json/__init__.py:231: in dumps
    return _default_encoder.encode(obj)
/usr/local/lib/python3.11/json/encoder.py:199: in encode
    chunks = self.iterencode(o, _one_shot=True)
/usr/local/lib/python3.11/json/encoder.py:257: in iterencode
    return _iterencode(o, 0)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

o = UUID('c9bf9e57-1685-4c89-bafb-ff5af830be8a')

    def default(o):
>       raise TypeError(f"Object of type '{o.__class__.__name__}' is not JSON serializable")
E       TypeError: Object of type 'UUID' is not JSON serializable

/usr/local/lib/python3.11/json/encoder.py:179: TypeError
----------------------------- Captured stderr call -----------------------------
[2026-10-28 11:20:01] [worker] [ERROR] Failed to serialize job payload for job-123
[2026-10-28 11:20:01] [worker] [DEBUG] Envelope dump: {'id': 'job-123', 'attempts': 1}
=========================== short test summary info ============================
FAILED tests/test_worker.py::test_worker_retry_state - TypeError: Object of type 'UUID' is not JSON serializable
========================= 1 failed, 13 passed in 0.42s =========================
"""

SAMPLE_BUILD_LOG = """clang -c -Wall -Wextra -O2 -Iinclude src/core.c -o build/core.o
clang -c -Wall -Wextra -O2 -Iinclude src/parser.c -o build/parser.o
clang -c -Wall -Wextra -O2 -Iinclude src/protocol.c -o build/protocol.o
src/protocol.c:78:12: error: implicit declaration of function 'atomic_load_explicit' is invalid in C99 [-Werror,-Wimplicit-function-declaration]
   78 |     return atomic_load_explicit(&conn->state, memory_order_relaxed);
      |            ^
src/protocol.c:78:47: error: use of undeclared identifier 'memory_order_relaxed'
   78 |     return atomic_load_explicit(&conn->state, memory_order_relaxed);
      |                                               ^
src/protocol.c:78:12: note: did you mean 'atomic_load'?
   78 |     return atomic_load_explicit(&conn->state, memory_order_relaxed);
      |            ^~~~~~~~~~~~~~~~~~~~
      |            atomic_load
2 errors generated.
make: *** [Makefile:24: build/protocol.o] Error 1
"""

DIAGNOSTIC_SAMPLES: List[DiagnosticSample] = [
    DiagnosticSample(
        id="pytest_typeerror_traceback",
        category="test_failure",
        goal="Identify cause of test_worker_retry_state failure",
        raw_output=SAMPLE_TRACEBACK,
        critical_signals=[
            "FAILED tests/test_worker.py::test_worker_retry_state",
            "TypeError: Object of type 'UUID' is not JSON serializable",
            "src/worker.py:112: in serialize_job_state",
        ],
    ),
    DiagnosticSample(
        id="c_compiler_error",
        category="build_failure",
        goal="Identify missing headers or compilation error in src/protocol.c",
        raw_output=SAMPLE_BUILD_LOG,
        critical_signals=[
            "src/protocol.c:78:12: error: implicit declaration of function 'atomic_load_explicit'",
            "2 errors generated.",
            "make: *** [Makefile:24: build/protocol.o] Error 1",
        ],
    ),
]

# --- 2. SWE Micro-Tasks with Automated Pytest Verification ---

SWE_TASKS: List[SWETask] = [
    SWETask(
        id="swe_json_uuid_serialization",
        description="Fix TypeError in serialize_envelope when UUID is passed",
        setup_files={
            "src/serializer.py": (
                "import json\n"
                "from uuid import UUID\n\n"
                "def serialize_envelope(payload: dict) -> str:\n"
                "    return json.dumps(payload)\n"
            ),
            "tests/test_serializer.py": (
                "from uuid import UUID\n"
                "from src.serializer import serialize_envelope\n\n"
                "def test_serialize_uuid():\n"
                "    data = {'id': UUID('12345678-1234-5678-1234-567812345678'), 'name': 'test'}\n"
                "    res = serialize_envelope(data)\n"
                "    assert '12345678-1234-5678-1234-567812345678' in res\n"
            ),
        },
        failing_test_command="python3 -m pytest -q tests/test_serializer.py",
        patch={
            "src/serializer.py": (
                "import json\n"
                "from uuid import UUID\n\n"
                "def serialize_envelope(payload: dict) -> str:\n"
                "    return json.dumps(payload, default=str)\n"
            ),
        },
        passing_test_command="python3 -m pytest -q tests/test_serializer.py",
    ),
]


class EvaluationRunner:
    """Runs repeatable baseline and treatment benchmarks."""

    def __init__(self, telemetry_file: Optional[Path] = None):
        self.telemetry_file = telemetry_file

    def record_telemetry(self, result: BenchmarkRunResult) -> None:
        """Records run metrics without sensitive source code or prompts."""
        if not self.telemetry_file:
            return
        self.telemetry_file.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": result.timestamp,
            "workload": result.workload,
            "sample_id": result.sample_id,
            "baseline_tokens": result.baseline_tokens,
            "treated_tokens": result.treated_tokens,
            "tokens_saved": result.tokens_saved,
            "savings_pct": result.savings_pct,
            "duration_ms": result.duration_ms,
            "critical_signals_preserved": result.critical_signals_preserved,
            "status": result.status,
            "error": result.error,
        }
        with open(self.telemetry_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def evaluate_diagnostic_distillation(
        self,
        distill_func: Callable[[str, str], Any],
        samples: Optional[List[DiagnosticSample]] = None,
    ) -> List[BenchmarkRunResult]:
        samples = samples or DIAGNOSTIC_SAMPLES
        results = []
        for sample in samples:
            t0 = time.perf_counter()
            baseline_tokens = estimate_tokens(sample.raw_output)
            error_msg = None
            try:
                treated = distill_func(sample.goal, sample.raw_output)
                if isinstance(treated, dict) and treated.get("fallback"):
                    treated_text = sample.raw_output
                elif isinstance(treated, dict) and "content" in treated:
                    treated_text = treated["content"]
                else:
                    treated_text = str(treated)
            except Exception as exc:
                treated_text = sample.raw_output
                error_msg = str(exc)

            duration_ms = (time.perf_counter() - t0) * 1000.0
            treated_tokens = estimate_tokens(treated_text)
            saved = max(0, baseline_tokens - treated_tokens)
            savings_pct = (saved / baseline_tokens * 100.0) if baseline_tokens > 0 else 0.0

            # Verify critical signals are preserved
            preserved = all(sig in treated_text for sig in sample.critical_signals)
            status = "passed" if preserved and error_msg is None else "degraded"

            res = BenchmarkRunResult(
                timestamp=time.time(),
                workload="diagnostic_distillation",
                sample_id=sample.id,
                baseline_tokens=baseline_tokens,
                treated_tokens=treated_tokens,
                tokens_saved=saved,
                savings_pct=round(savings_pct, 2),
                duration_ms=round(duration_ms, 2),
                critical_signals_preserved=preserved,
                status=status,
                error=error_msg,
            )
            self.record_telemetry(res)
            results.append(res)
        return results

    def evaluate_swe_task(self, task: SWETask) -> Dict[str, Any]:
        """Validates that baseline test fails before patch and passes after patch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            # Setup files
            for rel_path, content in task.setup_files.items():
                dest = workdir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")

            # 1. Baseline test must FAIL
            p1 = subprocess.run(
                task.failing_test_command,
                shell=True,
                cwd=workdir,
                capture_output=True,
                text=True,
            )
            baseline_failed = p1.returncode != 0

            # 2. Apply patch
            for rel_path, patch_content in task.patch.items():
                dest = workdir / rel_path
                dest.write_text(patch_content, encoding="utf-8")

            # 3. Post-patch test must PASS
            p2 = subprocess.run(
                task.passing_test_command,
                shell=True,
                cwd=workdir,
                capture_output=True,
                text=True,
            )
            post_patch_passed = p2.returncode == 0

            return {
                "task_id": task.id,
                "baseline_test_failed": baseline_failed,
                "post_patch_test_passed": post_patch_passed,
                "verified": baseline_failed and post_patch_passed,
            }


def main():
    print("=== Laya Agent Kit Evaluation Corpus ===")
    runner = EvaluationRunner(telemetry_file=Path(".laya/telemetry_benchmark.jsonl"))

    # Baseline passthrough evaluation
    def passthrough(goal, raw):
        return raw

    results = runner.evaluate_diagnostic_distillation(passthrough)
    for r in results:
        print(f"Sample: {r.sample_id} | Base Tokens: {r.baseline_tokens} | Preserved: {r.critical_signals_preserved}")

    # SWE Task verification
    for task in SWE_TASKS:
        res = runner.evaluate_swe_task(task)
        print(f"SWE Task: {task.id} | Baseline Failed: {res['baseline_test_failed']} | Post-Patch Passed: {res['post_patch_test_passed']}")


if __name__ == "__main__":
    main()

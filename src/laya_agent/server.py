#!/usr/bin/env python3
"""Laya FastMCP bridge for coding-agent triage, retrieval, and verification.

Compatibility: preserves the original tool names and /v1/systemone wire format.
Safety model: decision-service failures are reported as indeterminate, not silently
relabelled as successful verification. Search and file tools remain local.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("laya-engine")

LAYA_BASE = os.environ.get("LAYA_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
LAYA_ENDPOINT = f"{LAYA_BASE}/v1/systemone"
LAYA_BATCH = f"{LAYA_BASE}/v1/systemone/batch"
LAYA_HEALTH = f"{LAYA_BASE}/health"
REQUEST_TIMEOUT = float(os.environ.get("LAYA_REQUEST_TIMEOUT", "15"))
MAX_STATE_CHARS = int(os.environ.get("LAYA_MAX_STATE_CHARS", "12000"))
MAX_BATCH_ITEMS = int(os.environ.get("LAYA_MAX_BATCH_ITEMS", "128"))


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _score(answer: Any, key: str) -> float | None:
    """Return a finite score, or None when the response is malformed."""
    try:
        value = float(answer["answers"][key]["noul"])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) and 0.0 <= value <= 1.0 else None


async def _post_json(
    url: str, payload: dict[str, Any] | list[dict[str, Any]], timeout: float | None = None
) -> Any:
    """Shared HTTP client and error path for all Laya calls."""
    async with httpx.AsyncClient(timeout=timeout or REQUEST_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


async def _decide(state: str, questions: dict[str, Any]) -> dict[str, Any]:
    return await _post_json(
        LAYA_ENDPOINT,
        {"state": state[:MAX_STATE_CHARS], "questions": questions},
    )


async def _batch_decide(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        return []
    if len(items) > MAX_BATCH_ITEMS:
        raise ValueError(
            f"Batch has {len(items)} items; configured maximum is {MAX_BATCH_ITEMS}."
        )
    # Preserve the upstream batch wire format used by the original implementation.
    result = await _post_json(LAYA_BATCH, items, timeout=max(REQUEST_TIMEOUT, 20.0))
    if not isinstance(result, list) or len(result) != len(items):
        raise ValueError("Laya batch response shape/count did not match the request.")
    return result


def _indeterminate(tool: str, error: Exception) -> str:
    """Structured error: callers must not mistake service failure for approval."""
    return _json({
        "status": "indeterminate",
        "tool": tool,
        "error": f"{type(error).__name__}: {error}",
        "fallback_required": True,
    })


# ---------------------------------------------------------------------------
# 1. Candidate file gating
# ---------------------------------------------------------------------------
@mcp.tool()
async def filter_candidate_files(
    task: str, file_paths: list[str], threshold: float = 0.60
) -> list[str]:
    """Rank candidate paths before reading files. A service failure returns all paths.

    This is a retrieval optimization, not an authorization/security boundary.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    if not file_paths:
        return []
    questions = {
        path: {
            "type": "noul",
            "instructions": f"Is this file path relevant to completing this task: {task!r}?",
        }
        for path in file_paths
    }
    try:
        data = await _decide(task, questions)
        answers = data.get("answers", {})
        # Keep unknown/malformed paths rather than silently losing potential evidence.
        kept = []
        for path in file_paths:
            meta = answers.get(path, {})
            try:
                score = float(meta.get("noul"))
            except (TypeError, ValueError):
                kept.append(path)
                continue
            if not math.isfinite(score) or score >= threshold:
                kept.append(path)
        return kept
    except Exception as err:
        sys.stderr.write(f"[laya-mcp warning] filter_candidate_files: {err}\n")
        return file_paths


# ---------------------------------------------------------------------------
# 2. Fast local symbol search
# ---------------------------------------------------------------------------
@mcp.tool()
async def fast_symbol_search(
    symbol: str, path: str = ".", file_glob: str = "", max_results: int = 10
) -> str:
    """Search text with ripgrep asynchronously; avoids blocking the MCP event loop."""
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return f"Error: Path {path} does not exist."
    if max_results < 1:
        return "Error: max_results must be at least 1."
    rg_bin = shutil.which("rg")
    if not rg_bin:
        return "Error: ripgrep ('rg') is not installed or not found on PATH."
    cmd = [
        rg_bin, "--smart-case", "--max-count", "3", "--max-columns", "150",
        "--color", "never", "--line-number", "--no-heading",
        "--hidden", "--glob", "!.git/**", "--glob", "!**/.venv/**",
        "--glob", "!**/node_modules/**", "--glob", "!**/__pycache__/**",
    ]
    if file_glob:
        cmd.extend(["-g", file_glob])
    cmd.extend(["--", symbol, str(target)])
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        output = stdout.decode("utf-8", errors="replace")
        if proc.returncode not in (0, 1):
            return f"Search error (exit {proc.returncode}): {stderr.decode(errors='replace')[:1000]}"
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not lines:
            return f"No occurrences of {symbol!r} found in {path}."
        shown = lines[:max_results]
        if len(lines) > max_results:
            shown.append(f"[... output truncated; at least {len(lines) - max_results} additional matches ...]")
        return "\n".join(shown)
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return f"Search timed out for {symbol!r} in {path}."
    except Exception as err:
        return f"Search error: {type(err).__name__}: {err}"


# ---------------------------------------------------------------------------
# 3. Diagnostic output distillation
# ---------------------------------------------------------------------------
@mcp.tool()
async def distill_command_output(
    goal: str, raw_output: str, threshold: float = 0.55, max_lines: int = 12
) -> str:
    """Keep lines relevant to a diagnostic goal; retain a bounded fallback excerpt."""
    if not 0.0 <= threshold <= 1.0:
        return "Error: threshold must be between 0 and 1."
    lines = [line.rstrip() for line in raw_output.splitlines() if line.strip()]
    if len(lines) <= max_lines:
        return raw_output
    payload = [
        {"state": line[:1000], "questions": {"relevant": {
            "type": "noul",
            "instructions": f"Does this line provide evidence about: {goal!r}?",
        }}}
        for line in lines
    ]
    try:
        results = await _batch_decide(payload)
        kept = []
        for i, result in enumerate(results):
            score = _score(result, "relevant")
            if score is not None and score >= threshold:
                kept.append(lines[i])
        if not kept:
            # No evidence is not proof that every line is irrelevant.
            return "\n".join(lines[:6] + ["[... omitted middle; Laya found no confident matches ...]"] + lines[-6:])
        return f"--- Distilled Output ({len(kept)}/{len(lines)} lines kept) ---\n" + "\n".join(kept)
    except Exception as err:
        sys.stderr.write(f"[laya-mcp warning] distill_command_output: {err}\n")
        return "\n".join(lines[:6] + [f"[distillation indeterminate: {err}; excerpt only]"] + lines[-6:])


# ---------------------------------------------------------------------------
# 4. Code-region localization
# ---------------------------------------------------------------------------
@mcp.tool()
async def locate_code_regions(
    file_path: str, task: str, chunk_size: int = 40, threshold: float = 0.65,
    max_regions: int = 8,
) -> str:
    """Return relevant overlapping line windows with anchors; never claims completeness."""
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        return f"Error: File not found: {file_path}"
    if chunk_size < 10 or max_regions < 1 or not 0.0 <= threshold <= 1.0:
        return "Error: chunk_size must be >= 10, max_regions >= 1, threshold in [0, 1]."
    try:
        text = _read_text(path)
    except OSError as err:
        return f"Error reading {file_path}: {err}"
    lines = text.splitlines()
    if len(lines) <= chunk_size:
        return f"File is short ({len(lines)} lines); read it directly:\n{text}"
    step = max(chunk_size // 2, 10)
    chunks: list[str] = []
    spans: list[tuple[int, int]] = []
    for start in range(0, len(lines), step):
        end = min(start + chunk_size, len(lines))
        chunks.append("\n".join(lines[start:end]))
        spans.append((start + 1, end))
        if end >= len(lines):
            break
    payload = [
        {"state": chunk[:1500], "questions": {"target_match": {
            "type": "noul",
            "instructions": f"Does this code contain logic/config for: {task!r}?",
        }}}
        for chunk in chunks
    ]
    try:
        results = await _batch_decide(payload)
        ranked: list[tuple[float, int]] = []
        for i, result in enumerate(results):
            score = _score(result, "target_match")
            if score is not None and score >= threshold:
                ranked.append((score, i))
        # Prefer high-confidence windows; collapse heavily overlapping matches.
        ranked.sort(reverse=True)
        selected: list[tuple[float, int]] = []
        for score, idx in ranked:
            start, end = spans[idx]
            if any(not (end < spans[j][0] - 4 or start > spans[j][1] + 4) for _, j in selected):
                continue
            selected.append((score, idx))
            if len(selected) >= max_regions:
                break
        if not selected:
            return (
                f"No code regions scored >= {threshold:.2f} for {task!r}. "
                "This is not proof the file is irrelevant; use targeted manual inspection."
            )
        selected.sort(key=lambda item: spans[item[1]][0])
        output = []
        for score, idx in selected:
            start, end = spans[idx]
            before_start = max(0, start - 4)
            after_end = min(len(lines), end + 3)
            output.append(
                f"=== REGION lines {start}-{end} (Laya score {score:.3f}) ===\n"
                f"# Context before:\n{chr(10).join(lines[before_start:start - 1])}\n"
                f"# Region:\n{chunks[idx]}\n"
                f"# Context after:\n{chr(10).join(lines[end:after_end])}\n"
                f"# File SHA-256: {_sha256(text)}"
            )
        return f"Matched {len(output)} region(s); localization may omit relevant code:\n\n" + "\n\n".join(output)
    except Exception as err:
        return f"Localization indeterminate ({type(err).__name__}: {err}). Inspect the file manually."


# ---------------------------------------------------------------------------
# 5. Patch verification
# ---------------------------------------------------------------------------
@mcp.tool()
async def verify_patch_state(
    file_path: str, expected_snippet: str, check_syntax: bool = True,
    expected_absent: str = "", expected_sha256_before: str = "",
) -> str:
    """Check post-edit content, optional removal, and Python/JSON syntax.

    expected_sha256_before is optional; when supplied, the tool also requires the
    current file hash to differ from the pre-edit hash. Snippet presence alone does
    not prove that the intended diff occurred.
    """
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        return _json({"status": "failed", "verified": False, "error": f"File not found: {file_path}"})
    try:
        content = _read_text(path)
    except OSError as err:
        return _json({"status": "failed", "verified": False, "error": str(err)})
    issues = []
    if not expected_snippet.strip() or expected_snippet.strip() not in content:
        issues.append("expected_snippet_not_found")
    if expected_absent and expected_absent in content:
        issues.append("expected_absent_text_still_present")
    current_hash = _sha256(content)
    if expected_sha256_before and current_hash == expected_sha256_before:
        issues.append("file_hash_unchanged")
    syntax_status = "not_checked"
    if check_syntax and path.suffix == ".py":
        try:
            import ast
            ast.parse(content, filename=str(path))
            syntax_status = "valid_python"
        except SyntaxError as err:
            issues.append("python_syntax_error")
            syntax_status = f"{err.__class__.__name__}: line {err.lineno}: {err.msg}"
    elif check_syntax and path.suffix == ".json":
        try:
            json.loads(content)
            syntax_status = "valid_json"
        except json.JSONDecodeError as err:
            issues.append("json_syntax_error")
            syntax_status = f"line {err.lineno}, column {err.colno}: {err.msg}"
    elif check_syntax and path.suffix == ".jsonc":
        syntax_status = "not_checked_jsonc_requires_jsonc_parser"
    verified = not issues
    return _json({
        "status": "verified" if verified else "failed",
        "verified": verified,
        "syntax": syntax_status,
        "sha256": current_hash,
        "issues": issues,
        "message": (
            f"Checks passed for {path.name}; run relevant tests/type checks as appropriate."
            if verified else
            "Verification failed or was incomplete; inspect the patch and do not assume success."
        ),
    })


# ---------------------------------------------------------------------------
# 6. Task decomposition
# ---------------------------------------------------------------------------
@mcp.tool()
async def triage_user_goals(prompt: str) -> str:
    """Classify whether a request is compound and identify a first blocker."""
    questions = {
        "is_compound": {"type": "noul", "instructions": "Does this prompt contain multiple distinct tasks?"},
        "primary_blocker": {
            "type": "choice",
            "instructions": "Which task category should be addressed first?",
            "criteria": {
                "packaging_or_build": "Build, packaging, linking, signing, dependency installation",
                "runtime_exception": "Crash, exception, invalid runtime state",
                "test_failure": "Failing tests or incorrect observed behavior",
                "ui_geometry": "Layout, styling, dimensions, rendering",
                "feature_addition": "New feature or refactor without a blocker",
                "security_or_data_loss": "Potentially destructive or security-sensitive behavior",
            },
        },
    }
    try:
        data = await _decide(prompt, questions)
        answers = data.get("answers", {})
        compound = _score(data, "is_compound")
        choice = answers.get("primary_blocker", {})
        if compound is None or not isinstance(choice.get("choice"), str):
            return _indeterminate("triage_user_goals", ValueError("Malformed Laya response"))
        return _json({
            "status": "ok",
            "is_compound_task": compound > 0.50,
            "recommended_focus": choice["choice"],
            "confidence": choice.get("confidence"),
            "directive": "Use this as a prioritization hint; do not discard explicit user requirements.",
        })
    except Exception as err:
        return _indeterminate("triage_user_goals", err)


# ---------------------------------------------------------------------------
# 7. Error triage and hypothesis testing
# ---------------------------------------------------------------------------
@mcp.tool()
async def laya_triage_error(error_trace: str) -> str:
    """Classify an error before proposing a fix; result is a hint, not root-cause proof."""
    questions = {
        "is_syntax_or_type": {"type": "noul", "instructions": "Is this a syntax or static type error?"},
        "bug_category": {
            "type": "choice",
            "instructions": "Choose the best primary failure category.",
            "criteria": {
                "assertion_mismatch": "Assertion or expected-value mismatch",
                "null_undefined": "None/null/undefined or missing attribute",
                "missing_dep": "Dependency, module, or file missing",
                "network_timeout": "Network, socket, or remote timeout",
                "auth_forbidden": "Authentication or permission failure",
                "serialization": "Encoding, parsing, or serialization mismatch",
                "logic_state": "Incorrect application logic or state transition",
            },
        },
    }
    try:
        data = await _decide(error_trace, questions)
        return _json({"status": "ok", "answers": data.get("answers", {})})
    except Exception as err:
        return _indeterminate("laya_triage_error", err)


@mcp.tool()
async def verify_hypothesis(hypothesis: str, evidence: str, threshold: float = 0.65) -> str:
    """Assess whether supplied evidence supports a hypothesis; not a substitute for a test."""
    if not 0.0 <= threshold <= 1.0:
        return _json({"status": "failed", "error": "threshold must be between 0 and 1"})
    try:
        data = await _decide(evidence, {"supported": {
            "type": "noul",
            "instructions": f"Does the evidence strongly support this hypothesis: {hypothesis!r}?",
        }})
        score = _score(data, "supported")
        if score is None:
            return _indeterminate("verify_hypothesis", ValueError("Malformed score"))
        return _json({
            "status": "ok",
            "supported_by_model": score >= threshold,
            "score": score,
            "threshold": threshold,
            "caveat": "Model support is not proof; validate with source inspection or a reproducible test.",
        })
    except Exception as err:
        return _indeterminate("verify_hypothesis", err)


# ---------------------------------------------------------------------------
# 8. Documentation / skill pruning
# ---------------------------------------------------------------------------
@mcp.tool()
async def extract_doc_guidelines(
    doc_path: str, focus_topic: str, threshold: float = 0.60, max_sections: int = 12
) -> str:
    """Return sections relevant to a topic while preserving headings and bounded context."""
    path = Path(doc_path).expanduser().resolve()
    if not path.is_file():
        return f"File not found: {doc_path}"
    if not 0.0 <= threshold <= 1.0 or max_sections < 1:
        return "Error: threshold must be in [0, 1] and max_sections must be >= 1."
    content = _read_text(path)
    # Split at Markdown headings of any level; keep heading text with each section.
    sections: list[str] = []
    current: list[str] = []
    for line in content.splitlines():
        if line.startswith("#") and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    sections = [section for section in sections if section]
    if len(sections) <= 2:
        return content
    payload = [
        {"state": section[:1800], "questions": {"relevant": {
            "type": "noul",
            "instructions": f"Does this documentation section provide guidance for {focus_topic!r}?",
        }}}
        for section in sections
    ]
    try:
        results = await _batch_decide(payload)
        scored = []
        for i, result in enumerate(results):
            score = _score(result, "relevant")
            if score is not None and score >= threshold:
                scored.append((score, i))
        scored.sort(reverse=True)
        chosen = sorted(index for _, index in scored[:max_sections])
        if not chosen:
            return (
                "No sections confidently matched. This does not establish that the document "
                "contains no relevant guidance. First section for orientation:\n\n" + sections[0]
            )
        return "\n\n---\n\n".join(sections[i] for i in chosen)
    except Exception as err:
        return f"Documentation pruning indeterminate ({type(err).__name__}: {err}); inspect the document directly."


# ---------------------------------------------------------------------------
# 9. Plan requirement audit
# ---------------------------------------------------------------------------
@mcp.tool()
async def audit_plan_requirements(user_prompt: str, planned_steps: list[str]) -> str:
    """Audit a plan for omissions and executability; service failure never approves it."""
    if not planned_steps:
        return _json({"status": "failed", "approved": False, "error": "planned_steps is empty"})
    plan_text = "USER REQUEST:\n" + user_prompt + "\n\nPROPOSED PLAN:\n" + "\n".join(
        f"- {step}" for step in planned_steps
    )
    questions = {
        "omits_user_request": {
            "type": "noul",
            "instructions": "Does the plan omit any explicit requirement from the user request?",
        },
        "is_executable": {
            "type": "noul",
            "instructions": "Are the steps concrete, ordered, and actionable?",
        },
        "unsafe_or_irreversible": {
            "type": "noul",
            "instructions": "Does the plan include an irreversible/destructive action without an appropriate safeguard or confirmation?",
        },
    }
    try:
        data = await _decide(plan_text, questions)
        omission = _score(data, "omits_user_request")
        executable = _score(data, "is_executable")
        unsafe = _score(data, "unsafe_or_irreversible")
        if None in (omission, executable, unsafe):
            return _indeterminate("audit_plan_requirements", ValueError("Malformed scores"))
        approved = omission < 0.40 and executable >= 0.60 and unsafe < 0.40
        return _json({
            "status": "ok",
            "approved": approved,
            "omission_risk": omission,
            "executable_score": executable,
            "unsafe_action_risk": unsafe,
            "guidance": "Review the original request and plan manually; model audit is advisory.",
        })
    except Exception as err:
        return _indeterminate("audit_plan_requirements", err)


# ---------------------------------------------------------------------------
# 10. General decision engine + status / batch primitives
# ---------------------------------------------------------------------------
@mcp.tool()
async def laya_decide(state: str, questions: dict[str, Any]) -> str:
    """Run arbitrary Laya typed decisions (noul/choice/score) using the Jev-style schema."""
    if not isinstance(questions, dict) or not questions:
        return _json({"status": "failed", "error": "questions must be a non-empty object"})
    try:
        data = await _decide(state, questions)
        if not isinstance(data, dict) or not isinstance(data.get("answers"), dict):
            return _indeterminate("laya_decide", ValueError("Malformed response: missing answers object"))
        return _json({"status": "ok", **data})
    except Exception as err:
        return _indeterminate("laya_decide", err)


@mcp.tool()
async def laya_decide_batch(requests: list[dict[str, Any]]) -> str:
    """Run heterogeneous state/questions decisions in one batch call; preserves input order."""
    if not requests:
        return _json({"status": "failed", "error": "requests must not be empty"})
    if len(requests) > MAX_BATCH_ITEMS:
        return _json({"status": "failed", "error": f"maximum batch size is {MAX_BATCH_ITEMS}"})
    payload = []
    for i, request in enumerate(requests):
        if not isinstance(request, dict) or not isinstance(request.get("questions"), dict):
            return _json({"status": "failed", "error": f"request {i} must contain a questions object"})
        payload.append({
            "state": str(request.get("state", ""))[:MAX_STATE_CHARS],
            "questions": request["questions"],
        })
    try:
        results = await _batch_decide(payload)
        return _json({"status": "ok", "count": len(results), "results": results})
    except Exception as err:
        return _indeterminate("laya_decide_batch", err)


@mcp.tool()
async def laya_status() -> str:
    """Report HTTP backend reachability without loading or exposing model internals."""
    try:
        async with httpx.AsyncClient(timeout=min(REQUEST_TIMEOUT, 5.0)) as client:
            response = await client.get(LAYA_HEALTH)
            response.raise_for_status()
            try:
                health = response.json()
            except ValueError:
                health = {"body": response.text[:1000]}
        return _json({"status": "ok", "base_url": LAYA_BASE, "health": health})
    except Exception as err:
        return _json({
            "status": "unavailable",
            "base_url": LAYA_BASE,
            "error": f"{type(err).__name__}: {err}",
        })


if __name__ == "__main__":
    mcp.run()

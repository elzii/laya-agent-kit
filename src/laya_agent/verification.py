"""Local, deterministic checks used by the patch-verification workflow."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def verify_file(
    file_path: str,
    expected_snippet: str,
    check_syntax: bool = True,
    expected_absent: str = "",
    expected_sha256_before: str = "",
) -> dict[str, Any]:
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        return {"status": "failed", "verified": False, "error": f"File not found: {file_path}"}
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"status": "failed", "verified": False, "error": str(exc)}
    issues: list[str] = []
    if not expected_snippet.strip() or expected_snippet.strip() not in content:
        issues.append("expected_snippet_not_found")
    if expected_absent and expected_absent in content:
        issues.append("expected_absent_text_still_present")
    current_hash = sha256_text(content)
    if expected_sha256_before and current_hash == expected_sha256_before:
        issues.append("file_hash_unchanged")
    syntax = "not_checked"
    if check_syntax and path.suffix == ".py":
        try:
            ast.parse(content, filename=str(path))
            syntax = "valid_python"
        except SyntaxError as exc:
            issues.append("python_syntax_error")
            syntax = f"SyntaxError: line {exc.lineno}: {exc.msg}"
    elif check_syntax and path.suffix == ".json":
        try:
            json.loads(content)
            syntax = "valid_json"
        except json.JSONDecodeError as exc:
            issues.append("json_syntax_error")
            syntax = f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
    verified = not issues
    return {"status": "verified" if verified else "failed", "verified": verified,
            "syntax": syntax, "sha256": current_hash, "issues": issues}

"""Shared policy defaults and safe response helpers for Laya integrations."""
from __future__ import annotations
import json
import math
from typing import Any

DEFAULT_FILE_THRESHOLD = 0.60
DEFAULT_REGION_THRESHOLD = 0.65
DEFAULT_DISTILL_THRESHOLD = 0.55
DEFAULT_DOC_THRESHOLD = 0.60
DEFAULT_HYPOTHESIS_THRESHOLD = 0.65
DEFAULT_MAX_REGIONS = 8
DEFAULT_MAX_DISTILLED_LINES = 12
DEFAULT_MAX_STATE_CHARS = 12_000
DEFAULT_MAX_BATCH_ITEMS = 128


def json_text(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def finite_score(response: Any, key: str) -> float | None:
    """Extract a valid [0,1] score from the official server's known response shape."""
    try:
        score = float(response["answers"][key]["noul"])
    except (KeyError, TypeError, ValueError):
        return None
    return score if math.isfinite(score) and 0 <= score <= 1 else None


def indeterminate(tool: str, error: Exception) -> str:
    """Never convert a service or schema failure into a successful decision."""
    return json_text({
        "status": "indeterminate",
        "tool": tool,
        "error": f"{type(error).__name__}: {error}",
        "fallback_required": True,
    })

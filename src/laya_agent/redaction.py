"""Pre-call secret and credential sanitizer for Laya requests (inspired by decision-gate)."""

from __future__ import annotations

import re
from typing import Any, Tuple

# Patterns for API keys, private keys, tokens
PATTERNS = [
    # Private keys (PEM / SSH)
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    # OpenAI / Anthropic / HuggingFace API keys
    (re.compile(r"\b(sk-[a-zA-Z0-9_\-]{20,})\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\b(sk-ant-[a-zA-Z0-9_\-]{20,})\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\b(hf_[a-zA-Z0-9]{30,})\b"), "[REDACTED_HF_TOKEN]"),
    # GitHub personal access tokens
    (re.compile(r"\b(ghp_[a-zA-Z0-9]{36,}|github_pat_[a-zA-Z0-9_]{50,})\b"), "[REDACTED_GITHUB_TOKEN]"),
    # AWS access keys
    (re.compile(r"\b(AKIA[0-9A-Z]{16})\b"), "[REDACTED_AWS_KEY]"),
    # Generic Bearer tokens
    (re.compile(r"(?i)\bBearer\s+([a-zA-Z0-9\-_=]{24,})\b"), "Bearer [REDACTED_TOKEN]"),
]


def redact_secrets(text: Any) -> Tuple[str, int]:
    """Scans text and replaces secrets with stable redaction tokens.

    Returns: (sanitized_text, count_of_redactions)
    """
    if not isinstance(text, str):
        text = str(text)

    total_redacted = 0
    sanitized = text
    for pattern, replacement in PATTERNS:
        matches = len(pattern.findall(sanitized))
        if matches > 0:
            total_redacted += matches
            sanitized = pattern.sub(replacement, sanitized)

    return sanitized, total_redacted

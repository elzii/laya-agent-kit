"""Deterministic offline stand-in for official Laya System-1 server.

Generates reproducible responses based on SHA-256 hashes of input state and questions.
Allows 100% offline testing of client, engine, and MCP tools with zero live network calls.
Includes fault injection capabilities (timeouts, 429 rate limits, 500 server errors, malformed JSON).
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, List, Optional
import httpx


def _hash_probability(state: str, question_name: str, option: str = "yes") -> float:
    """Generates a stable pseudo-probability in [0.05, 0.95] from input hash."""
    seed = f"{state[:200]}::{question_name}::{option}".encode("utf-8")
    h = int(hashlib.sha256(seed).hexdigest()[:8], 16)
    # Map to [0.05, 0.95]
    return 0.05 + 0.90 * (h / 0xFFFFFFFF)


def generate_fake_systemone_response(
    state: str,
    questions: Dict[str, Any],
) -> Dict[str, Any]:
    """Generates a schema-compliant Laya /v1/systemone response."""
    answers: Dict[str, Any] = {}
    for q_name, q_spec in questions.items():
        q_type = q_spec.get("type", "noul")
        instructions = q_spec.get("instructions", "")

        if q_type == "noul":
            p = _hash_probability(state, q_name, "noul")
            answers[q_name] = {
                "noul": round(p, 4),
                "confidence": round(abs(p - 0.5) * 2, 4),
            }
        elif q_type == "choice":
            options = q_spec.get("options", ["opt1", "opt2"])
            probs = [_hash_probability(state, q_name, opt) for opt in options]
            total = sum(probs) or 1.0
            norm_probs = {opt: round(pr / total, 4) for opt, pr in zip(options, probs)}
            top_choice = max(norm_probs.items(), key=lambda x: x[1])[0]
            answers[q_name] = {
                "choice": top_choice,
                "confidence": round(norm_probs[top_choice], 4),
                "probabilities": norm_probs,
            }
        elif q_type == "score":
            s = _hash_probability(state, q_name, "score")
            answers[q_name] = {
                "score": round(s, 4),
                "confidence": round(abs(s - 0.5) * 2, 4),
            }
        else:
            answers[q_name] = {"value": "unknown_type"}

    return {
        "status": "ok",
        "model": "laya-fake-systemone",
        "answers": answers,
    }


class FakeLayaTransport(httpx.AsyncBaseTransport):
    """An httpx Async Transport that handles Laya /v1 requests offline with deterministic fake responses."""

    def __init__(
        self,
        fault_mode: Optional[str] = None,  # "timeout", "rate_limit", "server_error", "malformed"
        custom_handler: Optional[Any] = None,
    ):
        self.fault_mode = fault_mode
        self.custom_handler = custom_handler
        self.call_history: List[Dict[str, Any]] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body = json.loads(request.content.decode("utf-8")) if request.content else {}
        self.call_history.append({"path": path, "body": body})

        # Fault injection
        if self.fault_mode == "timeout":
            raise httpx.ReadTimeout("Simulated Laya timeout", request=request)
        elif self.fault_mode == "rate_limit":
            return httpx.Response(status_code=429, json={"error": "Too Many Requests", "retry_after": 1})
        elif self.fault_mode == "server_error":
            return httpx.Response(status_code=500, json={"error": "Internal Laya Server Error"})
        elif self.fault_mode == "malformed":
            return httpx.Response(status_code=200, text="Not valid json {{{")

        if self.custom_handler:
            return self.custom_handler(request, path, body)

        if path in ("/openapi.json", "/docs", "/"):
            return httpx.Response(status_code=200, json={"status": "laya_online"})

        if path == "/v1/systemone":
            state = body.get("state", "")
            questions = body.get("questions", {})
            resp_data = generate_fake_systemone_response(state, questions)
            return httpx.Response(status_code=200, json=resp_data)

        if path == "/v1/systemone/batch":
            states = body.get("states", [])
            questions = body.get("questions", {})
            results = [generate_fake_systemone_response(st, questions) for st in states]
            return httpx.Response(status_code=200, json={"results": results})

        return httpx.Response(status_code=404, json={"error": f"Not found: {path}"})

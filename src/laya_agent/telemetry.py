"""Local-only, privacy-preserving token and latency accounting (inspired by oko)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional


class TelemetryLedger:
    def __init__(self, log_path: Optional[str] = None, enabled: Optional[bool] = None):
        if enabled is None:
            self.enabled = os.getenv("LAYA_TELEMETRY", "0") in ("1", "true", "yes")
        else:
            self.enabled = enabled

        self.log_path = Path(log_path or os.getenv("LAYA_TELEMETRY_LOG", ".laya/telemetry.jsonl")).expanduser()
        if self.enabled:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_call(
        self,
        tool: str,
        input_tokens_est: int,
        output_tokens_est: int,
        duration_ms: float,
        status: str = "ok",
        cache_hit: bool = False,
    ) -> None:
        """Records metadata strictly without code, prompts, or sensitive strings."""
        if not self.enabled:
            return

        record = {
            "timestamp": time.time(),
            "tool": tool,
            "input_tokens_est": input_tokens_est,
            "output_tokens_est": output_tokens_est,
            "duration_ms": round(duration_ms, 2),
            "status": status,
            "cache_hit": cache_hit,
        }

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

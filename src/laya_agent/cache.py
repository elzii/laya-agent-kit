"""Local state+question answer cache for Laya queries (inspired by decision-gate and pytest-jev)."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

CACHE_VERSION = "laya_cache_v1"
DEFAULT_TTL_SECONDS = 86400  # 24 hours


class AnswerCache:
    def __init__(self, cache_dir: Optional[str] = None, enabled: bool = True, ttl: int = DEFAULT_TTL_SECONDS):
        self.enabled = enabled
        self.ttl = ttl
        self.cache_dir = Path(cache_dir or os.getenv("LAYA_CACHE_DIR", ".laya/cache")).expanduser()
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _hash_key(self, state: str, questions: Any) -> str:
        q_str = json.dumps(questions, sort_keys=True) if isinstance(questions, (dict, list)) else str(questions)
        data = f"{CACHE_VERSION}::{state}::{q_str}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def get(self, state: str, questions: Any) -> Optional[Any]:
        if not self.enabled:
            return None
        key = self._hash_key(state, questions)
        entry_file = self.cache_dir / f"{key}.json"
        if not entry_file.exists():
            return None
        try:
            record = json.loads(entry_file.read_text(encoding="utf-8"))
            if time.time() > record.get("expires_at", 0):
                entry_file.unlink(missing_ok=True)
                return None
            return record.get("response")
        except Exception:
            return None

    def set(self, state: str, questions: Any, response: Any) -> None:
        if not self.enabled or not response:
            return
        if isinstance(response, dict) and response.get("fallback"):
            # Do NOT cache fallback or error responses
            return
        key = self._hash_key(state, questions)
        entry_file = self.cache_dir / f"{key}.json"
        try:
            record = {
                "key": key,
                "cached_at": time.time(),
                "expires_at": time.time() + self.ttl,
                "response": response,
            }
            tmp = entry_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(record), encoding="utf-8")
            tmp.replace(entry_file)
        except Exception:
            pass

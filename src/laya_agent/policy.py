import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import tomllib


@dataclass(frozen=True)
class Policy:
    max_output_chars: int = 12000
    max_regions: int = 8
    max_candidate_files: int = 30
    file_read_warning_lines: int = 50
    long_output_line_threshold: int = 12
    cache_enabled: bool = False
    redaction_enabled: bool = True
    telemetry_enabled: bool = False

    @classmethod
    def load(cls, path: Optional[str] = None):
        cfg_path = Path(path or os.getenv("LAYA_POLICY_PATH", "policy.toml"))
        data = {}
        if cfg_path.is_file():
            try:
                data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        retrieval = data.get("retrieval", {})
        distillation = data.get("distillation", {})
        optimizations = data.get("optimizations", {})

        return cls(
            max_output_chars=max(100, int(os.getenv("LAYA_MAX_OUTPUT_CHARS", distillation.get("max_output_chars", 12000)))),
            max_regions=max(1, int(os.getenv("LAYA_MAX_REGIONS", retrieval.get("max_regions", 8)))),
            max_candidate_files=max(1, int(os.getenv("LAYA_MAX_CANDIDATE_FILES", retrieval.get("max_candidate_files", 30)))),
            file_read_warning_lines=max(1, int(os.getenv("LAYA_FILE_READ_WARNING_LINES", retrieval.get("file_read_warning_lines", 50)))),
            long_output_line_threshold=max(1, int(os.getenv("LAYA_LONG_OUTPUT_THRESHOLD", distillation.get("long_output_line_threshold", 12)))),
            cache_enabled=os.getenv("LAYA_CACHE_ENABLED", str(optimizations.get("cache_enabled", False))).lower() in ("1", "true", "yes"),
            redaction_enabled=os.getenv("LAYA_REDACTION_ENABLED", str(optimizations.get("redaction_enabled", True))).lower() in ("1", "true", "yes"),
            telemetry_enabled=os.getenv("LAYA_TELEMETRY", str(optimizations.get("telemetry_enabled", False))).lower() in ("1", "true", "yes"),
        )

    @classmethod
    def from_env(cls):
        return cls.load()


def cap_text(value, limit=12000):
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    suffix = f"\n[truncated; {len(text)-limit} characters omitted]"
    return text[:max(0, limit - len(suffix))] + suffix


def verification_status(passed):
    return "passed" if passed is True else "failed" if passed is False else "indeterminate"

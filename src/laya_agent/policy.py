import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Policy:
    max_output_chars: int = 12000
    max_regions: int = 8
    max_candidate_files: int = 30
    file_read_warning_lines: int = 50

    @classmethod
    def from_env(cls):
        return cls(
            max_output_chars=max(100, int(os.getenv("LAYA_MAX_OUTPUT_CHARS", "12000"))),
            max_regions=max(1, int(os.getenv("LAYA_MAX_REGIONS", "8"))),
            max_candidate_files=max(1, int(os.getenv("LAYA_MAX_CANDIDATE_FILES", "30"))),
            file_read_warning_lines=max(1, int(os.getenv("LAYA_FILE_READ_WARNING_LINES", "50"))),
        )

def cap_text(value, limit=12000):
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    suffix = f"\n[truncated; {len(text)-limit} characters omitted]"
    return text[:max(0, limit-len(suffix))] + suffix

def verification_status(passed):
    return "passed" if passed is True else "failed" if passed is False else "indeterminate"

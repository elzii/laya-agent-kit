"""Small, dependency-free harness detector used by maintainers and tests."""
from __future__ import annotations
import shutil
from pathlib import Path


def detect(home: Path | None = None) -> dict[str, bool]:
    home = home or Path.home()
    return {
        "gemini": (home / ".gemini").exists() or shutil.which("gemini") is not None,
        "claude": (home / ".claude").exists() or shutil.which("claude") is not None,
        "codex": (home / ".codex").exists() or shutil.which("codex") is not None,
        "opencode": (home / ".config" / "opencode").exists() or shutil.which("opencode") is not None,
    }

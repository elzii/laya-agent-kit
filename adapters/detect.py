from pathlib import Path
DIRS = {
    "gemini": Path.home()/".gemini",
    "claude": Path.home()/".claude",
    "codex": Path.home()/".codex",
    "opencode": Path.home()/".config"/"opencode",
}
def detect_harnesses():
    return {name: path.exists() for name, path in DIRS.items()}

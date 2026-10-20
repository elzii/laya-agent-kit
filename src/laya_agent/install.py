"""Conservative installer: installs skills/instruction snippets, never overwrites harness config."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
# Use checkout files in development; use bundled package resources after installation.
SKILLS_ROOT = PACKAGE_ROOT / "skills"
HARNESS_ROOT = PACKAGE_ROOT / "harnesses"
if not SKILLS_ROOT.is_dir():
    SKILLS_ROOT = Path(__file__).resolve().parent / "resources" / "skills"
if not HARNESS_ROOT.is_dir():
    HARNESS_ROOT = Path(__file__).resolve().parent / "resources" / "harnesses"
SKILL_DESTINATIONS = {
    "gemini": Path.home() / ".gemini" / "skills",
    "claude": Path.home() / ".claude" / "skills",
    "codex": Path.home() / ".agents" / "skills",
    "opencode": Path.home() / ".config" / "opencode" / "skills",
}
INSTRUCTION_FILES = {
    "gemini": (HARNESS_ROOT / "gemini" / "GEMINI.md", Path.home() / ".gemini" / "laya-agent-kit-GEMINI.md"),
    "claude": (HARNESS_ROOT / "claude" / "CLAUDE.md", Path.home() / ".claude" / "laya-agent-kit-CLAUDE.md"),
    "codex": (HARNESS_ROOT / "codex" / "AGENTS.md", Path.home() / ".codex" / "laya-agent-kit-AGENTS.md"),
    "opencode": (HARNESS_ROOT / "opencode" / "AGENTS.md", Path.home() / ".config" / "opencode" / "laya-agent-kit-AGENTS.md"),
}


def detect_harnesses() -> list[str]:
    found = []
    if (Path.home() / ".gemini").exists() or shutil.which("gemini"):
        found.append("gemini")
    if (Path.home() / ".claude").exists() or shutil.which("claude"):
        found.append("claude")
    if (Path.home() / ".codex").exists() or shutil.which("codex"):
        found.append("codex")
    if (Path.home() / ".config" / "opencode").exists() or shutil.which("opencode"):
        found.append("opencode")
    return found


def install(harness: str) -> None:
    dest = SKILL_DESTINATIONS[harness]
    dest.mkdir(parents=True, exist_ok=True)
    for skill in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        target = dest / skill.parent.name
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill, target / "SKILL.md")
        print(f"Installed skill: {target / 'SKILL.md'}")
    source, target = INSTRUCTION_FILES[harness]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print(f"Kept existing instruction snippet (not overwritten): {target}")
    else:
        shutil.copy2(source, target)
        print(f"Wrote instruction snippet: {target}")
    print("\nMCP configuration is deliberately not edited automatically.")
    print(f"Review the example in: {HARNESS_ROOT / harness}")
    print("Merge the MCP entry into the harness config, using an absolute Python path.")


def uninstall(harness: str) -> None:
    dest = SKILL_DESTINATIONS[harness]
    for skill in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        target = dest / skill.parent.name / "SKILL.md"
        if target.exists():
            target.unlink()
            try:
                target.parent.rmdir()
            except OSError:
                pass
            print(f"Removed: {target}")
    _, instruction = INSTRUCTION_FILES[harness]
    if instruction.exists():
        instruction.unlink()
        print(f"Removed: {instruction}")
    print("MCP configuration was not changed; remove its entry manually if desired.")


def doctor() -> int:
    import urllib.error
    import urllib.request
    base = os.getenv("LAYA_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    print(f"Python: {sys.executable}")
    print(f"ripgrep: {shutil.which('rg') or 'NOT FOUND (fast_symbol_search requires rg)'}")
    print(f"MCP package: {'available' if _importable('mcp') else 'MISSING (install package dependencies)'}")
    print(f"Configured base URL: {base}")
    try:
        with urllib.request.urlopen(base + "/health", timeout=3) as response:
            print(f"Laya HTTP: reachable (HTTP {response.status})")
    except Exception as exc:
        print(f"Laya HTTP: not confirmed ({type(exc).__name__}: {exc})")
        print("Check that your official laya-serve process is running and that LAYA_BASE_URL is correct.")
        return 1
    return 0


def _importable(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(prog="laya-agent-kit")
    sub = parser.add_subparsers(dest="command", required=True)
    p_install = sub.add_parser("install", help="Install portable skills and a separate instruction snippet")
    p_install.add_argument("--harness", choices=["auto", *SKILL_DESTINATIONS], default="auto")
    p_uninstall = sub.add_parser("uninstall", help="Remove installed skills/snippet; does not edit MCP config")
    p_uninstall.add_argument("--harness", choices=list(SKILL_DESTINATIONS), required=True)
    sub.add_parser("doctor", help="Check local dependencies and official Laya HTTP health")
    args = parser.parse_args()
    if args.command == "install":
        harnesses = detect_harnesses() if args.harness == "auto" else [args.harness]
        if not harnesses:
            print("No known harness detected. Specify --harness gemini|claude|codex|opencode.")
            raise SystemExit(2)
        for harness in harnesses:
            install(harness)
    elif args.command == "uninstall":
        uninstall(args.harness)
    else:
        raise SystemExit(doctor())

if __name__ == "__main__":
    main()

"""Install portable skills and append harness guidance without clobbering user instructions."""
import argparse, asyncio, shutil, sys
from datetime import datetime
from pathlib import Path
from .client import LayaClient

PACKAGE = Path(__file__).resolve().parents[2]
if not (PACKAGE/"skills").is_dir():
    PACKAGE = Path(sys.prefix)/"share"/"laya-agent-kit"
HOME = Path.home()
HARNESS_CONFIG = {
    "gemini": {"root": HOME/".gemini", "instruction": "GEMINI.md", "skills": HOME/".gemini"/"skills", "source": PACKAGE/"harnesses/gemini/GEMINI.md"},
    "claude": {"root": HOME/".claude", "instruction": "CLAUDE.md", "skills": HOME/".claude"/"skills", "source": PACKAGE/"harnesses/claude/CLAUDE.md"},
    "codex": {"root": HOME/".codex", "instruction": "AGENTS.md", "skills": HOME/".agents"/"skills", "source": PACKAGE/"harnesses/codex/AGENTS.md"},
    "opencode": {"root": HOME/".config"/"opencode", "instruction": "AGENTS.md", "skills": HOME/".config"/"opencode"/"skills", "source": PACKAGE/"harnesses/opencode/AGENTS.md"},
}
START = "<!-- BEGIN LAYA AGENT KIT MANAGED SECTION -->"
END = "<!-- END LAYA AGENT KIT MANAGED SECTION -->"

def backup(path):
    if not path.exists(): return
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    dest=path.with_name(path.name+".laya-backup-"+stamp)
    shutil.copytree(path,dest) if path.is_dir() else shutil.copy2(path,dest)

def install_one(name, dry_run=False):
    cfg=HARNESS_CONFIG[name]
    target=cfg["root"]/cfg["instruction"]
    print(f"[{name}] instructions: {target}; skills: {cfg['skills']}")
    if dry_run: return
    cfg["skills"].mkdir(parents=True,exist_ok=True)
    source_skills=PACKAGE/"skills"
    for skill_dir in source_skills.iterdir():
        if not skill_dir.is_dir(): continue
        dest=cfg["skills"]/skill_dir.name
        if dest.exists(): backup(dest)
        if dest.exists(): shutil.rmtree(dest)
        shutil.copytree(skill_dir,dest)
    cfg["root"].mkdir(parents=True,exist_ok=True)
    incoming=cfg["source"].read_text(encoding="utf-8").strip()
    existing=target.read_text(encoding="utf-8") if target.exists() else ""
    # Idempotently replace only the previously managed section; preserve all user content.
    if START in existing and END in existing:
        before=existing.split(START,1)[0].rstrip()
        after=existing.split(END,1)[1].lstrip()
        existing="\n\n".join(x for x in (before,after) if x)
    if target.exists(): backup(target)
    managed=f"{START}\n{incoming}\n{END}"
    target.write_text((existing.rstrip()+"\n\n" if existing.strip() else "")+managed+"\n",encoding="utf-8")
    print("  installed; existing instruction content preserved")

async def doctor():
    import json
    checks = {"rg": shutil.which("rg"), "fd": shutil.which("fd") or shutil.which("fdfind")}
    result = await LayaClient().health()
    print(json.dumps({"dependencies": checks, "laya": result}, indent=2))
    if not checks["rg"] or not checks["fd"]:
        print("Missing command-line dependency. Run scripts/install-deps.sh from the source checkout.")
    if result.get("reachable"):
        print("Laya is reachable; endpoint request/response compatibility still needs a real inference test.")
        return 0 if checks["rg"] and checks["fd"] else 1
    print("Official Laya server unreachable. Start it with your existing script; this package will not restart it.")
    return 1

def main():
    parser=argparse.ArgumentParser(prog="laya-agent-kit")
    sub=parser.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("install"); p.add_argument("--harness",choices=[*HARNESS_CONFIG,"all"],required=True); p.add_argument("--dry-run",action="store_true")
    sub.add_parser("doctor")
    args=parser.parse_args()
    if args.cmd=="install":
        for name in HARNESS_CONFIG if args.harness=="all" else [args.harness]: install_one(name,args.dry_run)
    else: raise SystemExit(asyncio.run(doctor()))

if __name__=="__main__": main()

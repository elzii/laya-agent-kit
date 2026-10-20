#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$ROOT/scripts/install-deps.sh"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -e "$ROOT"
printf '\nSetup complete. Activate with:\n  source "%s/.venv/bin/activate"\nThen run:\n  laya-agent-kit doctor\n' "$ROOT"

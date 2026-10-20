#!/usr/bin/env bash
set -euo pipefail
OS="$(uname -s)"
if command -v rg >/dev/null 2>&1 && { command -v fd >/dev/null 2>&1 || command -v fdfind >/dev/null 2>&1; }; then
  echo "Dependencies already present: rg=$(command -v rg), fd=$(command -v fd || command -v fdfind)"; exit 0
fi
case "$OS" in
  Darwin)
    if ! command -v brew >/dev/null 2>&1; then echo "Homebrew required: https://brew.sh" >&2; exit 1; fi
    brew install ripgrep fd ;;
  Linux)
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update; sudo apt-get install -y ripgrep fd-find
      if ! command -v fd >/dev/null 2>&1 && command -v fdfind >/dev/null 2>&1; then
        mkdir -p "$HOME/.local/bin"; ln -sf "$(command -v fdfind)" "$HOME/.local/bin/fd"
        echo "Ensure $HOME/.local/bin is on PATH."
      fi
    elif command -v dnf >/dev/null 2>&1; then sudo dnf install -y ripgrep fd-find || sudo dnf install -y ripgrep fd
    elif command -v pacman >/dev/null 2>&1; then sudo pacman -Sy --needed ripgrep fd
    else echo "Unsupported Linux package manager; install ripgrep and fd manually." >&2; exit 1; fi ;;
  *) echo "Unsupported OS: $OS. Install ripgrep and fd manually." >&2; exit 1 ;;
esac
command -v rg >/dev/null 2>&1 || { echo "rg not found on PATH." >&2; exit 1; }
command -v fd >/dev/null 2>&1 || command -v fdfind >/dev/null 2>&1 || { echo "fd/fdfind not found on PATH." >&2; exit 1; }
echo "Dependency check passed."

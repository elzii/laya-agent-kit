# Laya Agent Kit

A multi-harness integration layer for coding agents that use the **official Laya inference server** already running on your machine. This project does not install, launch, or manage `laya-serve`.


[!IMPORTANT]
> **Pre-requisites**:
- Install [Laya](https://github.com/NandhaKishorM/laya) globally with `python3 -m pip install laya`

- 🟦 Windows: Use [Supervisor](http://supervisord.org/) to autostart Laya server. [GoogleAI Instructions - Windows](https://www.google.com/search?udm=50&aep=11&q=How+to+install+supervisor+on+windows+and+autostart+a+python+script+on+login)
- 🐧 Linux: Use [systemd](https://www.freedesktop.org/wiki/Software/systemd/) to autostart Laya server. [GoogleAI Instructions - Linux](https://www.google.com/search?udm=50&aep=11&q=How+to+create+a+custom+user+systemd+daemon)
- 🖥️ macOS: Create a [Launch Agents](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html) to autostart Laya server. [GoogleAI Instructions - macOS](https://www.google.com/search?udm=50&aep=11&q=How+to+create+a+custom+launch+agent+on+macos)

_The below assumes you on  macOS and have **python3 >= 3.11** installed via **homebrew**:_

`$HOME/Library/LaunchAgents/com.laya.server.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.laya.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/laya-serve</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/tmp</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>LAYA_DEVICE</key>
        <string>mps</string>
        <key>LAYA_PRELOAD</key>
        <string>1</string>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/laya-serve.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/laya-serve.stderr.log</string>
</dict>
</plist>
```

- Bootstrap it and start it with:
```bash
# Unregister previous service instance
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.laya.server.plist 2>/dev/null || true

# Load and kickstart the updated service
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.laya.server.plist
launchctl kickstart -k gui/$(id -u)/com.laya.server
```


## Architecture

- `src/laya_agent/server.py`: MCP bridge and tool implementations. It preserves the current `/v1/systemone` and `/v1/systemone/batch` request shape and existing tool names.
- `src/laya_agent/engine.py`: Where the inference functions are implemented. `server.py` calls `engine.py` to perform the actual inference. This separation allows for easier testing and development of the inference logic without needing to run the server.
- `src/laya_agent/client.py`: Thin client for harnesses to call the MCP bridge. It handles requests and errors, and is essentially the same as server, but leaves it so server.py is a very client readable overview.
- `skills/`: portable, on-demand workflows for triage, retrieval, debugging, and verification.
- `harnesses/`: harness-specific instruction and configuration examples. Review and merge these into your own harness config; don't blindly overwrite existing settings.
- `adapters/`: install/doctor/uninstall helper.
- `tests/`: local policy and smoke tests.


## Run `laya-serve` Manually
```bash
export LAYA_DEVICE=mps
export LAYA_PRELOAD=1
laya-serve --host 127.0.0.1 --port 8000
```


The MCP bridge defaults to `http://127.0.0.1:8000` and speaks the official API shape used by the attached MCP: single inference `{"state": "...", "questions": {...}}` at `/v1/systemone`, and batch inference `{"states": ["..."], "questions": {...}}` at `/v1/systemone/batch`. Batch calls are chunked to 48 states (configurable, capped at 64) and individual states are capped at 45,000 characters. A reachability check alone does not prove inference compatibility; run a real tool test after setup.

## Install dependencies

On macOS with Homebrew:

```bash
./scripts/install-deps.sh
```

This installs `ripgrep` (`rg`) and `fd` with `brew install ripgrep fd`. Debian/Ubuntu installs `ripgrep` and `fd-find` and adds a `fd` alias under `~/.local/bin` when necessary. Other Linux package managers are handled where possible. You can also install them manually.

For a combined OS-dependency and Python setup, run `./scripts/setup.sh`. Or install the Python package manually in an isolated environment:


## Development install

From this directory:

```bash
python3 -m venv .venv                    # OPTIONAL
source .venv/bin/activate                # OPTIONAL
python -m pip install -e .               # install this repo as a package
export LAYA_BASE=http://127.0.0.1:8000   # host and port settings (defaults)
command -v rg                            # fast_symbol_search uses ripgrep
laya-agent-kit doctor                    # checks dependencies and Laya server reachability
```

### Running Tests
```bash
# Run unit tests
python3 -m pytest -q -p no:cacheprovider

# Run with verbose output
python3 -m pytest -v tests/
```


## MCP configuration

Point each harness at the absolute path to `.venv/bin/laya-agent-mcp`, with `LAYA_BASE=http://127.0.0.1:8000`. Example configuration files are under `harnesses/`. Keep the official Laya server running separately using your own script.

## Multi-harness skills and instructions

The shared `skills/laya-system1-gating/SKILL.md` contains the cross-harness version of the phased token-optimization protocol. Four focused skills cover triage, context retrieval, debugging, and verification. These skills retain operational details and recovery rules; the shared protocol coordinates them rather than replacing their domain-specific guidance. Harness-specific instruction files refer to the shared protocol without assuming every harness has the same planning-artifact or hook APIs.

Preview or install skills/instructions:

```bash
laya-agent-kit install --harness gemini --dry-run
laya-agent-kit install --harness gemini
laya-agent-kit install --harness claude
laya-agent-kit install --harness codex
laya-agent-kit install --harness opencode
```

The installer copies skills into each harness's user-level skills directory and adds a marked managed section to the relevant instruction file. Existing instruction text is preserved, and a timestamped backup is made before changes. Review the changes after installation.

## Tools carried forward

- `filter_candidate_files`
- `fast_symbol_search`
- `distill_command_output`
- `locate_code_regions`
- `verify_patch_state`
- `triage_user_goals`
- `laya_triage_error`
- `verify_hypothesis`
- `extract_doc_guidelines`
- `audit_plan_requirements`
- `laya_decide`

Also included: `laya_status` and `laya_systemone_batch`.

## Safety and honest verification

Laya fallback/unavailable responses are not treated as positive judgments. If Laya is down, tools use a clearly marked fallback or return indeterminate rather than fabricating semantic scores. `verify_patch_state` checks expected snippet presence and selected syntax only; run tests, type checks, linters, and builds as appropriate. The 50-line and 12-line rules are workflow heuristics, not a reason to suppress evidence needed to solve a task safely. Semantic filtering produces a shortlist, not proof that excluded files are irrelevant; missing matches and unavailable tools must not be treated as negative evidence.


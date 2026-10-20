# Laya Agent Kit

A multi-harness integration layer for coding agents that use the **official Laya inference server** already running on your machine. This project does not install, launch, or manage `laya-serve`.

## Architecture

- `src/laya_agent/server.py`: MCP bridge and tool implementations. It preserves the current `/v1/systemone` and `/v1/systemone/batch` request shape and existing tool names.
- `skills/`: portable, on-demand workflows for triage, retrieval, debugging, and verification.
- `harnesses/`: harness-specific instruction and configuration examples. Review and merge these into your own harness config; don't blindly overwrite existing settings.
- `adapters/`: install/doctor/uninstall helper.
- `tests/`: local policy and smoke tests.

Your existing server startup remains separate:

```bash
export LAYA_DEVICE=mps
export LAYA_PRELOAD=1
laya-serve --host 127.0.0.1 --port 8000
```

The MCP bridge defaults to `LAYA_BASE_URL=http://127.0.0.1:8000`. Set `LAYA_BASE_URL` on the MCP process if the official server is elsewhere. `LAYA_DEVICE` and `LAYA_PRELOAD` belong to the inference-server process, not each agent harness.

## Development install

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
command -v rg  # fast_symbol_search uses ripgrep
laya-agent-kit doctor
```

Configure a harness to launch the MCP bridge with the same Python environment, for example:

```json
{
  "command": "/absolute/path/to/laya-agent-kit/.venv/bin/python",
  "args": ["-m", "laya_agent.server"],
  "env": { "LAYA_BASE_URL": "http://127.0.0.1:8000" }
}
```

Run the bridge manually for a quick import check:

```bash
python -m laya_agent.server
```

## Tool safety semantics

- Retrieval filtering is an optimization, not a security boundary. If Laya cannot score candidate paths, the tool keeps the candidates rather than silently discarding them.
- Model-based triage, plan audits, and hypothesis checks are advisory.
- A service error is **not** a successful verification. Verification results use explicit status fields.
- `verify_patch_state` checks the expected snippet, optional absent text, optional pre-edit hash, and Python/JSON syntax. It does not replace tests, type checks, or diff review.
- `laya_status` probes the official server's `/health` endpoint. If your official build exposes a different health endpoint, adjust that tool rather than assuming the endpoint exists.

## Important integration note

The `server.py` bridge is intentionally kept as a single file in this initial scaffold so the tool contract stays easy to compare against the already syntax-checked implementation. `client.py`, `policy.py`, and `verification.py` are reusable extracted utilities for subsequent modularization; the current bridge does not yet import them. The first integration test should be against your actual official Laya server because endpoint schemas and response details are server-version dependent.

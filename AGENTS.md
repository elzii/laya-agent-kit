# AGENTS.md — Contributor and Agent Guide for Laya Agent Kit

## 1. Project Overview & Boundaries

`laya-agent-kit` is a multi-harness integration layer providing fast "System-1" gating tools for coding agents (Claude Code, Codex CLI, Gemini CLI, OpenCode). It acts as an MCP server and skills toolkit backed by an **already-running official Laya inference server** (`/v1/systemone` and `/v1/systemone/batch`).

### Non-Negotiable Architectural Boundaries
- **Integration Layer Only**: This repository does not install, launch, daemonize, or manage `laya-serve`. It connects to a reachable HTTP endpoint configured via `LAYA_BASE` / `LAYA_BASE_URL` (default: `http://127.0.0.1:8000`).
- **No Direct Model Weight Execution**: This package does not download or execute neural network weights in-process.
- **Host Model Separation**: The MCP server runs as a separate process and cannot directly intercept or measure the host coding model's internal prompt tokens. Token accounting must clearly distinguish between estimated tokens and provider-reported usage.
- **Local Privacy**: Local telemetry never logs raw source code, prompts, or sensitive strings.

---

## 2. Development & Testing Commands

All commands are run from the repository root:

```bash
# Run unit tests
python3 -m pytest -q -p no:cacheprovider

# Run verbose test suite
python3 -m pytest -v -p no:cacheprovider

# Check bridge dependencies and Laya server reachability
python3 -m laya_agent.install doctor
# or via installed script:
laya-agent-kit doctor

# Install MCP server / skills into agent harnesses
python3 -m laya_agent.install install --harness all
```

> **Note on Doctor**: `laya-agent-kit doctor` checks dependency presence and Laya HTTP server reachability. It does not execute pytest or linters.

---

## 3. Core Guardrails & Invariants

1. **Verification Status vs Behavioral Proof**:
   - `verify_patch_state` verifies snippet presence and language syntax (Python, JSON, TOML, YAML, Bash).
   - **Syntax and snippet presence do not prove behavioral correctness.** Coding tasks must always be validated by running actual tests or builds.
2. **Safe Fallback & Abstention**:
   - When the external Laya server is unreachable, times out, or returns an error, tools return a marked fallback payload with status `"indeterminate"`.
   - Never treat an unavailable service, timeout, or low-confidence judgment as a positive pass.
3. **Evidence Preservation**:
   - Diagnostic distillation (`distill_command_output`) must never drop stack trace context or discard raw outputs entirely. Full raw outputs must be spooled to local disk storage (`.laya/spool/`) so agents can inspect the full log if needed.
4. **Zero Overlap in Code Retrieval**:
   - `locate_code_regions` must return merged, non-overlapping contiguous ranges to prevent duplicate token inflation.
   - > [!CAUTION]
     > **Under Evaluation for Potential Removal (High-Risk, High-Reward)**: `locate_code_regions` is under active review for potential deprecation or removal. While retrieving partial code chunks provides high token savings on large files, partial extraction carries significant risk of context truncation—omitting critical callers, error branches, or surrounding class state—which can lead to agent hallucinations or incomplete reasoning. Whole-file reads paired with targeted symbol lookup (`fast_symbol_search`) may ultimately prove safer.
5. **No File Left Behind**:
   - Local syntax verification must not emit compilation artifacts (e.g. `__pycache__/*.pyc`) into user repositories.
6. **Command Execution & Scratch Scripting**:
   - For ad-hoc diagnostic scripts, use inline execution for quick checks (< 20 lines / < 750 chars) to avoid multi-turn tool overhead; use scratch scripts for large (> 20 lines) or iterative tasks. Always distill command output over 12 lines.

---

## 4. MCP Interface Compatibility

The MCP server (`src/laya_agent/server.py`) exposes 13 tools. All public tool names and argument aliases must be strictly preserved:
- `laya_status`
- `filter_candidate_files` (aliases: `file_paths`, `candidates`, `paths`, `task`)
- `fast_symbol_search`
- `distill_command_output` (aliases: `goal`, `raw_output`, `threshold`)
- `locate_code_regions` (aliases: `file_path`, `path`, `task`, `goal`)
- `verify_patch_state` (aliases: `file_path`, `expected_snippet`, `check_syntax`)
- `triage_user_goals` (aliases: `prompt`)
- `laya_triage_error` (aliases: `error_trace`)
- `verify_hypothesis` (aliases: `hypothesis`, `evidence`)
- `extract_doc_guidelines` (aliases: `doc_path`, `focus_topic`, `topic`, `task`, `query`, `file_path`, `path`)
- `audit_plan_requirements` (aliases: `user_prompt`, `planned_steps`, `plan_file_path`)
- `laya_decide`
- `laya_systemone_batch`

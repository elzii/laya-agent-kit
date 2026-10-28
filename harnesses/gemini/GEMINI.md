# Laya Agent Kit

When the `laya-agent-kit` MCP server is connected, use its tools for phased System-1 gating. The full portable protocol is available as the `laya-system1-gating` skill.

- Compound requests: call `triage_user_goals` before broad discovery; audit multi-step plans with `audit_plan_requirements`.
- Discover paths with `fd`/`fdfind`; search text with `fast_symbol_search` or `rg` as appropriate; pass candidate paths through `filter_candidate_files`.
- For files over 50 lines, prefer `locate_code_regions` over whole-file reads or sequential paging. Use `extract_doc_guidelines` for focused documentation retrieval.
- Ad-hoc scripts: use inline execution (e.g. `python3 -c`) for quick checks (< 20 lines / < 750 chars); use scratch files in the host scratch/artifact directory for larger scripts (> 20 lines / > 750 chars) or iterative tasks.
- Distill command/test/browser output over 12 lines with `distill_command_output`.
- On failures, use `laya_triage_error`; test assumptions with `verify_hypothesis`.
- After edits, use `verify_patch_state` for snippet/syntax checks and run relevant tests. It is not proof of behavioral correctness.
- If Laya returns fallback/errors or is unreachable, do not restart/retry it automatically; use targeted local tools and treat Laya-backed judgments as indeterminate.
- Use the host's supported plan-artifact mechanism; do not assume other harness-specific tools exist.

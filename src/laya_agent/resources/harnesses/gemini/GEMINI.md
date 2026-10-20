# Laya workflow

Use the `laya-agent-kit` MCP server for code retrieval, triage, diagnostic distillation, and patch checks when it is available. The official Laya inference server is an external dependency at `http://127.0.0.1:8000` by default.

## Operating rules

- For compound tasks, use `triage_user_goals`; before a multi-step or risky plan, use `audit_plan_requirements`.
- Prefer `fd` and `rg` for initial discovery. Use `filter_candidate_files` only to prioritize candidates, not to prove omitted files irrelevant.
- Avoid reading whole files over about 50 lines when a targeted search or `locate_code_regions` can establish the relevant context. Read the complete file when correctness genuinely requires it.
- Use `extract_doc_guidelines` to retrieve task-relevant portions of large instructions or documentation.
- Distill command output only when it is long; retain the original output and investigate missing evidence.
- After edits, inspect `git diff` and use `verify_patch_state` plus actual tests/type checks as appropriate. Do not reread whole files solely to confirm a patch if focused verification is sufficient.
- Laya model judgments are advisory. On retrieval failure, fall back to normal tools; on verification failure, report `indeterminate`/failure rather than success.
- Preserve every explicit user requirement and ask before destructive or irreversible actions when appropriate.

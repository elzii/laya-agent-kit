# Laya workflow

Use the `laya-agent-kit` MCP tools when they are available and materially useful for code retrieval, triage, debugging, or patch verification. Laya runs as a separate official service, normally at `http://127.0.0.1:8000`.

- Use `triage_user_goals` for compound requests and `audit_plan_requirements` for substantial plans.
- Start with `rg`/`fd`; use Laya filtering and region localization to focus inspection, not to prove completeness.
- Keep original logs available when using `distill_command_output`.
- Treat model classifications as hypotheses. Confirm them using source, reproduction, and tests.
- Inspect the actual diff and run relevant tests. A successful `verify_patch_state` is not proof of behavioral correctness.
- Fall back to normal tools if Laya is unavailable. Do not turn a service error into a green check.

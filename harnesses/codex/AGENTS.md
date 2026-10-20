# Laya workflow

When the `laya-agent-kit` MCP tools are configured, use them as a focused aid for code navigation, triage, and verification. The official Laya inference server is external and defaults to `http://127.0.0.1:8000`.

- Preserve all explicit requirements. For compound tasks, use `triage_user_goals`; audit substantial plans with `audit_plan_requirements`.
- Start with repository-native `rg`/`fd`; use Laya to prioritize candidate files and locate regions in long files. Do not interpret a missing Laya match as proof of absence.
- Use `distill_command_output` for long diagnostic logs and `extract_doc_guidelines` for large docs when it will reduce irrelevant context.
- Treat classifications and hypothesis scores as advisory. Inspect source and reproduce behavior.
- Review the actual diff and run appropriate tests/type checks. `verify_patch_state` is a narrow check, not a replacement for testing.
- If Laya fails, continue with normal tools; never report a failed or indeterminate verification as success.

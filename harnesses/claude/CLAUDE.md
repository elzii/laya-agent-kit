# Laya workflow

When the `laya-agent-kit` MCP tools are available, use them to reduce unnecessary code reading and to structure triage. The official Laya inference server is external and defaults to `http://127.0.0.1:8000`.

- For compound requests, call `triage_user_goals`; audit substantial plans with `audit_plan_requirements`.
- Start with `fd`/`rg`, then use `filter_candidate_files` to prioritize candidates and `locate_code_regions` to focus long-file inspection. A Laya shortlist is not exhaustive.
- Use `distill_command_output` for long logs and `extract_doc_guidelines` for long documents only when relevant.
- Treat `laya_triage_error` and `verify_hypothesis` as suggestions, not proof.
- Review the actual diff and run appropriate tests. `verify_patch_state` checks only its specified conditions.
- If the server is unavailable, use normal repository tools. Never treat a service error or indeterminate result as approval or verification success.

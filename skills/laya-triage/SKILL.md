---
name: laya-triage
description: Triage compound coding requests and audit implementation plans.
---

# Laya task triage and planning

1. For a request with multiple distinct objectives, call `triage_user_goals` before broad discovery. Identify dependencies and the primary blocker; handle related goals in a deliberate order rather than starting every workstream at once.
2. Before a multi-step implementation, call `audit_plan_requirements` with the original user request and explicit planned steps. Check that each requirement is represented in the plan.
3. Treat unavailable, fallback, malformed, or ambiguous output as **indeterminate**, not approval. A score is decision support, not a substitute for reading the requirements or exercising judgment.
4. Prefer the smallest plan that satisfies the request. Preserve explicit constraints, acceptance criteria, and requested deliverables; do not silently drop secondary requirements.
5. When the host supports a user-visible plan artifact, use that host's native mechanism. Do not assume another harness's artifact directory, `write_to_file` API, metadata, or `file://` link conventions.

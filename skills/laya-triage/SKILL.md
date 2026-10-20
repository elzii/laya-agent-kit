---
name: laya-triage
description: Use Laya to prioritize compound coding requests and audit an implementation plan before acting.
---

# Laya triage

Use this skill when the request contains multiple independent changes, an unclear first blocker, or a plan with several steps.

1. Preserve every explicit user requirement. Laya's classification is advisory and must not erase a requirement.
2. Call `triage_user_goals` with the complete user request when it is compound or ordering is unclear.
3. Draft a concise, ordered plan with observable outcomes and dependencies.
4. For a multi-step or risky plan, call `audit_plan_requirements` with the original request and the proposed steps.
5. If the audit is `indeterminate`, unavailable, or malformed, review the plan manually. Never treat an error as approval.
6. Ask for confirmation before destructive, irreversible, external, or security-sensitive actions when confirmation is warranted.
7. Work on the highest-priority blocker first, then return to remaining requirements.

Do not call Laya for trivial single-step requests where it adds no value.

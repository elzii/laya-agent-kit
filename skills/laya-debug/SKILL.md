---
name: laya-debug
description: Diagnose errors using focused evidence and testable hypotheses.
---

# Laya debugging

1. Capture the exact error, the operation that triggered it, and concise surrounding context. Preserve the full raw log locally when it may be needed later.
2. For command, test, compiler, server, browser, DOM, or style output longer than 12 lines, use `distill_command_output(goal, raw_output)` before relying on the output in subsequent reasoning. Do not discard the original evidence merely because a summary was produced.
3. Call `laya_triage_error` for a traceback, failing test, layout issue, or reproducible bug before proposing a patch when the tool is available.
4. State a falsifiable root-cause hypothesis and use `verify_hypothesis(hypothesis, evidence)` before speculative multi-step changes when useful. Treat its score as a heuristic, not proof.
5. Separate observed facts, tool assessments, and plausible explanations. Confirm the diagnosis with a minimal reproduction, targeted test, or other independent evidence where practical.
6. If Laya is unavailable or returns fallback, use targeted local diagnosis and clearly distinguish that fallback from semantic Laya analysis. Never claim a hypothesis was Laya-verified when it was not.

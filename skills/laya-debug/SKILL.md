---
name: laya-debug
description: Triage an error, distill noisy logs, and evaluate a concrete debugging hypothesis.
---

# Laya debugging workflow

1. Capture the exact error, stack trace, command, relevant environment, and reproduction steps. Do not remove context that may distinguish competing causes.
2. Call `laya_triage_error` to get a provisional category. This is a search hint, not a root-cause finding.
3. Search the repository for the first relevant project frame, symbol, error string, and related tests.
4. For long output, call `distill_command_output` with a precise diagnostic goal. Keep the original output available; a distilled excerpt can omit important evidence.
5. State a falsifiable hypothesis and the evidence for and against it. Use `verify_hypothesis` only as a weak prioritization signal.
6. Prefer the smallest reproducible check: focused test, minimal reproduction, type check, or targeted command.
7. Change one causal factor at a time where practical. After the fix, rerun the reproducer and relevant regression tests.
8. If Laya is unavailable or returns `indeterminate`, continue with conventional debugging. Do not present an unverified model guess as fact.

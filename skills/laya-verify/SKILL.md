---
name: laya-verify
description: Review patches and test results against acceptance criteria.
---

# Laya patch and result verification

1. Map each material change to the user's acceptance criteria and inspect the diff/working tree for unintended edits.
2. Use `verify_patch_state(file_path, expected_snippet, check_syntax=true)` to confirm that the expected snippet exists and supported syntax checks pass. Prefer this to rereading a long file solely to see whether an edit landed.
3. Understand the boundary of that check: snippet presence and syntax validity do not establish behavioral correctness, integration compatibility, or satisfaction of the full request.
4. Run relevant tests, type checks, linters, formatters, builds, or focused manual checks when available. Choose checks based on the change rather than treating one generic test as sufficient.
5. Report each check as **passed**, **failed**, **skipped**, or **indeterminate**. Say what was actually run; never claim unrun tests passed or that an unavailable Laya result is verification.
6. If `verify_patch_state` is unavailable, use an appropriate local check and disclose that the Laya-backed check was unavailable when material.

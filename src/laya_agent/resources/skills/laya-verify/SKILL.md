---
name: laya-verify
description: Verify a code change with diff review, deterministic checks, and appropriate tests.
---

# Laya patch verification

1. Inspect the actual diff (`git diff --check` and `git diff`) rather than relying on a summary or an expected snippet alone.
2. Check that the patch implements the user request, preserves nearby invariants, and does not include unrelated changes.
3. Call `verify_patch_state` with a distinctive expected snippet. Supply `expected_absent` for a removed obsolete snippet where appropriate. If a pre-edit SHA-256 was captured, pass it as `expected_sha256_before`.
4. Interpret `verified` narrowly: it means only that the tool's requested local checks passed. It does not mean tests, type checking, behavior, or the entire patch are correct.
5. Run the smallest relevant test first, then broader tests or type/lint/build checks appropriate to the repository.
6. If verification returns `failed` or `indeterminate`, do not claim success. Inspect the diff and resolve the missing check.
7. Report what was changed, what checks actually ran, and any remaining uncertainty. Never claim a test passed unless it was run and passed.

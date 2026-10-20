---
name: laya-context
description: Find relevant files and narrow code regions without reading entire large files.
---

# Laya context retrieval

1. Start with repository-native discovery (`fd`, `rg`, directory listing, language/build manifests). Do not assume Laya replaces ordinary search.
2. For a large candidate list, call `filter_candidate_files` with the task and candidate paths. Treat the output as a shortlist, not proof excluded files are irrelevant. If Laya fails, use the original candidates.
3. Use `fast_symbol_search` for exact symbols, call sites, configuration keys, and error text.
4. For a long file, use `locate_code_regions` with a specific question about the logic being changed. Read only the reported regions plus enough surrounding context to understand callers and invariants.
5. Do not read an entire file just because one region is relevant. Files under roughly 50 lines can generally be read directly when useful.
6. Preserve file paths and line anchors in notes. A missing match is not proof that code does not exist; try alternate symbols, callers, tests, and configuration.
7. For project instructions or large documentation, use `extract_doc_guidelines` with the current task as `focus_topic`. If no sections match, inspect the source document directly.

Retrieval is a token-efficiency aid, never an authorization or security boundary.

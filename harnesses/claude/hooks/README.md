# Optional Claude Code hooks

This directory intentionally contains no automatically enabled hook scripts yet. Start with MCP tools plus `CLAUDE.md` and the portable skills. Hooks are harness- and version-specific; add one only after choosing a lifecycle event and defining a fast, deterministic check. Do not make a hook block work merely because the Laya service is unavailable. If you add hooks, document the event, command, timeout, exit-code behavior, and fallback here, then test with the exact Claude Code version you use.

# Design

Native text editors lex complete TOML statements, including quoted keys,
multiline strings, arrays and inline tables. Only provider/feature tables are
normalized; unrelated statements remain intact. Ambiguous or structurally
invalid input fails before replacement. Tests use Python tomllib as an independent
development-only oracle; generated client commands never invoke Python.

Relay identity requires its actor header, matching site endpoint, or a sk-clb
token with a Codex backend endpoint. A provider name alone is insufficient.
Cleanup removes relay URLs/token/transport overrides, only the relay actor header,
and selectors pointing to that provider. Unrelated headers/providers/model/MCP/
projects remain. Generic pre-existing model-discovery flags remain; flags newly
added by this generator are comment-marked for removal (or restoring prior false).

Both operations prepare a temporary result, preserve the original on errors,
back up before atomic replacement and do nothing when unchanged. Cleanup neither
reads an older backup nor changes auth.json or server-side keys. POSIX utilities
and PowerShell 5.1+ are the supported base environment, not arbitrary shell-less
or policy-restricted devices.

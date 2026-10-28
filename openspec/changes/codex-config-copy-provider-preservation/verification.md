# Verification

## Local checks (2026-10-28)

- 61 focused tests passed across native command execution, command dialog,
  clipboard helper, shared CopyButton and visitor access.
- Native fixtures ran with Windows PowerShell 5.1 and Git Bash. The complete
  parsed configuration after cleanup equals its previous value with only the
  three permitted provider fields deleted. Root/profile selectors, provider
  identity, headers, legacy auth and feature flags remain unchanged; repeated
  cleanup makes no additional backup or write.
- Two headless Edge browser scenarios passed for administrator and visitor.
  The UI was served at a genuinely insecure HTTP origin, without Clipboard API.
  Actual clipboard comparisons verified the complete setup, cleanup and
  platform-switched commands. Only fake API responses and credentials were used;
  clipboard contents were compared inside the browser and not logged.
- Focused ESLint and the production TypeScript/Vite build passed.
- Strict OpenSpec validation passed for this change and all 68 main specs.

## Requirement mapping

| Requirement | Implementation | Regression evidence |
| --- | --- | --- |
| Native commands explicitly invoke Bash | commands.ts quoted /bin/bash heredoc | commands.test.ts, including zsh where installed |
| Preserve provider identity; remove three fields only | edit_config.awk and edit_config.ps1 cleanup | Whole-document TOML comparisons, dotted empty provider, legacy auth and no-op tests |
| One-click command copying | shared CopyButton and clipboard.ts | copy-command.test.tsx, clipboard.test.ts and real HTTP browser clipboard checks |

The implementation follows the design: shared clipboard behavior, minimal
native cleanup changes, and no dependency or authentication changes. History
files and real user configuration were not inspected or modified. Cross-platform
cloud CI and frontend deployment are still pending; do not archive yet.

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

## Cloud and deployment checks

- Code commit `0421ed7ef5f7943b3ea0a9bf3e707fc4f0f4f47d` passed all four jobs
  in [Relay fork checks](https://github.com/XXXShaunPan/codex-lb/actions/runs/40646617842):
  the native relay regression gate and native command tests on Ubuntu, macOS
  (including /bin/zsh) and Windows.
- Frontend assets were deployed additively, then the HTML entry was replaced
  atomically. Live HTML and the commands bundle matched the verified build.
  Backup: `C:\Users\cncb_choice\Desktop\.codex-lb\backups\frontend-config-copy-20261028T145754`.
  Older hashed assets remain available for open tabs and rollback.
- Both administrator and visitor browser clipboard scenarios passed again
  against the production-served assets on port 8080. API data was mocked, so
  these checks did not rotate or export a real key.
- Readiness returned HTTP 200; service process ID stayed 7240. There was no
  service restart, database migration or server Key mutation.

## Final assessment

All five tasks and all three requirements are covered. The implementation follows
the design: shared clipboard behavior, minimal native cleanup changes, and no
dependency or authentication changes. History files and real user configuration
were not inspected or modified. Main specs and user documentation are synchronized.
No outstanding critical, warning or coherence findings; ready for archive.

# Standalone production checkout

The inspected Windows service runs `uv run --no-sync codex-lb --host 0.0.0.0 --port 8080` with `codex-lb-custom` as its working directory. Its editable `.pth`, package `direct_url.json`, launcher shebang, and `python -I` module resolution all identify that production checkout. Its base Python interpreter is managed by uv outside both project directories. No runtime import migration or environment reinstall is necessary.

The maintenance checkout is the only initially usable Git repository; the production `.git` file points to a deleted old worktree parent. The 5,506 tracked files have five actual content differences (tests/specifications), 52 line-ending-only differences, and no missing baseline files. Runtime application files already match the verified maintenance copies. New diagnostics/test/change-record files must also be retained.

The operator explicitly reported the desktop weather test successful before requesting consolidation and publication. This closes the local include-compatibility verification, but does not authorize unrelated runtime changes. Preserve the known-good service during Git/documentation synchronization; temporary diagnostic retirement remains a separate tracked cleanup.

Database, encryption material, saved API-key tokens, `.env`, logs, virtual environments, generated assets, and one-off deployment backups are not publication inputs. Keep the old checkout until the remote branch and independent production checkout have been verified; no deletion is performed by this change.

## Verification record

- Published compatibility commit `011fbd1c` and diagnostic commit `eee76da6` to the fork's `custom/main` without force pushing. Remote ref verification matched the latter commit.
- Synchronized 23 reviewed test/specification/change-record files. No runtime source file was copied or edited during consolidation; those files were already identical to the verified versions.
- Preserved the previous worktree pointer and the historical one-off frontend deployment helper under `<data>/service/backups/standalone-checkout-20261028-173532/`.
- Production now owns a complete `.git` directory on `custom/main` tracking `origin/custom/main`, with no object alternates or external common directory. `git fsck --connectivity-only` passed and the production working tree was clean at `eee76da6`.
- Isolated production Python resolved `app` inside `codex-lb-custom`, and its own environment contained the test dependencies. The live health endpoint remained healthy; runtime-source, service-XML and frontend-index hashes plus the service process ID were unchanged.
- The same focused regression suites were run directly with `codex-lb-custom/.venv/Scripts/python.exe -I -B`: 347 tests passed in 147.44 seconds, with only the existing Starlette/AnyIO deprecation warning. This verifies the production checkout's source and test environment without importing from the maintenance checkout. Strict validation of all main OpenSpec capabilities also passed.
- Published the operations guidance and consolidation record as `6491fd05`; production fast-forwarded to that exact remote commit after verifying the update touched only documentation. Its working tree remained clean and the health endpoint stayed healthy. The maintenance checkout was deliberately not deleted.

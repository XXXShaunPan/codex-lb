# Deployment — 2026-10-29

The user authorized implementation, Git publication and production activation.

- Feature commit: `e508a052` (quadratic quota preference and ent26 USD balance).
- Activated head: `3044b67f` (standard Intel macOS runner, unchanged runtime).
- [Matching-head cloud checks](https://github.com/XXXShaunPan/codex-lb/actions/runs/40904311531)
  passed all four jobs, including real macOS Bash/zsh coverage. The earlier ARM
  job could not acquire hosted capacity; no test failure or gate was bypassed.

An isolated production build was pinned by source/build fingerprints, with
PowerShell 7 / 5.1 ordinal-hash compatibility checked. Online SQLite backups
passed integrity verification before cutover. After service stop, the database
had no nonempty WAL, so a complete native copy was flushed before restart; the
full readonly integrity scan then ran after readiness to avoid unnecessary
downtime. A WAL-aware SQLite backup path remained available if needed.

Private backups, prior source/frontend, configuration/encryption material and
deployment receipts are under the service data directory at
`backups/quadratic-quota-usd-20261029T232402`. They include credentials and must
not be published. No schema migration or historical-fee rewrite was performed.

Service stop was requested at 23:48:09.714 +08:00 and readiness returned at
23:48:37.198 +08:00: a measured maintenance window of 27.5 seconds. PID changed
from 12260 to 4892. The frontend entry was switched atomically after backup and
live-state verification completed. Previous content-hashed resources remain.

Live HTML and dashboard/settings/accounts bundles match the prepared build.
Entry SHA256: `D2D197159499BC6F9233244D2D526133E3732B8A49F17A7E87D62FCD1833212D`.
Both health endpoints return 200. The browser smoke scenario passed against
the live HTTP service with fake API data, showing the USD balance and quadratic
explanation without exporting a real key or making a billable model request.

Readonly database checks confirm three ent26 USD balances, monthly reset fields
and squared-quota scores, with three Model Sources still at the 100% placeholder.
Normal quota polling resumed (oldest ent26 observation was 90 seconds old on
follow-up). API credentials/recoverable tokens, visitor credentials/assignments,
account/source weights, dashboard settings, legacy priority rules/bands, service
configuration and encryption key remained unchanged. No API key was rotated.

Rollback should restore matching source/frontend while preserving current data.
Do not replace newly accepted request accounting with an old database snapshot
without explicit reconciliation and a maintenance window.

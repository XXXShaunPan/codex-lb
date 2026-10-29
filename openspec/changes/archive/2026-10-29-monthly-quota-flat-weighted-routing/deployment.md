# Deployment verification — 2026-10-29

The user explicitly authorized Git publication and production activation after
the local implementation was verified.

## Published and activated code

- `75a8dbb5`: monthly ent26 quota presentation and flat custom-weighted routing.
- `0a12df28`: update the remaining image mixed-pool regression to the new random
  probability contract. It asserts both candidates' real scores rather than the
  retired priority ordering; no runtime changes were needed for this follow-up.
- All four jobs passed on the activated head in
  [Relay fork checks](https://github.com/XXXShaunPan/codex-lb/actions/runs/40827523994).
  Publication is on `origin/custom/main`.

The release frontend was rebuilt from committed source in an isolated directory.
Its full source/build fingerprints were pinned before service control, including
an ordinal path ordering check across PowerShell 7 and Windows PowerShell 5.1.
Private deployment helpers and receipts are not committed to the repository.

## Backup and cutover

An online SQLite snapshot and a final stopped-service snapshot both passed
integrity checks. The final copy was hash-checked against the stopped database;
the legacy visitor database, service configuration, encryption material, old
entry point and previous source archive were also backed up. Private recovery
artifacts are under the service data directory at
`backups/monthly-quota-flat-routing-20261029T140329`.
These backups contain credentials and must not be published.

No schema migration was required or performed. New content-hashed frontend
assets were added without deleting old resources. The HTML entry point was
replaced atomically only after backend readiness and data-invariant checks.

Service control began at 14:16:54 +08:00 and cutover completed at 14:23:32 +08:00.
The unavailable interval was approximately six minutes, longer than anticipated
because the final database copy/hash/integrity verification was slow. Service
PID changed from 5552 to 12260; both health endpoints subsequently returned 200.

## Post-deployment verification

- Live HTML and the accounts, settings and API-page bundles match the verified
  release build. Entry SHA256:
  `D172000F401A2CF16B7543241D4BC787AA5C5AB1F9FCC18D00ECBE9ECD2D2D3A`.
- Read-only checks of all three ent26 accounts confirm monthly percentage/reset
  projection and quota-derived routing scores. All three Model Sources retain
  their 100% placeholder. Existing strategy remains `custom_weighted_quota`.
- A follow-up check confirms normal quota refresh resumed (oldest ent26 snapshot
  was 100 seconds old), not merely that pre-restart values remained readable.
- API credentials, recoverable configuration tokens, visitor credentials and
  assignments, account/source weights, dashboard settings and stored legacy
  priority rules/bands match the pre-start invariant snapshot. No keys were reset.
- Browser smoke checks use production-deployed static assets with mocked API
  fixtures; no billable model request or real credential export is needed.

Rollback should restore matching source/frontend under an explicit maintenance
window while retaining current data. Do not overwrite newly accepted request
accounting with an older database snapshot without reconciliation.

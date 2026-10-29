# Deployment verification — 2026-10-29

The user explicitly authorized database backup, migration, frontend publication
and service restart after the local implementation was verified.

The production-sized rehearsal passed repeated upgrade, schema-policy,
schema-drift, integrity and foreign-key checks. Existing table counts and
account/API-key/visitor credential fingerprints were unchanged. An initial
online backup hit its deadline; no failed or partial copy was accepted. A fixed
WAL read snapshot and backup-only write optimization produced the verified
rehearsal database without changing the live database's configuration.

The service was stopped, a final verified database backup was taken, and
20261028_000000_add_provider_spend_controls was applied and checked. Content-hashed
frontend assets were added without deleting old bundles; the entry point was
replaced atomically after backend readiness passed. The restarted service is
healthy and serves the verified frontend build.

All target ent26 accounts subsequently acquired fresh snapshots through normal
background refresh. Read-only verification of the real database confirmed that
account presentation exposes the USD budget, omits synthetic subscription
windows, and passes the same remaining percentage into routing state. No model
generation or credential reset was needed for these checks.

Backup/receipts are in the private service data directory under
backups/enterprise-spend-control-20261029T102344. It contains the final store.db,
legacy visitor database, encryption material, service configuration, old entry
point, baseline source archive, candidate-source overlay and deployment receipt.
Do not publish these artifacts: database backups include recoverable API tokens.

The deployed source fingerprint is
C0AD2D3EE050CA8E475451CE83BC504EABFD894A130A4678B34F6F00F9B1EF76.
The frontend entry fingerprint is
51FB8155888FB2FBF444B83A30FC6303F2DBC411378D57244A4744E58C22FD3C.
At deployment time, Git publication had not been requested; the verified patch
was deployed from the local working tree over 5da935f2. The operator subsequently
authorized Git publication on 2026-10-29. Only source, tests and documentation
belong in that commit; private backup and deployment artifacts remain local.

Rollback must preserve/reconcile any requests accepted after the backup. Retain
the current database before rollback and use the tested migration downgrade and
matching source/frontend restore under a maintenance window; do not silently
replace current accounting data with an older snapshot.

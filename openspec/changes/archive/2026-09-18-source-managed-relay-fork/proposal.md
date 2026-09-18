# Source-managed relay fork

## Why

The deployed relay depends on an external sitecustomize patch set. Upstream
v1.25 introduced a second source settlement path that escaped that patch and
recorded successful GPT-6 requests at zero cost. The operator has authorized a
maintained fork with native source integration and independent feature commits.

## What Changes

- Move virtual-account selection, assignments and report projections into
  maintained modules with explicit source integration points.
- Centralize source billing and persist immutable price/usage breakdowns for
  new requests; distinguish customer charges from unknown provider costs.
- Integrate visitor access and Codex configuration generation into the normal
  backend and frontend build; preserve existing visitor credentials and scopes.
- Make Compass compatibility and control-log classification source-owned.
- Publish custom/main and custom release tags; document merge-based upstream
  upgrades with backups, one Alembic head and rollback.

## Impact

Base release: v1.25.0-beta.7. Production remains on the existing installation
until isolated migration, backend, frontend and HTTP checks pass. No upstream
release upgrade is bundled into this migration. No historical price snapshot
is fabricated for old rows.

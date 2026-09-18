# Relay fork operations

Normative requirements: [relay fork specification](../openspec/specs/relay-fork/spec.md).

## Source and feature ownership

- `upstream`: original `Soju06/codex-lb`, read-only upstream history.
- `origin`: `XXXShaunPan/codex-lb`; `main` remains the mirror.
- `custom/main`: deployable relay patch stack, initially based on `v1.25.0-beta.7`.
- `integration/<release>`: isolated upgrade branch.

The native feature modules are `virtual_accounts`, `provider_billing`,
`visitor_access`, `codex_config`, and `provider_compatibility`. Definition-time
adapters are explicitly declared at upstream integration points. No startup
code rewrites upstream methods, FastAPI route dependants or frontend assets.
Frontend controls are React components compiled into `app/static`.

The Windows service must use the custom checkout as its working directory.
Remove the legacy injection `PYTHONPATH` and feature-enable variables. Keep
`CODEX_LB_DATA_DIR`, the encryption key, normal topology configuration and the
explicit recovery/telemetry preferences. `X-Relay-Version` identifies the
custom deployment independently of the upstream app version.

## Database cutover

Stop the service before the final backup/cutover. Back up `store.db`,
`visitor-portal.db`, `encryption.key`, service XML and the external injection
package. Do not copy a live SQLite database using a plain file copy: use the
SQLite backup API or stop every writer first.

With `CODEX_LB_DATA_DIR` set to the target data directory:

```bash
uv run codex-lb-db upgrade head
uv run codex-lb-db check
uv run python -m scripts.import_relay_visitors /path/to/visitor-portal.db
uv run python -m scripts.import_relay_visitors /path/to/visitor-portal.db --apply
```

Visitor IDs, bcrypt hashes, session versions and key assignments are imported
without password resets. Re-running the importer does not restore subsequently
revoked assignments. Conflicting existing credentials abort the import.
The original external database is retained for rollback; new changes live in
`visitor_accounts` and `visitor_api_keys` under Alembic management.

New source billing evidence is persisted atomically with request logs in
`provider_billing_entries`. Each entry freezes the catalog rates, pricing
policy/version hash, actual reported tier, usage dimensions, customer charge
and observed amount. A missing actual tier uses standard pricing. Priority,
Fast and Flex use the same catalog calculator as the account pool, including
its long-context threshold. Source rates are used only for unknown catalog
models. Provider cost, tool cost and cache-write charges remain unknown when
the provider does not supply authoritative values; they are not invented or
silently added to the account-pool tariff. Explicitly reported cache-write
token counts are retained. Historical logs retain their stored charges and do
not receive fabricated historical price snapshots.

The upstream dispatch owner continues to settle/release reservations exactly
once. Estimated missing-usage/client-cancel settlement is marked separately
from reported usage. Failure attempts have zero customer charge in the ledger;
unknown upstream cost remains null. Existing core cancellation and retry
contracts remain authoritative.

Reports preserve the virtual-account behavior of the prior deployment. The
custom source-account reports still read retained request logs; historical
source detail already pruned before migration cannot be reconstructed.

## Following a selected upstream release

Use merge-based integration so the shared custom branch never needs a force push:

```bash
git fetch upstream --tags
git switch -c integration/vX.Y.Z custom/main
git merge --no-ff vX.Y.Z
```

Review conflicts by feature. If both sides add Alembic revisions, add a new
merge revision to restore a single head; never edit a deployed revision.
Enable `rerere` locally, but review reused conflict resolutions before staging:

```bash
git config rerere.enabled true
git config rerere.autoupdate false
uv sync --frozen --all-extras --dev
uv run python -m scripts.check_relay_source
uv run pytest tests/unit/test_relay_provider_billing.py tests/integration/test_relay_native.py tests/unit/test_source_dispatch.py tests/integration/test_model_source_dispatch.py -q
cd frontend
bun install --frozen-lockfile
bun run test src/features/codex-config/commands.test.ts src/features/visitor-access/relay-access.test.tsx
bun run build
```

Test migrations on a current production backup, run the same migration twice,
verify visitor scope/login/logout, account/source routing, report filters and
normal/long-context/tier billing. Against the candidate service, the live smoke
command creates a short-lived Compass-only key, submits synthetic text, checks
the recorded cost, and removes the temporary key:

```bash
uv run python -m scripts.smoke_relay_http
```

This probe consumes a small amount of upstream usage. Tests and CI use stub
providers and must never be pointed at the production database.

After local checks, staged deployment and `Relay fork checks` CI pass:

```bash
git switch custom/main
git merge --ff-only integration/vX.Y.Z
git tag -a custom-vX.Y.Z.1 -m 'Relay release based on vX.Y.Z'
git push origin custom/main
git push origin custom-vX.Y.Z.1
```

Push only the selected custom tag, not every upstream tag. Keep commits grouped
by feature; do not squash the whole fork into one custom commit. Update
`app/core/relay_build.py` when cutting a custom release.

## Rollback

Stop the service, retain the failed deployment database for diagnosis, restore
the pre-cutover database and service XML, and start the previous checkout with
its retained injection package. Do not point an old release at a newer schema
without a separately tested rollback plan. Any requests accepted after the
backup require reconciliation before restoring that backup.

After cutover, users should refresh the dashboard to load native bundles. The
old visitor JSON endpoints remain aliases during migration; external JS/CSS
and `sitecustomize` are no longer part of application startup.

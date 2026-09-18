# Relay fork implementation and verification

The first source-managed deployment retains upstream `v1.25.0-beta.7` and is
identified by `custom-v1.25.0-beta.7.1`. Domain commits separate virtual-account
routing/continuity, account projections, billing evidence, visitor persistence
and access, Codex configuration, provider compatibility, and explicit core
integration points.

Definition-time service adapters receive the native callable explicitly.
There is no startup installer or assignment to upstream class methods/module
functions. The frontend is a normal React build. The original external package
and pre-cutover database remain rollback artifacts, not runtime dependencies.

The production-copy migration reached one Alembic head with no schema drift.
Visitor import preserved IDs, hashes, versions and authorizations, and the
second import was a no-op. The two retained upstream prewarm observation
columns are represented in the ORM so existing database migrations and model
metadata agree without deleting historical data.

Verification on 2026-09-18 included 199 backend tests (source dispatch,
cancellation/release, scope enforcement and immutable billing), five frontend
tests, TypeScript production build, feature lint/type checks, all 66 OpenSpec
specifications, and browser checks of administrator login, visitor login/logout,
source-account detail, read-only navigation/settings and the key-reset warning.
The same gate passed on GitHub Actions for the custom branch.

The Windows service cutover removed the injection PYTHONPATH and moved its
working directory to the native checkout. Health returned HTTP 200 with the
custom build header. A synthetic Compass GPT-6 HTTP/SSE probe completed with
32 input / 16 output tokens and USD 0.00112, with matching durable price
version evidence. Subsequent live long-context attempts also produced billing
entries. The temporary probe key was deleted. A deliberately minimal control
probe returned an upstream validation error, and correctly remained a labeled
control attempt with no invented token usage.

Provider costs and supplemental cache-write/tool charges remain unknown unless
authoritatively supplied. This deployment does not infer a provider invoice
from the customer tariff or fabricate price versions for historical rows.
The [operations runbook](../../../docs/relay-fork-maintenance.md) covers future
merge-based upgrades, migration validation, live probes and rollback.

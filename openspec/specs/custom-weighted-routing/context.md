# Implementation and operational notes

The strategy is named `custom_weighted_quota`. Real account weights live on
`accounts.routing_weight` and virtual-account weights on
`model_sources.routing_weight`. A separate admin endpoint unifies both kinds
without putting credentials into its response. Writes invalidate the native
selection cache, including its cross-replica invalidation signal.

Reported short/long usage is retained separately from synthetic lease pressure.
The new selector runs after hard availability filtering and before the native
health-tier, burn/preserve, reset-time and planner-preference stages. Explicit
owners and existing mappings retain continuity even after weight is set to
zero. The virtual-pool first-source fallback is disabled for this strategy.
Source-only embeddings also use the same weights, with subscription accounts
excluded from their candidate pool.

Validation covers 673 backend cases across routing, concurrency, source dispatch,
visitor isolation, billing and the new API/migration. Fifty frontend routing
tests and the production build passed. Migration tests start from the prior
head, preserve existing rows, verify default weights, repeat upgrade, downgrade
and upgrade again. Non-finite JSON numbers, boolean values, deleted accounts
and visitor access are rejected.

This release was prepared in an isolated worktree. Production was deliberately
left on the previous checkout and process. The manual activation script checks
a committed tag and hashed frontend build before stopping the service; its
`-CheckOnly` mode is read-only. See the
[operator guide](../../../docs/custom-weighted-routing.md) for activation and
the score formula. OpenSpec CI is pinned to the previously validated 1.13.1
because later CLI versions changed warning severity for unchanged upstream
specifications; the full strict validation gate remains enabled.

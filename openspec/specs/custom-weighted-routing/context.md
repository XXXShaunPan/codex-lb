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

The flat-pool follow-up retires the priority extension from assignment. Every
eligible account competes by `weight * minimum_known_remaining_fraction`, with
probability equal to its score divided by the total score. This is a random draw,
not an argmax: weight 2 at 50% and weight 1 at 100% have equal probability across
plans. ent26 uses its upstream monthly allowance; different dollar limits do not
change a percentage score. A Model Source remains at a 100% placeholder until
provider polling is implemented.

Legacy `relay_routing_rules` and `relay_routing_quota_bands` records are retained,
but neither native nor mixed-source assignment reads or updates them. The admin
rules APIs are deprecated storage compatibility only, and their UI editors are
removed. No migration or destructive data cleanup is required.

No known applicable quota means no new allocation; a confirmed absent short window is ignored in minimum
mode. Source placeholders are explicitly labeled, including in account details.
Mixed source/real routing removes real accounts at their hard concurrency cap
before the probability draw. Already-owned requests bypass new-allocation
policy, but retain hard security, capability and availability checks.

Regression tests cover cross-plan probabilities, lower-score wins, current quota
minima, ent26 allowance normalization, native/mixed-source paths, inert saved
rules, zero/unknown quota, continuity and hard availability constraints. Legacy
API validation and visitor restrictions remain enforced.

The follow-up was initially prepared as local source changes with isolated test
databases and frontend output. After explicit authorization it was published and
activated on 2026-10-29 without a migration, setting change or credential rotation;
see the [deployment record](../../changes/archive/2026-10-29-monthly-quota-flat-weighted-routing/deployment.md).
The manual activation script checks
a committed tag and hashed frontend build before stopping the service; its
`-CheckOnly` mode is read-only. See the
[operator guide](../../../docs/custom-weighted-routing.md) for activation and
the score formula. OpenSpec CI is pinned to the previously validated 1.13.1
because later CLI versions changed warning severity for unchanged upstream
specifications; the full strict validation gate remains enabled.

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

The priority extension stores full plan/account rules in `relay_routing_rules`
and persistent per-account quota bands in `relay_routing_quota_bands`. Lower
numbers win; default Plus is 10/30 and all others 20/20. Only the best eligible
group reaches the random draw. Account overrides replace the entire plan rule;
removing the override restores inheritance. Band decisions happen outside the
balancer runtime lock, using normalized reported windows and transaction-owned
DB sessions. SQLite writer serialization / PostgreSQL row locks protect band
transitions. Older observations cannot reverse newer transitions. A changed
threshold/basis fingerprint re-evaluates the band under the new rule.

Unknown requested quota demotes ordinary accounts. No known applicable quota
means no new allocation; a confirmed absent short window is ignored in minimum
mode. Source placeholders are explicitly labeled, including in account details.
Mixed source/real routing removes real accounts at their hard concurrency cap
before choosing a priority group. Already-owned requests bypass new-allocation
policy, but retain hard security, capability and availability checks.

Validation covers routing, concurrency, source dispatch, visitor isolation,
billing, priority rules, persistent hysteresis, stale observations, and the new
API/migrations. Fifty-nine frontend cases and the production build passed.
Migration tests start from the prior
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

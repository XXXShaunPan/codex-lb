# Local verification — 2026-10-28

Implementation is complete locally. Deployment is deliberately separate: this
side task did not create commits, push branches, migrate the live database,
restart the service, replace production assets or rotate credentials.

## Evidence

- 161 tests passed in the first budget/migration/updater batch.
- 372 existing account API, probe, relay, priority and load-balancer tests passed.
- The final targeted batch passed 326 tests covering new budgets, polling,
  priority rules and concurrent selection, including the last stale-window fix.
- The migration/repository follow-up passed all five tests. Upgrade is idempotent,
  downgrade/re-upgrade works and schema drift checks pass. Exactly one Alembic
  head remains: 20261028_000000_add_provider_spend_controls.
- Five frontend test files / 54 tests passed, including list/detail/dashboard
  rendering and visitor-access regressions. TypeScript and production build passed.
- Focused Ruff, ty, ESLint and git diff whitespace checks passed.
- All 69 main OpenSpec specs and this change validated strictly.
- Headless Edge verified the account page using mocked API data. Before/after
  screenshots are under frontend/test-results/spend-control-enterprise-spending-budget-on-account-page/.
  The new assets are served by an isolated port-4177 preview, not production.

## Coverage and coherence

| Requirement | Evidence |
| --- | --- |
| Durable per-seat snapshots | API/repository tests use two seats sharing one workspace and different budgets; older writes lose; deletion cascades |
| Accurate budget-only presentation | Decimal precision, different limits, unknown values, null clearing and stale synthetic-window suppression tests |
| Exhaustion / recovery | Real Account-to-routing-state and cloned state tests; bypassed subscription quotas do not bypass spending controls; elapsed time does not replenish budgets |
| Weighted admission | Real priority runtime consumes budget percentages without fake windows and keeps existing rules |

New logic follows the existing usage repository/background ownership pattern and
uses a prefixed extension table rather than modifying prior migrations. No
outstanding correctness or completeness findings from local verification.
Cloud CI had not run at the local-verification stage because no commit/push had
been requested. The existing workflow includes the new tests for Git publication.

## Live state left unchanged

- Service remained Running with process ID 11040; readiness returned HTTP 200.
- Live revision remains 20261027_010000_add_image_routing_settings and the new
  budget table does not yet exist in the live database.
- Production app/static/index.html still hashes to
  4D1DDF99708C0785226FD5C81465F0A88042D1593B540AF21FC31FD91667E683.
- The candidate frontend was built only into .local/spend-control-build.

This section records the pre-deployment state. See [deployment.md](deployment.md)
for the separately authorized 2026-10-29 rollout and subsequent Git-publication scope.

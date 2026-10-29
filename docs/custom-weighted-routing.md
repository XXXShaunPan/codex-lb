# Custom weight × minimum remaining quota

Normative contract: [custom weighted routing](../openspec/specs/custom-weighted-routing/spec.md).

In Settings → Routing, select **Custom weight × remaining quota**. Administrators
can edit weights below the strategy or in an account's detail view.
Weight defaults to 1; zero excludes
new assignments. Decimal values from 0 to 1,000,000 are supported.

All eligible accounts participate in **one pool**, without plan/account priority
groups or low-quota downgrade rules. Legacy priority configuration is no longer
shown or consulted during allocation; its stored records are retained for
compatibility, and the old admin APIs are marked deprecated.

`score = configured weight × minimum known remaining fraction`.
`P(account) = score / sum(all eligible scores)`.
The fraction is the minimum of applicable normalized short and long quota
windows (weekly or monthly as appropriate), bounded to 0..1. The ent26 monthly
allowance comes from its real upstream spending-control percentage; different
monetary allowance sizes do not change the score. Missing windows are not
invented. Completely unknown/invalid quota receives no new assignments.
Model Sources, including Compass, retain 100% and no five-hour
window; that is explicitly a **routing placeholder, not real upstream balance**.
An account with weight 2 and 50% remaining has the same probability as one
with weight 1 and 100% remaining. Selection is a proportional random draw,
not a guarantee of an exact ratio over a small number of requests.

Across the whole pool, plan capacity, reset preference, burn/preserve preference, soft health
tiers, planner cost, latency, error-rate multipliers and synthetic inflight
pressure do not change the scores. Hard scope, authentication, model support,
pause/deactivation, cooldown/backoff and concurrency caps still apply.
Existing session/response/file ownership is retained even when its operator
weight becomes zero; the probability rule governs only new assignments.
If every score is zero, selection fails closed instead of choosing the first
source or falling back to an unweighted pool. Other strategies are unchanged.

## Manual activation of a prepared Windows release

Development takes place in a separate checkout. Publishing does not change the
active checkout, frontend assets, database or service process. Build the
frontend there, commit the source, tag the release and run:

```powershell
# From the prepared checkout; stamps the source tree and artifact checksums.
.\.venv\Scripts\python.exe -m scripts.stamp_frontend_build
# Safe preflight: does not stop the service or change production state.
.\scripts\activate-prepared-release.ps1 -DataDir 'C:\path\to\.codex-lb' -CheckOnly
```

When ready, open **Administrator PowerShell**, enter the prepared checkout and
run the same command without `-CheckOnly`:

```powershell
.\scripts\activate-prepared-release.ps1 -DataDir 'C:\path\to\.codex-lb'
Invoke-WebRequest 'http://127.0.0.1:8080/health' -UseBasicParsing |
    Select-Object StatusCode, Headers
```

The script verifies a clean tagged checkout, matching frontend checksums,
unchanged runtime dependencies and a fast-forward relationship. It then stops
the service, backs up the database/configuration/encryption key and old static
assets, fast-forwards the **current deployment directory**, copies the verified
build, runs and checks migrations, and starts the service. It retains old
hashed assets so already-open clients can finish loading them. Refresh the
dashboard afterward, configure weights and explicitly select the new strategy.

Earlier migrations added account/source weights and independent `relay_routing_*`
rule/hysteresis tables. The flat-pool follow-up needs no migration and does not
delete those records or change current strategy settings/account assignments.
If this strategy is already selected, the new probability formula takes effect
for new assignments after the operator activates the prepared code.
The script intentionally refuses releases that change runtime dependencies;
those require a separately prepared runtime. On failure, inspect the printed
backup path and service state before recovery; no automatic rollback overwrites
requests accepted after a successful start.

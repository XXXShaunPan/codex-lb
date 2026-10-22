# Priority groups + custom weight × remaining quota

Normative contract: [custom weighted routing](../openspec/specs/custom-weighted-routing/spec.md).

In Settings → Routing, select **Custom weight × remaining quota**. Administrators
can edit weights, plan rules and account overrides below the strategy, or edit
an account's override in its detail view. Weight defaults to 1; zero excludes
new assignments. Decimal values from 0 to 1,000,000 are supported.

Default groups (smaller priority numbers win):

| Group | Normal priority | Low-quota priority |
| --- | --- | --- |
| Plus | 10 | 30 |
| Other plans, including Model Sources | 20 | 20 |

Only the highest-priority **available** group participates, regardless of total
weight in lower groups. Each plan can set normal/low priority (0–10000), the
threshold basis (weekly/long window, five-hour, or minimum applicable windows),
downgrade and recovery thresholds, and whether low-band accounts may receive
new assignments. Default downgrade is **below 20%**, recovery **at least 25%**.
The band is persisted across restarts. A value of 22% stays low after 19%, but
stays normal if the account has not crossed below 20%. Recovery must exceed
downgrade. Disabling low-band admission for Plus disables the last-resort
fallback. Explicit account overrides replace the whole plan rule; uncheck the
override and save to restore inheritance. `*` is the default for non-Plus plans
without their own rule. Plus has its own built-in default.

Within the selected group, `score = configured weight × remaining fraction`.
The fraction is the minimum of applicable normalized short and long quota
windows (weekly or monthly as appropriate), bounded to 0..1. The basis controls
**threshold decisions**, not permission to bypass another known exhausted
window. Missing requested windows put ordinary accounts in the low band;
known quota still supplies their weight. Completely unknown quota receives
no new assignments. Confirmed weekly-only accounts have no short window in
minimum-applicable mode. Model Sources retain 100% weekly and no five-hour
window; that is explicitly a **routing placeholder, not real upstream balance**.
An account with weight 2 and 50% remaining has the same probability as one
with weight 1 and 100% remaining. Selection is a proportional random draw,
not a guarantee of an exact ratio over a small number of requests.

Within a group, plan capacity, reset preference, burn/preserve preference, soft health
tiers, planner cost, latency, error-rate multipliers and synthetic inflight
pressure do not change the scores. Hard scope, authentication, model support,
pause/deactivation, cooldown/backoff and concurrency caps still apply.
Existing session/response/file ownership is retained even when a rule disables
new allocations; priorities and weights govern only new assignments.
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

The migrations add account/source weights and independent `relay_routing_*`
rule/hysteresis tables. They leave current strategy settings and existing
account assignments unchanged. If this custom strategy is already selected,
the new default grouping takes effect for new assignments after activation.
The script intentionally refuses releases that change runtime dependencies;
those require a separately prepared runtime. On failure, inspect the printed
backup path and service state before recovery; no automatic rollback overwrites
requests accepted after a successful start.

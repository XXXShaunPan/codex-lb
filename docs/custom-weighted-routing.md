# Custom weight × remaining quota

Normative contract: [custom weighted routing](../openspec/specs/custom-weighted-routing/spec.md).

In Settings → Routing, select **Custom weight × remaining quota**. Edit weights
in the table beneath that strategy or in an individual account's detail view.
Real accounts and Model Sources use the same controls. Only administrators can
read or change them. Each account defaults to 1; zero excludes new assignments.
Decimal values from 0 to 1,000,000 are supported.

For each eligible candidate, `score = configured weight × remaining fraction`.
The fraction is the minimum of applicable normalized short and long quota
windows (weekly or monthly as appropriate), bounded to 0..1. Absent windows
are neutral (100%); Model Sources retain 100% weekly and no five-hour window.
An account with weight 2 and 50% remaining has the same probability as one
with weight 1 and 100% remaining. Selection is a proportional random draw,
not a guarantee of an exact ratio over a small number of requests.

Plan capacity, reset preference, burn-first/preserve preference, soft health
tiers, planner cost, latency, error-rate multipliers and synthetic inflight
pressure do not change the scores. Hard scope, authentication, model support,
pause/deactivation, cooldown/backoff and concurrency caps still apply.
Existing session/response ownership is retained; weights govern new assignments.
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

The migration adds `routing_weight` columns to `accounts` and `model_sources`.
It leaves current routing settings and existing account assignments unchanged.
The script intentionally refuses releases that change runtime dependencies;
those require a separately prepared runtime. On failure, inspect the printed
backup path and service state before recovery; no automatic rollback overwrites
requests accepted after a successful start.

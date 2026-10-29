# Context and operational notes

Read-only probes on 2026-10-28 observed ent26 usage responses with HTTP 200,
rate_limit=null and spend_control.individual_limit denominated in USD. Official
[workspace usage-control guidance](https://learn.chatgpt.com/docs/enterprise/usage-limits)
supports plan-dependent spending controls; the concrete wire fields here are
based on the observed endpoint, not a promised public API schema.

For example a USD 200 allowance with USD 116.67 remaining can report 58% remaining,
while another seat in the same workspace can have a USD 50 allowance. The client
keeps upstream decimals and the reported percentage rather than assuming one
plan-wide allowance. Missing fields remain unknown, and the next reset comes
from upstream, not a fabricated five-hour/week/month duration.

provider_billing_spend_controls stores one typed snapshot per local account ID.
It is unrelated to customer API-key spend limits and does not rewrite request
fees or historical subscription snapshots. Account selection clones include
the snapshot. Successful polling invalidates selection caches and its durable
observation timestamp prevents polling storms when subscription windows are
absent. Explicit null clears the budget; omission/errors retain prior evidence.

Budget-only accounts use their budget percentage in custom weighted routing;
the tightest remaining fraction is squared before applying the custom weight.
All eligible plans share one probability pool; legacy priority/hysteresis rules
are no longer consulted. Reached controls are a hard
filter even when standard subscription quota is bypassed. Elapsing a reset time
does not itself prove that an exhausted budget was replenished.

The monthly/flat-pool follow-up projects ent26 percentage and reset time into
the existing monthly account-summary fields. Standard quota rows replace the
separate spending-budget panel. Raw monetary snapshots/API fields remain for
compatibility; no duration, reset date or subscription credits are fabricated.
The later USD display uses spendControl.remaining in existing subscription-quota
card/table fields, with the USD symbol. This presentation value is not fed into
credit aggregates or probability scores, and unlike units are not compared as
one numeric quantity when sorting. Missing/non-USD balances stay unknown.
The operator separately authorized activation on 2026-10-29; see the
[monthly/flat-pool deployment record](../../changes/archive/2026-10-29-monthly-quota-flat-weighted-routing/deployment.md).

Deployment is separate from this local side-task implementation. Before enabling
the modified code, back up the database, apply the new forward migration and
restart the backend through the normal operator-controlled workflow, then install
the frontend build and verify a read-only usage poll. No real credentials need
rotation and historical money/usage must not be backfilled with invented values.

The operator authorized deployment on 2026-10-29. Migration, frontend publication
and service restart completed, and normal background refresh populated the target
accounts' real budgets. See the archived change's
[deployment verification](../../changes/archive/2026-10-28-enterprise-spend-control/deployment.md)
for the backup and validation record. Git publication was authorized separately
after rollout; private production backups are not part of the source repository.

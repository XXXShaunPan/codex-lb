# Enterprise spend-control quotas

## Why
Some accounts (observed plan type ent26) return HTTP 200 with rate_limit=null
and an individual USD budget under spend_control. The current parser discards
that object and the updater returns before persisting any current quota.

## What Changes
- Persist typed spend-control snapshots per local account, independent of usage windows.
- Expose actual budget amounts, percentages, reset time and observation time.
- Show budget quotas in account list, dashboard cards and account details.
- Exclude exhausted budgets from selection without fabricating subscription windows.

## Impact
One additive migration, usage polling, account summaries and quota presentation.
No credential changes, historical fee corrections, commits or live deployment.

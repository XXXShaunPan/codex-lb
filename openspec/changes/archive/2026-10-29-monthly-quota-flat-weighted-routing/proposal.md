# Monthly enterprise quotas and a flat weighted pool

## Why
The new ent26 upstream quota reader works, but the monetary spending-budget UI
does not match the desired monthly quota presentation. The custom weighted
strategy still filters by plan/account priorities before drawing, preventing
otherwise equal accounts from participating on equal terms.

## What changes
- Reuse ent26 spend-control snapshots as monthly percentage/reset presentation;
  remove the separate spending-budget panel without changing ingestion or money.
- Draw all eligible accounts together using custom weight times their minimum
  known applicable remaining fraction, including enterprise monthly allowance.
- Keep Model Source quota at a clearly labeled 100% placeholder.
- Retire priority-group and low-band admission from this strategy and its UI.
  Preserve legacy stored rules/API compatibility without consulting them in routing.

## Scope
Source and isolated tests/build only. No production restart, frontend publication,
live routing-setting change, credential rotation, migration or historical rewrite.

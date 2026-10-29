# Stronger quota preference and enterprise balance display

## Why
Linear quota weighting does not sufficiently reduce low-quota selection. ent26
also has a real remaining USD allowance that can fill the existing subscription
quota display without reintroducing a separate spending-budget panel.

## What changes
- Use custom weight multiplied by squared minimum remaining fraction for new
  random assignments. Keep the flat pool, source placeholder, hard limits and
  existing session ownership; do not square the operator's custom weight.
- Show ent26's actual upstream USD remaining amount with a dollar symbol in the
  existing subscription quota column/card. Keep monthly percentage/reset and
  keep USD separate from subscription credits and aggregate quota accounting.
- Update regression/distribution tests, explanatory text and documentation,
  then commit and deploy after matching-head cloud checks and verified backups.

No new configuration, database migration, credential reset or historical rewrite.

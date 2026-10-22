# Priority groups for custom weighted routing

## Scope

Update the opt-in custom strategy to choose the lowest numbered eligible
priority group before drawing by weight and reported remaining quota.
Administrators manage plan defaults and full per-account overrides. Defaults:
Plus 10 / low 30, all other plans 20 / low 20, downgrade below 20%, recover
at 25%, minimum applicable short/long quota, low-quota fallback allowed.
Persist hysteresis across restarts. Unknown ordinary quota cannot grant a
normal-priority admission; fully unknown quota cannot receive new traffic.
Source quota is explicitly a placeholder, not provider balance. Preserve
continuity and all hard availability checks. Leave production running.

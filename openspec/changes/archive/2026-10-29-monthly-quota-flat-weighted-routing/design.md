# Design

Keep the typed spend-control storage and existing polling freshness/exhaustion
rules. Normalize ent26's remaining percentage and upstream reset into the existing
AccountUsage monthly fields. Never invent a 30-day duration or convert USD into
subscription credits. Account list, card and detail reuse their normal quota
rows; unknown monthly percentages remain unknown. Retain the raw spendControl
API field for compatibility but do not display monetary budget controls.

The custom selector reads normalized reported AccountState quota values before
synthetic inflight pressure. Take the minimum known applicable fraction, or zero
if all are unknown/invalid. Budget-only accounts ignore obsolete subscription
rows. Model Source placeholders remain 1.0. Scores are sampled by random.choices;
only internal availability probes may use deterministic selection. No priority
rules or hysteresis data are read/written during assignment. Retain authenticated
legacy rules endpoints as deprecated, inert configuration for compatibility.

Keep hard authentication, scope, model capability, pause/cooldown, exhaustion,
concurrency and continuity constraints. Existing owned sessions are not randomly
moved on every turn. Do not modify other strategies or active configuration.

Regression coverage includes actual account API normalization, mixed real/source
and native assignment paths, differing plans and stale saved rules, partial and
unknown quota, monthly/short minima, distribution and lower-score selection,
continuity, UI reset labels and absence of retired controls.

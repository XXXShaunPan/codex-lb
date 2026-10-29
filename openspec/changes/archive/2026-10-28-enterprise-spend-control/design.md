# Design

Use a separate provider_billing_spend_controls table keyed by local account ID;
different users in one workspace must never share or overwrite a budget. Store a
typed JSON snapshot and its observation time. Keep monetary values as decimal
strings. Include whether upstream returned real rate-limit windows and its credit
flags so budget-only responses never reuse stale synthetic 5h/weekly records.

Add one eager scalar relationship to Account and preserve it when making routing
snapshots. Save through request/background usage repository ports before the
existing empty-rate-limit return. Successful snapshots govern poll freshness even
without standard usage rows. Explicit null clears a prior control; an omitted
field or failed query does not fabricate fresh availability. Older concurrent
observations cannot overwrite newer ones.

Use one shared budget display across account surfaces. Do not infer monthly or
weekly duration, impose a fixed dollar allowance, or combine dollars with credits.
The authoritative reached flag or a nonpositive explicit remaining amount excludes
the account from selection, including standard-quota bypass paths. Recovery needs
a later successful snapshot, not a locally assumed reset. Keep account status and
credentials independent; budget filtering must not overwrite paused/reauth states.

Work locally against isolated test databases. Do not restart the service, migrate
the live database, push Git refs or change production assets in this side task.

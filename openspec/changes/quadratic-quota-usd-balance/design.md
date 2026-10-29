# Design

Use score = w * q^2, q = minimum known applicable remaining fraction clamped to
[0,1]. Squaring only q strengthens the same-weight preference while preserving
linear operator control: 80% versus 20% becomes a 16:1 odds ratio instead of 4:1.
No threshold cutoff or positive score offset is added. Positive low quotas can
still win; unknown/invalid/zero quotas and zero weights remain excluded. Source
q remains 1 until quota polling exists. Continuity is not a new allocation.

The ent26 amount is already available as spendControl.remaining plus its unit.
Use the existing USD formatter after validating a finite nonblank numeric value
and a USD unit. Do not infer money from percentages or credits. Render in the
existing subscription-quota locations, retain the monthly quota row, and keep
the legacy numeric credits accessor/aggregate paths unchanged. Table sorting
groups USD and credits and sorts values only within the same unit.

Tests exercise exact scores, cross-plan equality, random lower-score wins,
quota separation, image/mixed source request paths, missing/invalid/zero/negative
balances, both dashboard surfaces and existing normal-account output. Publish
with an isolated frontend build, immutable source/build fingerprints and a
database backup. Avoid the prior release's repeated small-block full-file hashes
while stopped; use a bounded, efficient database verification path.

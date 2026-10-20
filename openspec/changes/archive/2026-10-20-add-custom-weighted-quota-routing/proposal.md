# Custom weight and remaining quota routing

## Why
Operators need direct control over the share of new requests assigned to each
subscription account and virtual model-source account, without implicit plan,
reset-time, latency or historical-error ranking factors.

## What Changes
- Add opt-in `custom_weighted_quota` strategy to dashboard settings.
- Persist a finite per-account/source weight (default 1, range 0..1,000,000).
- Draw from eligible accounts proportionally to weight times the smallest
  applicable remaining quota fraction. Use reported quota before synthetic
  inflight/leased-token pressure; absent windows are neutral (100%).
- Expose administrator-only weight controls for real and virtual accounts.
- Keep hard availability/security/cap constraints and existing continuity.
- Prepare a separately built release; do not restart or migrate the live service.

## Impact
Two additive columns; one new Alembic revision. Existing strategies and active
production settings remain unchanged. No upstream version upgrade is included.

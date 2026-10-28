## Implementation

- [x] Add bounded rejected-include diagnostics without changing validation outcomes.
- [x] Verify protocol identifiers, whitespace indicators, secret/free-text redaction, valid-request silence, and native/v1 route behavior.
- [x] Run regression tests, lint/type checks, and strict spec validation; sync the new requirement.

## Activation

- [x] Back up and deploy only the two affected runtime files; perform the approved restart without changing integrity settings.
- [x] Verify health and a synthetic rejected option using the existing Mac key without an upstream call or key reset.
- [x] Capture a new user replay and identify the actual rejected option before deciding any further compatibility change.
- [ ] Remove temporary include-option instrumentation once the incident is diagnosed and the targeted fix is verified.

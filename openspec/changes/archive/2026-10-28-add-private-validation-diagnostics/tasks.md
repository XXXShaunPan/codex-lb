## Implementation

- [x] Add bounded, privacy-preserving validation diagnostics.
- [x] Wire local Pydantic, client-payload, and framework validation errors without altering response contracts.
- [x] Verify redaction, correlation, and native/compatible Responses routes with regression tests.
- [x] Run focused tests, lint/type checks, and strict OpenSpec validation; sync verified requirements.

## Activation

- [x] Enable on the shared deployment only after restart timing is authorized; verify health and a synthetic rejected request without model calls.
- [x] Ask the user to reproduce the desktop failure and inspect its diagnostic, without treating the synthetic test as the original root cause.

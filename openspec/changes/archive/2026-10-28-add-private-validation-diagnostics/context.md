# Private validation diagnostics

The first failing location is enough to narrow the current desktop problem without storing the original request. Example (synthetic, not a diagnosis of the reported weather query):

```text
request_validation_diagnostic request_id=<request-id> stage=local_validation source=pydantic field=include error_type=value_error
```

A matching line establishes local rejection. Absence of a line is not by itself proof of an upstream failure: correlate the same request's other logs and verify that the running process has loaded the patch. The displayed field is sanitized, not a copy of a JSON value. Only the first validation failure is logged, and paths stop at twelve components. Unknown schema/union labels are redacted deliberately. Non-UUID request IDs use `sha256:` plus the first sixteen hexadecimal digest characters for correlation.

No new environment setting, payload capture, database change, account/key mutation, or upstream model call is required. The change does not attempt to fix an unknown failing schema field.

## Verification

- 2026-10-28: 57 focused tests passed: 44 across the new unit/integration suites and existing passthrough request validation suite, plus 13 existing OpenAI-compatible rejection tests. Existing Starlette/AnyIO deprecation warnings only.
- Ruff lint and formatting, targeted `ty check`, strict change validation, and all 68 main OpenSpec capabilities passed before deployment.
- The production request-policy and exception-handler files matched the maintained repository's HEAD baseline before patching. The shared service restart was explicitly approved by the user after tests.
- Production backups: `<data>/service/backups/validation-diagnostics-20261028-151921/`. The three deployed Python files were byte-identical to their tested source copies before restart.
- The approved restart began at approximately 15:20 China time. The new server reached the existing SQLite startup `quick_check` at 15:20:52 and did not yet bind port 8080. Unlike the previous 1.7-second check, this scan encountered very slow disk reads and a high disk queue. A supplemental read-only scan was cancelled to avoid competing for I/O. The user explicitly chose to wait for the full check rather than bypass it; no integrity-check setting or database content was changed by this patch.
- The full `quick_check` passed at 15:37:36 after 1004.5 seconds. Startup completed at 15:37:39; `/health` subsequently returned `{"status":"ok"}`. No integrity check was bypassed.
- At 15:39:12, a deliberately malformed JSON request without an API key or model reached the real native Responses route and returned the unchanged HTTP 400 envelope. The console recorded `request_id=<request-id> stage=local_validation source=framework field=9 error_type=json_invalid`. This confirms activation without an upstream model request or token billing. It is only a synthetic activation probe, not the user's weather-query failure.
- The user replayed the Mac desktop weather query at 15:44. At 15:44:55, request `<request-id>` produced `stage=local_validation source=pydantic field=include error_type=value_error`, followed by the native Responses route's HTTP 400. This identifies the local include allowlist rejection before upstream selection. The actual include enum remains private and was not captured. The separately authorized compatibility fix is tracked in `accept-web-search-results-include`.

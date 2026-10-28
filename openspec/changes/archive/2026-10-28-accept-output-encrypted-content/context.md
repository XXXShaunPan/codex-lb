# Observed desktop encrypted-output include

The real request IDs `<request-id>` and `<request-id>` failed on the exact option `output.encrypted_content`, without surrounding whitespace, at 16:32:22/23 China time on 2026-10-28. These were the user's desktop weather-query replays, not synthetic probes.

The [public Responses reference](https://developers.openai.com/api/reference/typescript/resources/responses), checked on the same date, documents `reasoning.encrypted_content` but does not establish that the observed desktop option is an alias for it. The fix therefore preserves the observed wire value without interpreting or decrypting any content. No claim is made about universal support by third-party providers.

The earlier `web_search_call.results` addition addressed a separate documented compatibility gap and did not resolve this incident. This change is based on the captured actual trigger. Tests use stubbed upstreams; a deliberately invalid secondary field can prove live include acceptance without dispatching a billable request. End-to-end desktop success still requires a replay after activation.

## Verification and activation

- Before the fix, all four newly added native/v1 schema cases failed on `include` with `Unsupported include value: output.encrypted_content`.
- After the one-entry allowlist change, 347 tests passed in 141.74 seconds. Coverage includes schema serialization, native/v1 HTTP and trailing slashes, model-source route forwarding, WebSocket normalization/rejection, and privacy diagnostics. The only warning is the existing Starlette/AnyIO deprecation.
- Ruff formatting/lint, targeted type checks, strict change validation, and strict validation of all main OpenSpec capabilities passed.
- Runtime backup: `<data>/service/backups/output-encrypted-include-20261028-164838/requests.py`.
- The deployed file was byte-identical to tested source: SHA-256 `B4F38B9FBB93CD6DC8C5BF7B5305106AA155F9A036EE95363EFA8D572D127818`.
- The approved restart stopped the old server at 16:50:38 and completed startup at 16:50:49 China time on 2026-10-28. The existing clean-shutdown policy skipped the redundant SQLite scan automatically; no integrity-check setting or run-state sidecar was manually changed. `/health` returned `{"status":"ok"}`.
- At 16:51:53, a native Responses probe using the scoped existing test key and only `include=["output.encrypted_content"]` passed include validation and stopped at a deliberately invalid `truncation` field (`<request-id>`). A control mixing the newly supported value with an unknown option still stopped at `include` (`<request-id>`). Neither request reached upstream or token billing; no key was reset or printed.
- The user subsequently confirmed that the original desktop weather test passed. This verifies the reported incident's end-to-end outcome, without claiming universal support for every provider or tool. Temporary diagnostic retirement is tracked separately; repository consolidation preserves the now-verified running code.

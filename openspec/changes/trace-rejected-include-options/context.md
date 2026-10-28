# Temporary rejected-include tracing

The preceding compatibility change accepts the documented `web_search_call.results` option, but the user's 16:04:39 replay (`<request-id>`) still failed at `include/value_error`. The actual value has not been captured. This instrumentation is authorized to diagnose that value, not to accept guessed protocol options.

Only the rejected include string reaches the diagnostic helper, never the payload or the validation exception. A name must fit a bounded ASCII identifier grammar and a response-item root (`message`, `reasoning`, `response`, `input`, `output`, `text`, or a `*_call`/`*_output` family); sensitive markers are blocked. Surrounding spaces may be trimmed for display with an explicit boolean; embedded whitespace or control characters are redacted. There is no raw-value fallback, value hash, or persistent request-body capture. A redacted entry is not evidence that it is a valid protocol option.

The existing generic validation event remains value-free. The temporary event can be removed by removing the validator hook and helper after diagnosis; do not change the allowlist based only on this synthetic instrumentation test.

## Verification and activation

- 2026-10-28: 331 regression tests passed, including native/v1 HTTP forwarding/rejection, WebSocket normalization/rejection, request schema behavior, and extended diagnostic privacy. The only warning was the existing Starlette/AnyIO deprecation.
- Ruff formatting/lint, targeted type checks, strict change validation, and strict validation of all main OpenSpec capabilities passed.
- Backups: `<data>/service/backups/include-diagnostic-20261028-162413/` (`requests.py` and `validation_diagnostics.py`). Production baselines were checked before modification and both deployed files matched the tested copies byte for byte afterward.
- Deployed SHA-256: `requests.py` = `E8B6B431E227EB804632A55683F5B298BC6E6E57CDAED4260C082C0F21ACF971`; `validation_diagnostics.py` = `2B747FB01559D5926B773DC4E552FF2B37E6C3619D0EA47C6161900290880CA5`.
- User-approved restart: the old server stopped at 16:26:19; the replacement completed startup at 16:26:30 (China time). Existing clean-shutdown handling automatically skipped a redundant SQLite scan; no integrity setting or sidecar was manually changed. `/health` returned `{"status":"ok"}`.
- At 16:28:04, an intentionally invalid `web_search_call.diagnostic_probe` request returned HTTP 400 and emitted the exact protocol option under request ID `<request-id>`. A separate synthetic credential-shaped include emitted only `[redacted]` under request ID `<request-id>`. Both used the scoped existing test key privately, without printing/regenerating it, and stopped before upstream dispatch or token billing.
- The user's new weather-query replay at 16:32:22/23 produced two real diagnostics for `output.encrypted_content`, with `whitespace_trimmed=false`, under request IDs `<request-id>` and `<request-id>`. This identifies the actual rejected option. The user explicitly authorized its targeted fix and restart, tracked in `accept-output-encrypted-content`. Keep the temporary trace until the targeted fix is verified against the desktop replay, then remove its hook.

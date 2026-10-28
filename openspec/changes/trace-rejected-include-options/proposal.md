## Why

The Mac desktop replay at 2026-10-28 16:04:39 still failed local `include` validation after the documented `web_search_call.results` compatibility fix. Existing metadata-only diagnostics deliberately omit the rejected option, so adding more guessed values is not justified. The user explicitly authorized a narrow diagnostic expansion and restart.

## What Changes

- Emit a separate, bounded diagnostic for only the first rejected include option during an active request.
- Expose only protocol-shaped names from response-item families; redact credentials, free text, unknown families, malformed names, and oversized values. Report stripped surrounding whitespace as a boolean without changing validation.
- Preserve the current include allowlist, external errors, routing, billing, and generic private validation diagnostic.
- Add privacy and native/v1 product-path tests before deployment.

## Impact

- Runtime: `app/core/validation_diagnostics.py` and one hook in the existing include validator.
- Spec: `proxy-runtime-observability`.
- No database, API-key, provider, or integrity-check setting changes.
- This is temporary incident instrumentation. Remove its validator hook after the actual rejected option has been captured and the targeted compatibility decision is verified.

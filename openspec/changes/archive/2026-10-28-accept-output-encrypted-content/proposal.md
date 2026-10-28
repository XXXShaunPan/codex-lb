## Why

Expanded diagnostics captured the actual Mac desktop failure at 2026-10-28 16:32:22 and 16:32:23: the native Responses route rejected `include=output.encrypted_content` locally. This is no longer a guessed option. The user explicitly requested a targeted fix and restart.

## What Changes

- Add only `output.encrypted_content` to the shared Responses include allowlist.
- Preserve it verbatim and independently of `reasoning.encrypted_content`; do not alias, delete, or inject either option.
- Cover native/v1 schemas, account HTTP routes and trailing slashes, model-source forwarding, WebSocket creates, and continued unknown/type-error rejection.
- Keep narrow incident diagnostics until an actual desktop replay confirms the remaining request path, then retire the temporary hook as tracked separately.

## Impact

- Runtime: one allowlist entry in `app/core/openai/requests.py`.
- Spec: `responses-api-compat`.
- No database, key, model-selection, routing, billing, or integrity-check configuration changes.
- This is compatibility with an observed desktop wire value, not a claim that every upstream provider documents or accepts it. Real upstream acceptance remains a separate verification step.

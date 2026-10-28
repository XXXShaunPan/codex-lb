## Why

The 2026-10-28 15:44:55 desktop reproduction failed locally with `field=include error_type=value_error`, before upstream selection. The shared Responses include allowlist omits the documented `web_search_call.results` value; a synthetic request with that value reproduces the exact validation failure. The private diagnostic intentionally did not capture the user's actual value, so the exact desktop enum remains unconfirmed.

## What Changes

- Add only `web_search_call.results` to the existing shared Responses include allowlist.
- Preserve existing include values, forwarding behavior, type checking, and rejection of unknown values.
- Add schema, native/v1 HTTP, equivalent trailing-slash route, and WebSocket forwarding/rejection regression coverage with stubbed upstreams.

## Impact

- Spec: `responses-api-compat`.
- Runtime code: one allowlist entry in `app/core/openai/requests.py`.
- No migrations, provider/routing changes, key changes, new logging content, or configuration flags.
- Test before deployment; retain the full database startup integrity check. A production replay from the user is required to confirm the original desktop issue is resolved.

# Reusable Codex configuration and image routing

See [requirements](spec.md) and the [user guide](../../../docs/relay-config-images.md).

New and regenerated API tokens are recoverable in `codex_config_api_tokens`.
The empty-table migration deliberately leaves existing hashes and prefixes
untouched: the first export of each historical key requires a confirmed reset.
Normal regeneration also updates the pool. A stored token whose SHA256 differs
from the authentication hash cannot be exported.

For example, a visitor assigned key A may export A repeatedly without resetting
it, but cannot inspect key B's status or retrieve B. Choosing reset invalidates
old clients; removing relay configuration does not undo a server-side key reset.
Database and backup access now grants access to saved tokens. Protect both,
along with generated commands and config.toml, as credentials.

The generated commands explicitly invoke /bin/bash with awk, or built-in PowerShell 5.1+; no client
Python, Node, package installation, downloaded executable or configuration upload.
It derives URLs from the web origin, updates the active custom provider or
`openai_https`, stores the token inline, enables model discovery and retains
unrelated configuration. Structurally ambiguous TOML fails before writing; an unchanged result
creates no redundant backup. The legacy key file is left untouched but no
longer used by the configured provider.

Restore means targeted cleanup, not replacing the file with a historical backup.
Only base_url, model_catalog_url and experimental_bearer_token are removed from
identified relay providers. Provider IDs/names, root/profile selectors, headers,
legacy auth readers, transport options and all feature flags remain unchanged.
History files are not accessed. If an earlier restore already removed a provider,
its original identity must be recovered from the user's backup rather than guessed.
Both operations keep timestamped backups and atomically replace the prepared result.
The native command tests use tomllib solely as an independent development oracle.

The command button uses the shared dialog-aware CopyButton. Its fallback remains
synchronous with the click gesture, copies within the active focus trap on HTTP,
and does not promise success when all browser clipboard mechanisms are denied.

The native-only commands and targeted cleanup were deployed on 2026-10-28 after
macOS/Ubuntu/Windows CI and administrator/visitor browser verification. Only the
frontend resources changed, with no service restart or server Key mutation.

The public `gpt-image-2` model remains independent of the Responses host.
`/api/image-routing/settings` is admin-only. An empty host selects from the
catalog; visible subscription image-input entries with explicit image-tool
support and positive catalog priorities are preferred. An explicit host is
useful when upstream capability metadata is incomplete. It cannot override
API-key account scope or make an unavailable upstream model available.

Source-only keys do not need a subscription host. Source Images requests use
native generations/edits endpoints, preserve files and masks, and enter the
same priority/weight/hysteresis selection as text requests. Streams close their
transport and release admission even before the first response body or after
client cancellation. A limited key with missing terminal usage fails closed.

Subscription logs contain public model, separate `image_host_model`, and
reported image-tool tokens. Source logs retain the source identity and durable
pricing snapshot. Both use the existing account-pool image tariff; it currently
uses one input rate, so this is a customer tariff, not exact text/image-modality
reconciliation with a provider invoice. No historical fees are rewritten.

## Verified deployment

`custom-v1.25.0-beta.7.4` passed the relay CI gate on 2026-10-27 and was deployed
without rotating the three existing keys. Live low-quality image probes verified
both Compass native Images routing (20 input / 196 output tokens, USD 0.00598)
and subscription routing with independent `gpt-6.1-terra` host (20 / 386 tokens,
USD 0.01168). Probe keys and visitors were removed afterward. The deployed UI
matches the production build and both health endpoints return 200.

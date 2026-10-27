# Reusable Codex configuration and image routing

See [requirements](spec.md) and the [user guide](../../../docs/relay-config-images.md).

New and regenerated API tokens are recoverable in `codex_config_api_tokens`.
The empty-table migration deliberately leaves existing hashes and prefixes
untouched: the first export of each historical key requires a confirmed reset.
Normal regeneration also updates the pool. A stored token whose SHA256 differs
from the authentication hash cannot be exported.

For example, a visitor assigned key A may export A repeatedly without resetting
it, but cannot inspect key B's status or retrieve B. Choosing reset invalidates
old clients; restoring config.toml does not undo a server-side key reset.
Database and backup access now grants access to saved tokens. Protect both,
along with generated commands and config.toml, as credentials.

The generated Bash/PowerShell command requires Python 3.11+ (no pip packages).
It derives URLs from the web origin, updates the active custom provider or
`openai_https`, stores the token inline, enables model discovery and retains
unrelated configuration. Invalid TOML fails before writing; an unchanged result
creates no redundant backup. The legacy key file is left untouched but no
longer used by the configured provider.

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

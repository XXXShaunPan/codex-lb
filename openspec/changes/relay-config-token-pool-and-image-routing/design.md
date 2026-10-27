# Design

## Decisions

- A small `codex_config_api_tokens` table owns recoverable plaintext tokens,
  as requested. Native creation/regeneration stores the token in the same
  transaction as its authentication hash. Foreign-key deletion cascades.
  The migration creates an empty pool and does not rotate historical keys.
- Configuration status is non-secret; export is a scoped, no-store POST.
  Visitors retain their assigned-key permissions. Optional rotation is explicit;
  absent or mismatched saved tokens require confirmation. General key reads
  continue to exclude plaintext tokens.
- Bash and PowerShell embed a dependency-free Python 3.11+ updater. `tomllib`
  validates input and output before a timestamped backup and atomic replacement.
  Existing custom providers and unrelated settings survive the update. No
  second client-side secret file is created.
- `image_routing` contains host settings, native source forwarding and image
  log identity. Only small integration points touch upstream code. The shared
  virtual-account chooser receives the public image model and a separate
  subscription eligibility model, preserving priority/weight/hysteresis.
- Subscription requests retain the Responses image tool and existing tracked
  reservation settlement. A request-local identity object binds public model,
  independent host and terminal image-tool usage to detached logging. No host
  text-token usage is mislabeled as image usage.
- Source requests use native Images endpoints and the existing SourceDispatch
  owner. Its latch settles/releases the reservation, persists the immutable
  pricing quote and releases transport/admission exactly once. Limited keys
  require reported usage before the final image is exposed; incomplete previews
  do not create estimated charges.

## Constraints and trade-offs

The image host is a T3 dashboard setting in a relay-owned table, without a new
environment variable. Automatic selection uses visible subscription image-input
models, preferring explicit image-tool capability and catalog priority. Catalogs
without tool metadata cannot prove capability; the admin override resolves that
uncertainty without pinning a particular model in source.

Image billing deliberately reuses the existing account-pool tariff. It does not
claim provider-invoice accuracy or invent missing modality/cache-write/tool
prices. This change does not alter historical charges or expand the supported
public image-model/parameter validation matrix.

Plaintext token storage is an explicit security trade-off: restrict database,
backup and config-file access. Prefer HTTPS. Generated commands warn on HTTP.
The user's requested `requires_openai_auth=true` is preserved; the actor marker
is not a replacement for Bearer authentication or client authentication state.

## Verification and rollout

Test creation, native regeneration, deletion, missing/mismatched tokens,
rollback on token-write failure, visitor isolation and expired/inactive keys.
Execute generated commands on Windows locally and Bash in Linux CI, plus TOML
fixtures for dotted/quoted keys, features, multiple providers and multiline
content. Test source generation/edit/stream/disconnect, mixed-pool priority,
zero weights, native host/tool identity and billing. Upgrade a production-copy
database twice and check schema drift before the backed-up service cutover.

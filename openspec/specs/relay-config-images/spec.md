# Relay configuration and image routing

## Purpose

Define recoverable configuration export and unified image account routing while preserving credentials, scope and billing ownership.

## Requirements

### Requirement: Recoverable API token lifecycle
New and regenerated API keys SHALL persist their recoverable token in the main
database in the same transaction as the authentication hash. Deletion SHALL
remove the stored token. General key listings MUST NOT expose tokens.
Existing keys SHALL remain valid after migration and start with no recoverable
token. A stored token MUST match the current authentication hash before reuse.

#### Scenario: Native regeneration updates the pool
- **WHEN** an administrator regenerates a key through the normal API Key action
- **THEN** subsequent configuration export uses the new token
- **AND** the old token is no longer returned or accepted

### Requirement: Optional reset and scoped configuration export
Administrators and assigned visitors SHALL be able to export the saved token
without regeneration. Missing tokens and explicitly requested resets SHALL
require confirmation before regeneration. Retrieval MUST reject unassigned,
inactive or expired keys and MUST use no-store responses.

#### Scenario: First export of a historical key
- **WHEN** a key lacks a recoverable token and reset is not confirmed
- **THEN** export returns a reset-required response without changing the key

### Requirement: Idempotent Codex configuration updates
Commands SHALL back up config.toml before writing, update the active custom
provider when present, and otherwise use openai_https. They SHALL set name to
OpenAI, wire_api to responses, inline experimental_bearer_token,
requires_openai_auth=true, the x-openai-actor-authorization header to codex-lb,
and features.api_key_model_discovery=true. Base and model catalog URLs SHALL
derive from the website origin. Unrelated configuration SHALL be preserved.

#### Scenario: Existing custom provider and feature flags
- **WHEN** a user runs a generated command against an existing config
- **THEN** the active custom provider is updated without duplicate tables
- **AND** unrelated providers/features remain intact
- **AND** no separate token file is written

### Requirement: Separate image model and subscription host
The requested public image model SHALL remain the routing/accounting model.
Subscription image requests SHALL use an independently configurable Responses
host or select from the current catalog; no fixed gpt-5.5 host is permitted.
The image_generation tool SHALL retain the requested image model.

#### Scenario: Subscription image request
- **WHEN** gpt-image-2 is requested and a subscription candidate is selected
- **THEN** the configured host carries the image_generation tool
- **AND** the tool, public response and usage accounting remain gpt-image-2

### Requirement: Image model sources are full routing candidates
Enabled model sources with the requested image model SHALL participate with
eligible subscription candidates in the existing priority/weight policy and
API-key scope. Sources SHALL receive their native image API request with the
original image model. Image edits SHALL preserve file and mask payloads.

#### Scenario: Source-only image key
- **WHEN** a key is assigned only to an enabled source providing gpt-image-2
- **THEN** generation and editing route to that source
- **AND** they do not require an available subscription host

#### Scenario: Failed or cancelled image stream
- **WHEN** an upstream stream fails or the client disconnects
- **THEN** its connection and admission claims are released
- **AND** the API-key reservation is finalized or released at most once

## MODIFIED Requirements

### Requirement: API Key creation

The system SHALL allow the admin to create API keys via `POST /api/api-keys` with a `name` (required), `allowedModels` (optional list), `weeklyTokenLimit` (optional integer), `expiresAt` (optional ISO 8601 datetime), `assignedAccountIds` (optional list), and `usageSections` (optional comma-separated string, defaults to `"upstream_limits,account_pool_usage"`). The system MUST generate a key in the format `sk-clb-{48 hex chars}`, store the `sha256` authentication hash and a recoverable token in the same database transaction, and return the plain key in the creation response. Subsequent token export SHALL be limited to the scoped no-store configuration endpoint described in relay-config-images; general key reads MUST omit the token. The system MUST accept timezone-aware ISO 8601 datetimes for `expiresAt`, normalize them to UTC naive for persistence, and return the expiration as UTC in API responses.

When `assignedAccountIds` is omitted or empty, the created key SHALL remain unscoped and apply to all accounts. When `assignedAccountIds` is provided with one or more valid account IDs, the created key SHALL enable account-assignment scope and persist those assignments.

#### Scenario: Create unscoped key without assigned accounts

- **WHEN** admin submits `POST /api/api-keys` without `assignedAccountIds`
- **THEN** the created key returns `accountAssignmentScopeEnabled = false`
- **AND** `assignedAccountIds = []`

#### Scenario: Create scoped key with assigned accounts

- **WHEN** admin submits `POST /api/api-keys` with `assignedAccountIds` containing valid account IDs
- **THEN** the created key returns `accountAssignmentScopeEnabled = true`
- **AND** `assignedAccountIds` matches the supplied accounts

#### Scenario: Reject unknown assigned account IDs on create

- **WHEN** admin submits `POST /api/api-keys` with an unknown account ID in `assignedAccountIds`
- **THEN** the system returns 400

#### Scenario: Create key and show plain key

- **WHEN** admin submits `POST /api/api-keys` with a valid payload
- **THEN** the response contains a key matching `sk-clb-[0-9a-f]{48}`
- **AND** the full plain key is returned exactly once
- **AND** general key reads omit the plain key; only authorized configuration export may return the saved token

#### Scenario: Create key with timezone-aware expiration

- **WHEN** admin submits `POST /api/api-keys` with `{ "name": "dev-key", "expiresAt": "2025-12-31T00:00:00Z" }`
- **THEN** the system persists the expiration successfully without PostgreSQL datetime binding errors
- **AND** the response returns `expiresAt` representing the same UTC instant

### Requirement: API Key regeneration

The system SHALL allow regenerating an API key via `POST /api/api-keys/{id}/regenerate`. This MUST generate a new key matching `sk-clb-[0-9a-f]{48}` with a new hash and prefix while preserving all other properties (name, models, limits, expiration). The new plain key MUST be returned in the regeneration response and replace the recoverable token in the same transaction as the authentication hash. Authorized configuration export SHALL subsequently reuse the new token, never the old token.

#### Scenario: Regenerate key

- **WHEN** admin calls `POST /api/api-keys/{id}/regenerate`
- **THEN** the system returns the updated key object with a new `key` and `keyPrefix`
- **AND** the new key matches `sk-clb-[0-9a-f]{48}`
- **AND** the old key immediately stops authenticating

### Requirement: Frontend API Key management

The SPA settings page SHALL include an API Key management section with: a toggle for `apiKeyAuthEnabled`, a key list table showing prefix/name/models/limit/usage/expiry/status, a create dialog (name, model selection, assigned-account selection, usage sections multi-select, weekly limit, expiry date), and key actions (edit, delete, regenerate). On key creation, the SPA MUST display the plain key in a copy-able dialog with a warning to protect the token and that configuration export can reuse it, and the copy action MUST remain functional in secure and non-secure contexts.

The create and edit dialogs SHALL expose an `Apply to codex /model` checkbox directly below `Allowed models`. The checkbox SHALL default to unchecked for new keys and SHALL edit the stored API key value for existing keys.

#### Scenario: Create key with optional account scoping

- **WHEN** an admin opens the create API key dialog
- **THEN** the dialog shows the Assigned accounts picker
- **AND** leaving the picker at `All accounts` creates an unscoped key
- **AND** selecting one or more accounts creates a scoped key for only those accounts

#### Scenario: Create key with usage sections multi-select

- **WHEN** an admin opens the create API key dialog
- **THEN** the dialog shows a "Usage sections shown to client" multi-select dropdown below the Assigned accounts picker
- **AND** the dropdown includes "Upstream limits" and "Account pool usage" options
- **AND** by default both options are selected

#### Scenario: Create key and show plain key

- **WHEN** admin creates a key via the UI
- **THEN** a dialog shows the full plain key with a copy button and a warning message

#### Scenario: API key dialog copy fallback

- **WHEN** a user clicks Copy for the created API key inside the dialog
- **THEN** the copy operation succeeds using secure Clipboard API when available
- **AND** falls back to dialog-scoped `execCommand("copy")` when secure Clipboard API is unavailable

#### Scenario: Create key with codex model visibility option
- **WHEN** an admin opens the create API key dialog
- **THEN** the `Apply to codex /model` checkbox appears directly below `Allowed models`
- **AND** it is unchecked by default

#### Scenario: Edit key with stored codex model visibility option
- **WHEN** an admin opens the edit API key dialog for a key with `apply_to_codex_model: true`
- **THEN** the `Apply to codex /model` checkbox is shown as checked

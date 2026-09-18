## ADDED Requirements

### Requirement: Source-managed deployment
The relay SHALL run from custom/main without importing external injection
modules, runtime reassignment of upstream methods, or HTML asset injection.
Custom functionality SHALL use explicit integration points and separately
reviewable commits. Upstream branches and release tags MUST remain unchanged.

#### Scenario: Clean installation
- **WHEN** the application starts without an injection PYTHONPATH
- **THEN** all relay features load through normal application imports
- **AND** the frontend features are included in the production build

### Requirement: Unified virtual accounts
Model sources SHALL retain stable model-source identifiers, the other plan,
100 percent displayed weekly remaining capacity, and no five-hour quota.
Account assignment, compatible request selection and reports SHALL include
these sources while preserving hard response ownership and API-key scope.

#### Scenario: Source-only key
- **WHEN** a key is assigned only to a model-source virtual account
- **THEN** compatible inference stays within its assigned source
- **AND** control-only operations may use the existing real-account fallback

### Requirement: Durable billing evidence
New source request charges SHALL use a shared billing service on every source
settlement path. The service SHALL preserve the selected price version, rates,
input/cache/output dimensions, tier and calculated breakdown in a separate
ledger. Unknown provider cost, cache-write usage and tool fees MUST remain
unknown unless authoritative metadata provides them. Historical stored costs
MUST NOT change when the current catalog changes.

#### Scenario: Long context
- **WHEN** recognized model input exceeds the catalog threshold
- **THEN** the ledger and API-key settlement use the corresponding long-context rates
- **AND** replaying settlement does not double-charge the key

### Requirement: Visitor isolation and configuration
Visitors SHALL retain their existing credentials and assigned key scopes.
Only administrators SHALL manage visitors, accounts and sensitive settings.
Visitors SHALL read only assigned API-key data. Both roles SHALL be able to
generate Codex configuration after explicitly acknowledging key regeneration,
with backup and restore commands for existing configuration.

#### Scenario: Visitor requests an unassigned key
- **WHEN** a visitor requests another visitor's key or report
- **THEN** the server denies or scopes the request independently of UI visibility

### Requirement: Provider compatibility and control logs
Compass namespace replay SHALL preserve source-specific protocol fields.
Native upstream stream ownership and bounded recovery SHALL be retained.
Control requests SHALL be visibly classified without invented model usage.

#### Scenario: Search control request
- **WHEN** Codex invokes alpha/search
- **THEN** its request log identifies the control operation
- **AND** absent token usage remains absent

### Requirement: Upgrade and rollback discipline
Custom releases SHALL have one Alembic head, a tested frontend build, focused
regression checks and a backup before production migration. Shared custom/main
history SHALL be upgraded by merging the selected upstream release in an
integration branch and fast-forwarding only after validation.

#### Scenario: Failed deployment
- **WHEN** post-deployment health or core regression fails
- **THEN** the prior service configuration and backed-up database can be restored
- **AND** the prior source and injection package remain available

## MODIFIED Requirements

### Requirement: Visitor isolation and configuration
Visitors SHALL retain their existing credentials and assigned key scopes.
Only administrators SHALL manage visitors, accounts and sensitive settings.
Visitors SHALL read only assigned API-key data. Both roles SHALL be able to
generate Codex configuration by reusing a saved token or explicitly acknowledging
an optional (or missing-token-required) regeneration, with backup and restore
commands for existing configuration. The relay-config-images specification
defines token persistence and export isolation.

#### Scenario: Visitor requests an unassigned key
- **WHEN** a visitor requests another visitor's key or report
- **THEN** the server denies or scopes the request independently of UI visibility

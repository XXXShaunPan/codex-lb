## ADDED Requirements

### Requirement: Production checkout is independent of disposable maintenance directories

The production service SHALL resolve its application package, editable-install metadata, and executable launcher to the production checkout, not to a disposable maintenance checkout. The production Git repository SHALL contain its own usable metadata and objects without a worktree pointer or object alternates that require the maintenance checkout. Verified changes SHALL be preserved on the fork's `custom/main` before a maintenance checkout is declared safe to remove.

Consolidation MUST preserve runtime configuration, the virtual environment, built assets, database files, credentials, and unrelated local changes. A directory-removal assessment MUST distinguish the disposable checkout from the shared Python runtime, service executable, and data directory. Consolidation alone MUST NOT delete the maintenance checkout or restart the service.

#### Scenario: Maintenance checkout can be retired

- **WHEN** verified code and records are published and the production checkout passes isolated import and Git-connectivity checks
- **THEN** the service and repository remain usable without the disposable checkout
- **AND** service data and shared Python tooling remain outside that deletion scope

#### Scenario: Production has a stale worktree pointer

- **WHEN** its `.git` file refers to a missing previous parent repository
- **THEN** the old pointer is preserved as a local backup before independent Git metadata is installed
- **AND** runtime files and service settings are not overwritten by a checkout or reset

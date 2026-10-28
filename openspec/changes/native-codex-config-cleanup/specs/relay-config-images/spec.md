## ADDED Requirements

### Requirement: Native client configuration commands
Setup and cleanup SHALL run with system shell utilities on macOS/Linux and
PowerShell 5.1 or newer on Windows, without Python, Node, package installation,
downloaded programs or uploading existing configuration. They SHALL back up
before replacement and preserve the original when parsing or writing fails.

#### Scenario: No Python installed
- **WHEN** a user executes a generated command without Python or Node available
- **THEN** setup and cleanup complete using the native operating-system tools

### Requirement: Targeted relay configuration cleanup
The restore action SHALL remove only positively identified Codex-LB endpoint,
token, actor-header and transport overrides, and selectors referencing affected
providers. It MUST NOT overwrite config.toml from an old backup or alter other
providers, model choices, MCP settings, projects, auth.json or server-side keys.
Generic feature flags SHALL be retained unless ownership metadata records that
setup introduced or changed them. Repeated cleanup SHALL be a no-op.

#### Scenario: Settings added after setup
- **WHEN** the user adds unrelated configuration and then removes Codex-LB
- **THEN** those settings survive and only the relay configuration is removed

#### Scenario: Unrelated provider endpoint
- **WHEN** another provider also contains base_url and a bearer token
- **THEN** cleanup preserves those values unless that provider is identified as Codex-LB

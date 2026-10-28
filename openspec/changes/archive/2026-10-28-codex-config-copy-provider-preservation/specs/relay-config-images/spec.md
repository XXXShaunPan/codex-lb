## MODIFIED Requirements

### Requirement: Native client configuration commands
Setup and restore SHALL run with /bin/bash and system awk on macOS/Linux and
PowerShell 5.1 or newer on Windows, without Python, Node, package installation,
downloaded programs or uploading existing configuration. Bash commands SHALL
explicitly invoke /bin/bash with a quoted script body, independent of the caller's
shell. Both operations SHALL back up before replacement and preserve the original
when parsing or writing fails.

#### Scenario: Invoked from zsh
- **WHEN** a user pastes a generated Bash command into zsh
- **THEN** /bin/bash executes the body without caller-shell expansion

### Requirement: Targeted relay configuration cleanup
Restore SHALL remove only base_url, model_catalog_url and experimental_bearer_token
from positively identified Codex-LB providers. It MUST retain provider table IDs,
names, root/profile model_provider selectors, headers, auth/transport settings,
feature flags and all other configuration. It MUST NOT restore an old backup or
alter chat-history files, auth.json or server-side keys. Repeated restore SHALL
make no further changes or backups.

#### Scenario: Provider references used by historical chats
- **WHEN** restore clears a relay provider's endpoint and token overrides
- **THEN** the same provider ID, name and selectors remain configured
- **AND** all fields other than the three permitted removals remain unchanged

#### Scenario: Unrelated provider endpoint
- **WHEN** another provider also contains base_url and a bearer token
- **THEN** restore preserves it unless it is positively identified as Codex-LB

## ADDED Requirements

### Requirement: One-click command copying
The command copy button SHALL copy the complete selected-platform command in
secure and insecure HTTP contexts using available browser mechanisms. Its
fallback SHALL execute within the user's click gesture and the dialog focus
scope. Success SHALL only be shown after a successful copy; browser-wide denial
SHALL remain an explicit failure, without bypassing browser policy.

#### Scenario: HTTP page without Clipboard API
- **WHEN** an administrator or visitor clicks Copy command on an insecure page
- **THEN** the dialog-safe fallback copies the entire command in one click

#### Scenario: Platform changed after copying
- **WHEN** the user selects another platform
- **THEN** copied feedback resets and the next click copies the new command

## ADDED Requirements

### Requirement: Rejected include options have bounded private incident diagnostics

Separate from generic validation diagnostics, the system MUST emit at most one `request_include_diagnostic` warning for the first unsupported `include` option in an active request. It MUST preserve the include allowlist and all existing validation outcomes and external error contracts. Successful include validation and validation outside an active request MUST NOT emit this additional diagnostic.

The warning MUST identify the request using the existing private correlation policy and MUST expose an option only when its original length is at most 128 characters, its trimmed value is a bounded ASCII protocol identifier or wildcard, and its root identifies a response-item family. Credentials, sensitive markers, free text, unknown families, malformed identifiers, and oversized values MUST be represented only by `[redacted]`. It MUST indicate surrounding-whitespace normalization without changing the original validation input. It MUST NOT include any other request values, headers, conversation content, tool parameters, or exception representations.

#### Scenario: An unsupported protocol option is diagnosed

- **WHEN** a native or v1 Responses request contains multiple unsupported protocol include options
- **THEN** only the first rejected option is diagnosed with its request identifier
- **AND** the existing HTTP 400 response remains unchanged and no upstream request is dispatched

#### Scenario: Include contains sensitive or malformed content

- **WHEN** the rejected include value contains a credential, free text, a newline, an unknown root, or excessive length
- **THEN** its content is replaced with `[redacted]` in the additional warning
- **AND** conversation text and tool parameters are not logged

#### Scenario: Whitespace causes rejection of an otherwise recognizable name

- **WHEN** surrounding spaces cause an option to fail the unchanged allowlist
- **THEN** the diagnostic can show the trimmed protocol name and a true whitespace indicator
- **AND** the original request remains rejected

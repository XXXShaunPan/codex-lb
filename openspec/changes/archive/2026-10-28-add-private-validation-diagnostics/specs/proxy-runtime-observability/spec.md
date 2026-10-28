## ADDED Requirements

### Requirement: Local proxy validation failures have private diagnostic metadata

When local proxy Pydantic, framework request, or explicit client-payload validation rejects an OpenAI-compatible request, the system MUST emit one warning diagnostic for the first validation failure. The diagnostic MUST identify the local validation stage, error source, bounded structural field path, validation error type, and request correlation identifier. It MUST preserve the existing validation outcome, external error envelope and status, routing, and billing behavior.

The diagnostic MUST NOT include request values, headers, credentials, conversation content, validator messages/context, or exception representations. Field paths MUST retain only allowlisted structural names and bounded numeric indices, replacing unknown components with `[redacted]`, and MUST contain at most twelve components. Error types MUST be restricted to known validator types or a fixed fallback. UUID request IDs MUST remain correlatable; other request IDs MUST be hashed before inclusion. Framework OpenAI validation summary logs MUST use the generic public error message instead of raw validator messages.

#### Scenario: Native and compatible Responses reject a malformed tool field

- **WHEN** a request to a native or compatible Responses route fails local tool-field validation
- **THEN** the existing HTTP 400 envelope and parameter are unchanged
- **AND** the diagnostic identifies the failing structural field and error type with the request correlation identifier
- **AND** no upstream request is dispatched

#### Scenario: A validator embeds sensitive values in its error

- **WHEN** a validation exception contains secret input, context, dynamic dictionary keys, or a message derived from user input
- **THEN** the diagnostic includes only the permitted structural metadata
- **AND** neither the diagnostic nor the framework OpenAI validation summary logs those sensitive values

#### Scenario: Validation failures have excessive paths or nonstandard IDs

- **WHEN** a failure has more than twelve path components, unknown type text, or a non-UUID request ID
- **THEN** the log contains a bounded, sanitized field path and fixed type fallback
- **AND** the non-UUID request ID is represented by a deterministic hash

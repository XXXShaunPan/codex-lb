## ADDED Requirements

### Requirement: Responses requests preserve the observed encrypted-output include

The shared native and v1 Responses request schema MUST accept `output.encrypted_content` as an include option. HTTP, WebSocket, and model-source forwarding MUST preserve its spelling and relative order. The proxy MUST NOT replace it with `reasoning.encrypted_content`, remove it, or inject a reasoning include that the client did not send. Existing include options, unknown-value/type rejection, provider capability policy, routing, and billing MUST remain unchanged.

#### Scenario: A desktop request asks for encrypted output

- **WHEN** a native or v1 Responses request includes `output.encrypted_content` alone
- **THEN** local include validation succeeds and serialization preserves that exact option
- **AND** no `reasoning.encrypted_content` option is added

#### Scenario: Mixed encryption includes pass through all routes

- **WHEN** an account HTTP route, equivalent trailing-slash route, WebSocket create, or model-source route receives both encrypted-output and encrypted-reasoning includes
- **THEN** forwarding preserves both entries independently and in their original order

#### Scenario: An unsupported option remains invalid

- **WHEN** a request mixes `output.encrypted_content` with an unknown include value or a non-string entry
- **THEN** the existing invalid-payload error contract is preserved before upstream dispatch

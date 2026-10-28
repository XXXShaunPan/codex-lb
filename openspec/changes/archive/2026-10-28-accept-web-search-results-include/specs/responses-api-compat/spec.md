## ADDED Requirements

### Requirement: Responses requests accept documented web-search result includes

The shared native and OpenAI-compatible Responses request schema MUST accept `web_search_call.results` in `include`, both alone and alongside existing supported values. HTTP and WebSocket request normalization MUST preserve accepted include entries and their order. This requirement MUST NOT bypass existing provider-specific hosted-tool capability filtering, alter account selection or billing, or permit unknown include values or invalid field types.

#### Scenario: A web-search request asks for result details

- **WHEN** a native or v1 Responses HTTP request, including its equivalent trailing-slash path, contains a web-search tool and `include` with `web_search_call.results`
- **THEN** local include validation succeeds
- **AND** the subscription upstream receives the accepted include list unchanged

#### Scenario: A WebSocket create frame mixes supported include values

- **WHEN** a Responses WebSocket create frame contains `web_search_call.results` and `reasoning.encrypted_content`
- **THEN** normalization forwards both entries in their original order

#### Scenario: A request also contains an unknown include value

- **WHEN** an include list mixes `web_search_call.results` with an unsupported value
- **THEN** the existing invalid-payload error contract is preserved
- **AND** no upstream connection or request is made

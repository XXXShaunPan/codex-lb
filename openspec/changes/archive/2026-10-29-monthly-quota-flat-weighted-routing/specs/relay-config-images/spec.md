## MODIFIED Requirements

### Requirement: Image model sources are full routing candidates
Enabled model sources with the requested image model SHALL participate with
eligible subscription candidates in the selected shared routing policy and
API-key scope. Sources SHALL receive their native image API request with the
original image model. Image edits SHALL preserve file and mask payloads.

#### Scenario: Source-only image key
- **WHEN** a key is assigned only to an enabled source providing gpt-image-2
- **THEN** generation and editing route to that source
- **AND** they do not require an available subscription host

#### Scenario: Failed or cancelled image stream
- **WHEN** an upstream stream fails or the client disconnects
- **THEN** its connection and admission claims are released
- **AND** the API-key reservation is finalized or released at most once

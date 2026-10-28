## Why

Codex Desktop immediately receives `Invalid request payload` for some tool-related requests. Existing console errors omit the failing field and validator type, so they cannot distinguish local validation from a fast upstream rejection. Capturing whole payloads would expose credentials and conversation content.

## What Changes

- Add one bounded, metadata-only diagnostic when local proxy validation rejects a request: request correlation ID, validation stage, safe field path, and error type.
- Cover Pydantic conversion, framework request validation, and explicit client-payload validation errors, including shared HTTP/WebSocket error conversion.
- Never log input values, validator messages/context, exception representations, tool definitions, or headers. Redact unknown path components and hash non-UUID request IDs.
- Keep validation, response envelopes/status codes, routing, keys, billing, and database schema unchanged.

## Impact

- Spec: `proxy-runtime-observability`.
- Code: one reusable diagnostic module and small hooks in request-policy conversion and the framework exception handler.
- Verification: privacy/bounding unit tests and actual Responses route regression tests with no upstream network calls.
- Activation requires a service restart; do not restart the shared deployment without the user's timing choice.

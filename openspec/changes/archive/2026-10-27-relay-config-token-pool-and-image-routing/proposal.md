# Reusable Codex credentials and unified image routing

## Why

Configuration generation currently always rotates the API key and writes a
separate client key file. Image generation/edits use a fixed Responses host
and skip the native relay's model-source selection and priority policies.

## What Changes

- Persist newly created and regenerated API tokens transactionally in a
  dedicated table in the main SQLite database. Existing rows start without a
  recoverable token; no production key is rotated by the migration.
- Permit scoped configuration export without rotation. Require explicit reset
  confirmation when a token is missing or the user selects rotation.
- Generate backed-up, idempotent config updates using the existing active
  custom provider or openai_https, inline bearer token, origin-derived URLs,
  model catalog discovery and the requested actor header.
- Separate the public image model from the configurable subscription Responses
  host. Select source and subscription candidates through current relay policy.
- Forward source image generations/edits using their native image endpoints,
  preserve public models in usage/logs, and finalize reservations once.

## Impact

This extends the existing maintained fork and preserves priority grouping,
hysteresis, visitor isolation and immutable billing. New migrations extend the
current single head. User-provided example credentials are never embedded in
source, tests, docs or deployment commands.

# Reliable copy and provider-preserving restore

## Why
The command button uses only the secure Clipboard API, so copying fails on
remote HTTP pages. Restore also removes provider identity/selection, conflicting
with the user's requirement to retain history associated with that provider.

## What Changes
- Reuse the shared focus-aware copy control and harden synchronous Clipboard API
  failure handling; verify real browser clipboard behavior on an insecure origin.
- Restore removes only base_url, model_catalog_url and experimental_bearer_token
  from identified relay providers. Preserve all provider identities/selectors,
  headers, auth/transport settings and feature flags.
- Explicitly run both POSIX commands through /bin/bash, including from zsh.

## Impact
Frontend-only follow-up on integration/native-config-cleanup; no database,
account, key, chat-history or backend migration.

# Native configuration commands and targeted relay removal

## Why
The current generated commands require Python 3.11 and restore an entire old
configuration, which can discard unrelated settings added after setup.

## What Changes
- Use POSIX shell/awk on macOS and Linux and built-in PowerShell on Windows;
  no client Python, Node, downloaded executables or uploaded configuration.
- Replace restore-from-backup with targeted removal of positively identified
  relay endpoints/authentication and provider selectors, preserving other settings.
- Keep local backups, idempotence, inline tokens and existing server-side Key
  lifecycle unchanged. Change UI descriptions and execute both native commands
  against configuration fixtures on supported operating systems.

## Impact
Frontend-only behavior change; no database, billing, routing or Key resets.

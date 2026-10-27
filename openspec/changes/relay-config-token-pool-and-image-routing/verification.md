# Verification — 2026-10-27

## Requirement coverage

- Token lifecycle: `test_codex_token_pool.py` covers native creation and
  regeneration, reuse, hash matching, deletion, inactive/expired keys,
  visitor scope and transaction rollback on persistence failure.
- Commands: `test_codex_config_updater.py` covers TOML preservation, quoted
  provider names, dotted keys, comments, multiline strings, backups and
  idempotence; `commands.test.ts` executes the generated native-shell command
  (PowerShell on Windows, Bash on Linux CI), including Unicode paths.
- Image routing: `test_proxy_images.py` covers subscription host/tool identity,
  image usage logging, quotas and mixed priority pools/zero source weight.
  `test_relay_image_routing.py` covers source-only generation, multipart editing
  and mask, alias paths, missing usage, failures, truncated streams and
  disconnects before/after body start with single settlement/claim cleanup.
- UI: role controls and independent image settings have component tests.
  `screenshots/relay-config.spec.ts` verifies administrator and visitor modal
  behavior in Edge with synthetic fixtures and records screenshots.

## Local checks

- Existing relay/billing/priority/dispatch/load-balancer suite: 697 passed.
- Configuration/images/key lifecycle suite: 211 passed, plus 3 malformed-image
  regressions; the focused image suite passed all 13 scenarios after hardening.
- Additional public API-key/request-log regression: 142 passed (cloud gate;
  the legacy source-assignment assertion now checks unified account scope).
- Frontend focused suite: 61 passed; existing APIs page flow: 7 passed with a
  60-second local test budget; TypeScript/Vite production build passed.
- Browser scenarios: 2 passed. No live credentials are used in screenshots.
- Feature Ruff and ty checks: passed; source-injection guard: passed.
- OpenSpec strict validation: 68 specifications passed.
- Empty-database migration/downgrade/re-upgrade: passed.
- Production-copy migration: upgraded twice, no schema drift, quick_check=ok,
  one head `20261027_010000_add_image_routing_settings`, 3 historical keys
  preserved, recoverable-token pool empty. Copy under production backups:
  `verify-config-images-snapshot-20261027T190617`.

## Release gates

Cloud CI passed at `7cb765d7`:
https://github.com/XXXShaunPan/codex-lb/actions/runs/40494830075
The final malformed-image guard is being rerun through that same gate; the
backed-up service cutover remains pending at this checkpoint.
The incomplete first staging-copy attempt was stopped without affecting the
running production service; the successful copy pins a read snapshot.

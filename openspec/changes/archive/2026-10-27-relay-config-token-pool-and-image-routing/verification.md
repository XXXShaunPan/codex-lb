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
- Configuration/images/key lifecycle suite: 214 passed, including all 13 source
  image scenarios after malformed-image hardening.
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

Final release CI passed at `90c766bc` (1053 backend tests, 61 focused frontend
tests, Linux execution of the generated Bash command, build and spec checks):
https://github.com/XXXShaunPan/codex-lb/actions/runs/40495356469

Released as `custom-v1.25.0-beta.7.4`. Production `/health` and `/health/ready`
returned HTTP 200 with that version; served HTML matches the built frontend.
The three original API-key hashes/prefixes were unchanged and the initial token
pool was empty. Post-deployment probes used temporary credentials only.

Live Compass generation: public model `gpt-image-2`, source route, 20 input /
196 output tokens, USD 0.00598, matching immutable provider-billing entry.
Live subscription generation: public model `gpt-image-2`, independently selected
host `gpt-6.1-terra`, 20 input / 386 output tokens, USD 0.01168. This confirms
there is no fixed `gpt-5.5` dependency or host-text usage mislabeled as image usage.
Both probes verified visitor token reuse/no-store, unassigned-key denial and
logout; temporary keys/visitors were removed and original credentials rechecked.

The initial cutover was interrupted during backup after stopping the service.
No migration had started. The resume used a stopped-writer DB/WAL copy, preserving
the pre-migration database at `pre-config-images-resume-20261027T193245` under
production backups, with encryption key and service XML. A Windows PowerShell
5 inline-Python quoting error affected verification only; verification/migration
were resumed using a script file/PowerShell 7. Source integrity was `ok`, copied
key-table integrity and credential equality passed, migration policy/schema
checks passed, and service was restored at 19:35 local time. Incomplete earlier
copies are retained but MUST NOT be used for rollback.

## Final assessment

All eight tasks and all five requirements are covered. No outstanding code,
schema, deployment or scenario gaps remain. Provider invoice modality-level
reconciliation remains the explicitly documented pre-existing tariff limitation.

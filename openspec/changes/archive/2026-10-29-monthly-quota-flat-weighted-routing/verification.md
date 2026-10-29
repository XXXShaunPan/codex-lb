# Local implementation verification — 2026-10-29

## Summary

| Dimension | Result |
| --- | --- |
| Completeness | Six tasks implemented; eight changed requirements covered |
| Correctness | Native/mixed-source routing, monthly API projection, real browser UI and boundary regressions passed |
| Coherence | Existing quota ingestion/rows retained; standard quota UI reused; priority data left intact but inert |

## Evidence

- 740 backend tests passed across custom/legacy routing, spend controls,
  account weights, load-balancer integration/concurrency, image routing and
  source dispatch. A subsequent 150-test group passed quota refresh, the new
  mixed ent26/Compass path and existing weight/rule/spend-control migrations.
  These groups overlap; they are not a unique combined test count.
- 132 frontend tests passed across monthly list/card/table/detail display,
  routing settings, monthly reset sorting and API-key account selection.
  Existing normal account displays remain covered.
- A seeded 10,000-draw regression demonstrates the expected 40%/40%/20%
  probability distribution for two equal scores and one half-size score across
  Plus, ent26 and Compass. Lower-scoring accounts are not excluded.
- Legacy priority, low-band admission and stored hysteresis do not affect new
  native or mixed-source assignments; persisted bands remain unchanged.
  Known tightest quota, unknown/invalid/zero values, hard exhaustion, scope,
  pause/backoff/concurrency and existing ownership are covered.
- Browser verification passed against an isolated production build on port
  4177 with mocked API data. Chinese account list/details show monthly 58%
  and normal reset styling; no spending amounts or synthetic 5h/weekly bars.
  Settings show the probability explanation and Compass placeholder without
  a priority editor or priority API request. Before/after screenshots are under
  frontend/test-results/spend-control-enterprise-m-c9709-t-weighted-routing-controls/.
- Focused Ruff, ty and ESLint checks passed; TypeScript and Vite production
  build passed to `.local/monthly-quota-build`, not the served static directory.
- Strict OpenSpec validation passed for this change and all 69 main specs.

## Requirement mapping

- Monthly enterprise presentation: accounts/mappers.py projects percentage and
  reset; the shared hasMonthlyQuota helper and normal account quota rows render
  it. API, component, table/sorting/picker and browser tests cover this path.
- Budget-aware measurement and flat random selection: relay_routing/selection.py
  reads raw normalized quota, including budget-only and source-placeholder cases.
  Unit distribution tests and native/mixed-source integration tests cover it.
- Ranking independence and inert legacy configuration: request paths no longer
  call priority runtime; priority UI is removed, legacy admin APIs are deprecated.
- Eligibility/continuity and image-source participation: existing hard filters
  and ownership code remain in force; load-balancer/image/source suites pass.

## Operational boundary

The subsequent publication gate identified one image mixed-pool integration
test that still asserted the retired priority-group ordering. It now controls
only the random outcome while asserting that both candidates participate with
scores (0.6, 1.0), then (0.1, 1.0), and that zero source weight excludes it.
This preserves end-to-end image routing coverage under the new contract.

At the original local-verification stage, the source was based on 0d7bfa76. No branch, commit, push, live
configuration update, migration, service restart, credential reset or frontend
publication was performed. Normal production background activity was not paused.
Service PID remained 5552, and the served entry file SHA256 remained
51FB8155888FB2FBF444B83A30FC6303F2DBC411378D57244A4744E58C22FD3C.
The new source and frontend build required a separately authorized activation,
which was subsequently completed; see [deployment verification](deployment.md).

No outstanding correctness or design-divergence findings. Code, main specs and
operator documentation are synchronized, and the verified local change is archived.
The archive CLI emitted a non-blocking suggestion to split proposals with more
than ten deltas (including requirement renames); these deltas belong to this one
quota-display/routing revision. Deployment was handled by the subsequent explicit
publication/activation request rather than the original local implementation task.

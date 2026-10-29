# Verification

## Local checks

- 78 focused backend tests passed: exact quadratic scores, raw quota minima,
  operator weights remaining linear, seeded distributions, continuity, inert
  priorities, native/mixed ent26/Source paths and the real image request path.
- A seeded 10,000-draw check verifies 80%/20% equal-weight quota produces a
  16:1 score ratio with a nonzero low-quota selection share near 1/17.
- 66 frontend tests passed, including existing displays plus USD formatting,
  missing/invalid/non-USD amounts, zero/negative balances, separate units when
  sorting, preserved monthly percentage/reset and quadratic explanation text.
- Ruff, ty, focused ESLint, TypeScript and isolated Vite production build passed.
- Headless Edge browser verification passed for monthly rows, the existing
  subscription field's `$116.67`, and the quadratic/placeholder explanations.
  Before/after screenshots use fake account/API responses, never live credentials.
- Strict OpenSpec validation passed for this change and all 69 main specs.

The runtime change is limited to squaring the measured quota fraction. No extra
threshold, priority group, subscription-credit conversion, schema migration or
live weight edit is introduced. Publication and activation remain pending until
matching-head cloud checks and backup verification complete.

The first cloud run passed the full native relay gate, Windows and Ubuntu jobs.
Its macOS ARM job never received a runner and was cancelled by hosted capacity
exhaustion, not by a test failure
([run](https://github.com/XXXShaunPan/codex-lb/actions/runs/40901101383)).
The retry uses the standard `macos-15-intel` label documented by
[GitHub](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job).
macOS, system Bash and zsh tests remain enabled; no test or release check is skipped.

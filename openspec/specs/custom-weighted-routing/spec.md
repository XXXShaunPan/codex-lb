# Custom Weighted Routing Specification

## Purpose
Define administrator-managed priority groups with quota-weighted new allocation.

## Requirements

### Requirement: Explicit account weights
Administrators SHALL read and update a finite numeric routing weight for every
visible subscription account and Model Source. Default weight SHALL be 1;
valid values SHALL be from 0 through 1,000,000 inclusive. Negative, non-finite,
boolean and nonnumeric values MUST be rejected. Visitors MUST NOT read or
change these controls. Deleted accounts MUST return not-found.

#### Scenario: Save a virtual account weight
- **WHEN** an administrator sets the weight of model-source:source-id to 2.5
- **THEN** the source retains 2.5 after a restart
- **AND** the same setting is visible in its account detail and routing settings

### Requirement: Highest eligible priority group first
For `custom_weighted_quota`, new allocations SHALL use only eligible accounts
with the smallest numeric priority. Within that group probability SHALL be
proportional to configured weight multiplied by known remaining quota.

#### Scenario: Equivalent effective weights
- **GIVEN** A has weight 2 and 50% remaining and B has weight 1 and 100% remaining
- **WHEN** a new eligible request is assigned
- **THEN** A and B have equal draw probability when in the same priority group

#### Scenario: Non-Plus aggregate weight cannot crowd out Plus
- **GIVEN** an eligible normal Plus has priority 10 and others have priority 20
- **WHEN** a new request is assigned
- **THEN** only the Plus participates regardless of the others' aggregate weight

#### Scenario: Exhausted or zero-weight pool
- **WHEN** all otherwise eligible candidates have weight zero or no remaining quota
- **THEN** no new account is selected
- **AND** selection MUST NOT fall back to the first source or uniform routing

### Requirement: Reported quota measurement
Remaining fractions SHALL be clamped to [0,1] using reported usage before
synthetic pressure. The minimum known applicable fraction SHALL weight the
draw. Missing requested windows SHALL put ordinary accounts in their low
band; no known quota SHALL exclude new allocation. Confirmed absent windows
SHALL be ignored in minimum-applicable mode. Sources SHALL retain labeled
100% routing placeholders, which MUST NOT be represented as provider balance.

#### Scenario: Inflight pressure does not change a score
- **WHEN** a candidate reports 50% remaining but its synthetic pressure is 100%
- **THEN** its score uses 50% remaining, subject to hard concurrency limits

### Requirement: Ranking independence
Within a priority group, plan capacity, reset-time preference, burn/preserve, soft
health tiers, error/latency weight multipliers, planner costs and last-selected
time MUST NOT alter the weighted draw.

#### Scenario: A preserve account competes with a burn-first account
- **GIVEN** both accounts are eligible in the same group with equal effective weights
- **THEN** both have equal probability regardless of their routing-policy labels

### Requirement: Eligibility and continuity remain enforced
Authentication, assignment scope, model capability, pause/deactivation,
cooldown/backoff, quota exhaustion and concurrency caps MUST remain enforced.
Existing hard continuity and session ownership MUST remain authoritative;
weights, priorities and low-quota admission rules govern only new assignments.

#### Scenario: An established owner has weight zero
- **WHEN** an existing session validates its owner whose weight is now zero
- **THEN** that weight alone does not move the existing session to another account
- **AND** new allocations exclude the zero-weight account

### Requirement: Administrator rules and persistent hysteresis
Administrators SHALL configure normal/low priority, downgrade/recovery
thresholds, quota basis and low-band admission at plan and account levels.
Account overrides SHALL replace plan defaults and SHALL be removable to
restore inheritance. Defaults SHALL be Plus 10/30, others 20/20, thresholds
20/25, minimum applicable windows and low-band admission enabled. Recovery
MUST exceed downgrade. Changes SHALL apply to subsequent new allocations.
Quota bands SHALL persist across restart and stale observations MUST NOT
reverse newer transitions. Visitors MUST NOT read or mutate these rules.

#### Scenario: Recovery avoids oscillation
- **GIVEN** a Plus has remaining quota 19%, then 22%, then 25%
- **WHEN** new allocations are evaluated across process restarts
- **THEN** it stays low at 22% and returns to normal at 25%

#### Scenario: Low Plus fallback is disabled
- **GIVEN** a low Plus has low-band admission disabled
- **WHEN** all other groups are unavailable
- **THEN** new allocation fails closed and existing valid ownership is retained

### Requirement: Opt-in and operational isolation
Existing routing strategies SHALL retain their behavior. Selecting the new
strategy SHALL be an explicit dashboard change. Development, tests and builds
for this release MUST leave the running production process, deployed files,
production database and current routing settings unchanged until the operator
executes the documented manual activation procedure.

#### Scenario: Publish without restart
- **WHEN** this feature is pushed to the maintained fork
- **THEN** the current service keeps its original process and deployment version
- **AND** the operator receives explicit backup/migration/restart instructions

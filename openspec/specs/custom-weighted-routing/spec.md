# Custom Weighted Routing Specification

## Purpose
Define administrator-managed account weights and quota-only new allocation.

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

### Requirement: Weight and quota are the only allocation factors
For `custom_weighted_quota`, the probability of each eligible account SHALL be
proportional to its configured weight multiplied by the smallest applicable
remaining quota fraction. Other ranking factors MUST NOT alter the draw.

#### Scenario: Equivalent effective weights
- **GIVEN** A has weight 2 and 50% remaining and B has weight 1 and 100% remaining
- **WHEN** a new eligible request is assigned
- **THEN** A and B have equal draw probability regardless of plan or reset time

#### Scenario: Exhausted or zero-weight pool
- **WHEN** all otherwise eligible candidates have weight zero or no remaining quota
- **THEN** no new account is selected
- **AND** selection MUST NOT fall back to the first source or uniform routing

### Requirement: Reported quota measurement
Remaining fractions SHALL be clamped to [0,1] using reported usage before
synthetic inflight or token-lease penalties. Absent windows SHALL be neutral
(1). Model Sources SHALL retain fixed 100% weekly quota and no five-hour window.

#### Scenario: Inflight pressure does not change a score
- **WHEN** a candidate reports 50% remaining but its synthetic pressure is 100%
- **THEN** its score uses 50% remaining, subject to hard concurrency limits

### Requirement: Ranking independence
Plan capacity, reset-time preference, burn-first/preserve preferences, soft
health tiers, error/latency weight multipliers, planner costs and last-selected
time MUST NOT alter the weighted draw.

#### Scenario: A preserve account competes with a burn-first account
- **GIVEN** both accounts are eligible and have equal effective weights
- **THEN** both have equal probability regardless of their routing-policy labels

### Requirement: Eligibility and continuity remain enforced
Authentication, assignment scope, model capability, pause/deactivation,
cooldown/backoff, quota exhaustion and concurrency caps MUST remain enforced.
Existing hard continuity and session ownership MUST remain authoritative;
weights govern new assignments.

#### Scenario: An established owner has weight zero
- **WHEN** an existing session validates its owner whose weight is now zero
- **THEN** that weight alone does not move the existing session to another account
- **AND** new allocations exclude the zero-weight account

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

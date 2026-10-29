# Custom Weighted Routing Specification

## Purpose
Define a flat, plan-independent pool with quota-weighted random new allocation.

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

### Requirement: Flat quota-weighted random selection
For `custom_weighted_quota`, all eligible accounts SHALL participate in one pool.
Probability SHALL be proportional to custom weight multiplied by the minimum
known applicable remaining fraction. Plan and account priority groups MUST NOT
filter candidates. Normal allocations SHALL use a random draw, not score argmax.
Only non-allocating eligibility probes MAY select deterministically.

#### Scenario: Equivalent effective weights
- **GIVEN** A has weight 2 and 50% remaining and B has weight 1 and 100% remaining
- **WHEN** a new eligible request is assigned
- **THEN** A and B have equal draw probability regardless of their plans or saved priority rules

#### Scenario: Lower score can win
- **WHEN** one account has a smaller positive score than another
- **THEN** it still has nonzero selection probability

#### Scenario: Exhausted or zero-weight pool
- **WHEN** all otherwise eligible candidates have weight zero or no remaining quota
- **THEN** no new account is selected
- **AND** selection MUST NOT fall back to the first source or uniform routing

### Requirement: Reported quota measurement
Remaining fractions SHALL be clamped to [0,1] using reported usage before
synthetic pressure. The minimum known applicable fraction SHALL weight the
draw, including short, weekly or monthly quota as applicable. Missing windows
MUST NOT be invented; all unknown/invalid quota SHALL exclude new allocation.
Confirmed absent windows SHALL be ignored. Sources SHALL retain labeled
100% routing placeholders, which MUST NOT be represented as provider balance.

#### Scenario: Inflight pressure does not change a score
- **WHEN** a candidate reports 50% remaining but its synthetic pressure is 100%
- **THEN** its score uses 50% remaining, subject to hard concurrency limits

#### Scenario: Tightest quota wins the score
- **WHEN** a real account has 80% short-window and 30% long-window quota remaining
- **THEN** its score is custom weight multiplied by 0.3

### Requirement: Ranking independence
Plan capacity, plan/account priority, low-quota bands, reset-time preference,
burn/preserve, soft health tiers, error/latency weight multipliers, planner costs
and last-selected time MUST NOT alter the weighted draw.

#### Scenario: A preserve account competes with a burn-first account
- **GIVEN** both accounts are eligible with equal effective weights
- **THEN** both have equal probability regardless of their routing-policy labels

#### Scenario: Obsolete low-band exclusion
- **WHEN** a positive-quota account has a saved rule disallowing low-band admission
- **THEN** that rule does not prevent participation in the custom strategy

### Requirement: Eligibility and continuity remain enforced
Authentication, assignment scope, model capability, pause/deactivation,
cooldown/backoff, quota exhaustion and concurrency caps MUST remain enforced.
Existing hard continuity and session ownership MUST remain authoritative;
weights and quota-derived scores govern only new assignments.

#### Scenario: An established owner has weight zero
- **WHEN** an existing session validates its owner whose weight is now zero
- **THEN** that weight alone does not move the existing session to another account
- **AND** new allocations exclude the zero-weight account

### Requirement: Inert legacy priority configuration
The custom strategy SHALL NOT read or update legacy priority/hysteresis rules
during assignment. Settings and account details MUST NOT display priority-rule
editors. Existing stored data and authenticated legacy APIs MAY remain for
compatibility, clearly marked deprecated and without routing effect.
Visitors MUST NOT read or mutate those legacy APIs.

#### Scenario: Stored rules survive without affecting routing
- **WHEN** the new implementation runs against an existing rules database
- **THEN** routing ignores those rules without deleting their records

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

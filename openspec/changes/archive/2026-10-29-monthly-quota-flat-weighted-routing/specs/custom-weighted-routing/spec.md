## RENAMED Requirements

- FROM: `### Requirement: Highest eligible priority group first`
- TO: `### Requirement: Flat quota-weighted random selection`
- FROM: `### Requirement: Administrator rules and persistent hysteresis`
- TO: `### Requirement: Inert legacy priority configuration`

## MODIFIED Requirements

### Requirement: Flat quota-weighted random selection
For `custom_weighted_quota`, all eligible accounts SHALL participate in one pool.
Probability SHALL be proportional to custom weight multiplied by the minimum
known applicable remaining fraction. Plan and account priority groups MUST NOT
filter candidates. Normal allocations SHALL use a random draw, not score argmax.
Only non-allocating eligibility probes MAY select deterministically.

#### Scenario: Equivalent effective weights
- **GIVEN** Plus A has weight 2 and 50% remaining and ent26 B has weight 1 and 100% remaining
- **THEN** both have equal draw probability, regardless of saved priority rules

#### Scenario: Lower score can win
- **WHEN** one account has a smaller positive score than another
- **THEN** it still has nonzero selection probability

#### Scenario: Exhausted or zero-weight pool
- **WHEN** no eligible candidate has a positive score
- **THEN** no new allocation is made, without first-source or uniform fallback

### Requirement: Reported quota measurement
Remaining fractions SHALL be clamped to [0,1] using normalized reported usage
before synthetic pressure. The minimum known applicable short/weekly/monthly
fraction SHALL weight the draw. Missing windows SHALL not be invented and all
unknown/invalid quota SHALL exclude new allocation. Source accounts SHALL use
a labeled 100% placeholder, not an assertion of real provider balance.

#### Scenario: Tightest quota wins the score
- **WHEN** a real account has 80% short-window and 30% long-window quota remaining
- **THEN** its score is custom weight multiplied by 0.3

#### Scenario: Inflight pressure does not change a score
- **WHEN** a candidate reports 50% remaining but its synthetic pressure is 100%
- **THEN** its score uses 50% remaining, subject to hard concurrency limits

### Requirement: Ranking independence
Plan capacity, plan/account priority, low-quota bands, reset preference,
burn/preserve, soft health tiers, error/latency multipliers, planner costs and
last-selected time MUST NOT alter the custom weighted draw.

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

#### Scenario: Stored rules survive without affecting routing
- **WHEN** the new implementation runs against an existing rules database
- **THEN** routing ignores those rules without deleting their records

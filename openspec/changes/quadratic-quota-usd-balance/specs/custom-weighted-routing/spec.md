## MODIFIED Requirements

### Requirement: Flat quota-weighted random selection
For `custom_weighted_quota`, all eligible accounts SHALL participate in one pool.
Probability SHALL be proportional to `custom_weight * q^2`, where q is the minimum
known applicable remaining fraction in [0,1]. Only the quota fraction SHALL be
squared, not the configured custom weight. Plan/account priorities MUST NOT
filter candidates. Normal allocations SHALL use a random draw, not score argmax.
Only non-allocating eligibility probes MAY select deterministically.

#### Scenario: Equivalent effective weights
- **GIVEN** A has weight 4 and 50% remaining and B has weight 1 and 100% remaining
- **WHEN** a new eligible request is assigned
- **THEN** A and B have equal draw probability regardless of their plans or saved priority rules

#### Scenario: Lower score can win
- **WHEN** one account has a smaller positive score than another
- **THEN** it still has nonzero selection probability

#### Scenario: Exhausted or zero-weight pool
- **WHEN** all otherwise eligible candidates have weight zero or no remaining quota
- **THEN** no new account is selected
- **AND** selection MUST NOT fall back to the first source or uniform routing

#### Scenario: Greater separation at equal custom weights
- **GIVEN** two otherwise eligible accounts have equal custom weights and 80% / 20% remaining
- **THEN** their scores have a 16:1 ratio and their probabilities are 16/17 and 1/17

### Requirement: Reported quota measurement
Remaining fractions SHALL be clamped to [0,1] using reported usage before
synthetic pressure. The minimum known applicable fraction SHALL be squared for
the score, including short, weekly or monthly quota as applicable. Missing
windows MUST NOT be invented; all unknown/invalid quota SHALL exclude new
allocation. Confirmed absent windows SHALL be ignored. Sources SHALL retain
labeled 100% routing placeholders, not actual provider balance.

#### Scenario: Inflight pressure does not change a score
- **WHEN** a candidate reports 50% remaining but its synthetic pressure is 100%
- **THEN** its score uses 0.5 squared, subject to hard concurrency limits

#### Scenario: Tightest quota wins the score
- **WHEN** a real account has 80% short-window and 30% long-window quota remaining
- **THEN** its score is custom weight multiplied by 0.09

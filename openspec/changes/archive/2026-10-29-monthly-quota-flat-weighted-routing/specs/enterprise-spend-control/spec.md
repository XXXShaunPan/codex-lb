## RENAMED Requirements

- FROM: `### Requirement: Display actual spending budgets`
- TO: `### Requirement: Monthly enterprise quota presentation`

## MODIFIED Requirements

### Requirement: Monthly enterprise quota presentation
Account summaries SHALL expose ent26's upstream remaining percentage and reset
time through the existing monthly usage/reset fields. List, dashboard card and
detail surfaces SHALL render monthly percentage/reset with normal quota styling,
without a separate monetary spending-budget panel. Unknown values MUST remain
unknown. Budget-only accounts MUST NOT show synthetic 5h/weekly quotas or convert
money into subscription credits. No fixed monthly duration SHALL be fabricated.
Raw spendControl API data MAY remain for compatibility.

#### Scenario: Monthly ent26 allowance
- **WHEN** ent26 reports 58% remaining and an upstream reset timestamp
- **THEN** all three account surfaces show monthly 58% and that reset time
- **AND** no spending-budget amount, 5h or weekly row is shown for budget-only accounts

### Requirement: Budget-aware quota-weighted selection
For budget-only accounts, custom weighted routing SHALL use actual budget
remaining percentage. For accounts with multiple applicable quota windows, the
minimum known remaining percentage SHALL determine the score. Plan/account
priorities, low-band admission and hysteresis MUST NOT affect this strategy.
Missing budget values MUST NOT be treated as full capacity.

#### Scenario: Budget-only account enters weighted pool
- **WHEN** a budget-only account has positive budget, positive custom weight and passes hard availability constraints
- **THEN** it participates without a fabricated 5h or weekly quota

#### Scenario: Different monetary allowance sizes
- **WHEN** two budget-only accounts have equal remaining percentages and custom weights
- **THEN** they have equal probability regardless of their monetary allowance sizes

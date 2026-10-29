# Enterprise spending-control quotas

## Purpose
Support upstream monetary budget controls without inventing subscription quota
windows or conflating dollars with credits. Preserve local seat ownership and
provide accurate account-facing information and exhaustion admission checks.

## Requirements

### Requirement: Persist upstream spending controls independently
The system SHALL parse and persist spend_control independently of rate_limit for
any plan. Snapshots SHALL be isolated by local account ID, preserve decimal
amounts, and survive process restarts. Failed or omitted observations MUST NOT
erase known budgets. Explicit null SHALL clear a previously returned control.
Older observations MUST NOT replace newer snapshots.

#### Scenario: Enterprise budget without subscription windows
- **WHEN** usage returns rate_limit=null and an individual USD spend control
- **THEN** the budget and observation time are stored without synthetic usage windows
- **AND** successful polling freshness is retained across sessions

#### Scenario: Shared workspace with separate users
- **WHEN** two local accounts share a workspace and have different spending limits
- **THEN** each account retains only its own returned budget

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
- **AND** no separate spending-budget panel, 5h or weekly row is shown for budget-only accounts

### Requirement: Enterprise USD subscription allowance display
The existing subscription-quota card and table fields SHALL show ent26's actual
spend-control remaining USD amount with a dollar symbol and two decimal places.
Missing, blank, non-finite or non-USD amounts SHALL remain unknown rather than
being shown as zero or inferred from percentages. Valid zero/negative balances
SHALL retain their numeric meaning. Monthly percentage/reset display SHALL remain.
USD amounts MUST NOT enter numeric subscription-credit aggregates or routing
scores; table comparisons SHALL keep different units separate.

#### Scenario: Current remaining balance
- **WHEN** ent26 reports USD 116.6687 remaining
- **THEN** subscription quota shows $116.67 on both the card and table
- **AND** the monthly quota row remains unchanged

#### Scenario: Unknown allowance is not a zero balance
- **WHEN** the remaining amount or its USD unit is missing or invalid
- **THEN** the subscription quota field displays an unknown value

#### Scenario: Normal subscription accounts retain credits
- **WHEN** a non-ent26 account has ordinary subscription credits
- **THEN** its existing numeric credit display and aggregation remain unchanged

### Requirement: Respect exhausted spending controls
Account selection SHALL exclude an account with an explicit reached control or
nonpositive remaining allowance, including when standard quotas are bypassed.
Recovery SHALL require a successful newer observation, not an assumed local reset.
This filter MUST NOT alter account authentication, operator status or permissions.

#### Scenario: Exhaustion and recovery
- **WHEN** a previously available budget becomes exhausted
- **THEN** it is excluded from selection even if has_credits=true
- **AND** a later successful observation with available budget makes it eligible again

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

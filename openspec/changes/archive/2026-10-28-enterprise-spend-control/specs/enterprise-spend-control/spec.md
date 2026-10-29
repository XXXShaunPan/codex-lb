## ADDED Requirements

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

### Requirement: Display actual spending budgets
Account APIs and list, card and detail surfaces SHALL expose the upstream unit,
limit, used, remaining, remaining percentage, reset time and observation time.
Unknown values MUST remain unknown. Budget-only accounts MUST NOT show synthetic
5h or weekly windows or turn dollar balances into subscription credits.

#### Scenario: Different configured allowances
- **WHEN** one account has a USD 200 limit and another has a USD 50 limit
- **THEN** the views show each actual allowance and remaining amount
- **AND** reset/observation timestamps use the normal dashboard datetime contract

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
For budget-only accounts, quota-weighted routing SHALL use the actual budget
remaining percentage independently of subscription-window basis settings.
Existing priority, weight and low-quota hysteresis rules SHALL remain in effect.
Missing budget values MUST NOT be treated as full capacity.

#### Scenario: Budget-only account enters weighted pool
- **WHEN** a budget-only account has positive budget and satisfies configured admission rules
- **THEN** it participates without a fabricated 5h or weekly quota

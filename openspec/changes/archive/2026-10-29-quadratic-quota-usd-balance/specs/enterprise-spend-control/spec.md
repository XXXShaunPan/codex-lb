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
- **AND** no separate spending-budget panel, 5h or weekly row is shown for budget-only accounts

## ADDED Requirements

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

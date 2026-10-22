## ADDED Requirements

### Requirement: Highest eligible priority group first
New custom-strategy allocations SHALL use only the nonempty eligible group
with the smallest numeric priority. Within that group the draw SHALL be
proportional to weight times reported remaining quota.

#### Scenario: Many non-Plus accounts cannot crowd out a healthy Plus
- **GIVEN** one eligible Plus has priority 10 and any number of others have 20
- **WHEN** a new request is allocated
- **THEN** only the Plus participates regardless of the other total weight

### Requirement: Administrator rules and persistent hysteresis
Administrators SHALL edit plan defaults and optional full account overrides
for normal/low priority, downgrade/recovery percentages, quota basis and low
quota admission. Defaults SHALL be Plus 10/30, others 20/20, thresholds 20/25,
minimum applicable windows and low-quota admission enabled. Lower priority
numbers SHALL win; recovery MUST exceed downgrade. Weight zero SHALL remain
ineligible for new assignments. Saves SHALL affect subsequent allocations.

#### Scenario: A depleted Plus recovers without flapping
- **GIVEN** a Plus has remaining quota 19%, then 22%, then 25%
- **WHEN** new allocations are evaluated across process restarts
- **THEN** it stays low at 22% and returns to normal at 25%

### Requirement: Conservative unknown quota and explicit placeholders
Ordinary accounts missing a requested quota window SHALL enter their low
band, using only known remaining quota for weighting. Accounts with no known
quota SHALL be excluded from new assignments. Confirmed absent windows SHALL
not count as missing in minimum-applicable mode. Sources SHALL use a labeled
100% routing placeholder independent of real provider balance.

#### Scenario: Missing weekly Plus quota cannot grant normal priority
- **GIVEN** a Plus has only a known 60% short window but weekly basis is selected
- **WHEN** an eligible non-Plus with default rules is available
- **THEN** the non-Plus wins over that unknown-weekly Plus

### Requirement: Continuity independent of admission priorities
Existing session, response and file owners MUST retain ownership despite
priority, weight, unknown quota or low-admission configuration changes.
Authentication, capability, permission and hard availability MUST still apply.

#### Scenario: Fallback is disabled for a bound owner
- **GIVEN** a low Plus already owns a session
- **WHEN** its low-quota admission is disabled
- **THEN** new allocations exclude it but its valid existing session continues

from __future__ import annotations

from app.core.usage.spend_controls import account_spend_control, spend_control_remaining_percent
from app.core.utils.time import from_epoch_seconds
from app.db.models import Account
from app.modules.accounts.schemas import AccountSpendControl


def build_spend_control_summary(account: Account) -> AccountSpendControl | None:
    snapshot = account_spend_control(account)
    row = account.spend_control_snapshot
    if snapshot is None or snapshot.control is None or row is None:
        return None
    control = snapshot.control
    limit = control.individual_limit
    return AccountSpendControl(
        unit=limit.unit if limit is not None else None,
        limit=str(limit.limit) if limit is not None and limit.limit is not None else None,
        used=str(limit.used) if limit is not None and limit.used is not None else None,
        remaining=str(limit.remaining) if limit is not None and limit.remaining is not None else None,
        remaining_percent=spend_control_remaining_percent(control),
        reached=control.reached,
        reset_at=from_epoch_seconds(limit.reset_at) if limit is not None else None,
        observed_at=row.observed_at,
        budget_only=not snapshot.rate_limit_present,
    )

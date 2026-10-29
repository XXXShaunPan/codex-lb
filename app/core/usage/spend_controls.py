from __future__ import annotations

from app.core.usage.models import SpendControlPayload, SpendControlSnapshot
from app.db.models import Account


def account_spend_control(account: Account) -> SpendControlSnapshot | None:
    row = account.spend_control_snapshot
    return SpendControlSnapshot.model_validate_json(row.payload_json) if row is not None else None


def spend_control_exhausted(control: SpendControlPayload | None) -> bool:
    if control is None:
        return False
    if control.reached is True:
        return True
    limit = control.individual_limit
    return limit is not None and limit.remaining is not None and limit.remaining <= 0


def spend_control_remaining_percent(control: SpendControlPayload) -> float | None:
    limit = control.individual_limit
    if limit is None:
        return None
    percent = limit.remaining_percent
    if percent is None and limit.used_percent is not None:
        percent = 100.0 - limit.used_percent
    if percent is None and limit.remaining is not None and limit.limit is not None and limit.limit > 0:
        percent = float(limit.remaining / limit.limit * 100)
    return None if percent is None else max(0.0, min(100.0, percent))

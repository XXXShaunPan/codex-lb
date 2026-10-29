from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.balancer import select_account
from app.core.crypto import TokenEncryptor
from app.core.usage.models import SpendControlPayload, SpendControlSnapshot, UsagePayload
from app.core.usage.spend_controls import spend_control_exhausted, spend_control_remaining_percent
from app.db.models import Account, AccountStatus, ProviderSpendControl, UsageHistory
from app.modules.accounts.mappers import build_account_summaries
from app.modules.proxy._load_balancer.sticky_selection import _clone_account
from app.modules.proxy.load_balancer import RuntimeState, _state_from_account

pytestmark = pytest.mark.unit


def budget(remaining="116.66873848438263", *, reached=False, limit="200.00"):
    return SpendControlPayload.model_validate(
        {
            "reached": reached,
            "individual_limit": {
                "unit": "usd",
                "limit": limit,
                "used": "83.33126151561737",
                "remaining": remaining,
                "reset_at": 1793491200,
            },
        }
    )


def account_with_budget(account_id="seat-a", remaining="116.66873848438263"):
    account = Account(
        id=account_id,
        chatgpt_account_id="shared-workspace",
        email=f"{account_id}@example.test",
        plan_type="ent26",
        status=AccountStatus.ACTIVE,
        access_token_encrypted=b"unused",
        refresh_token_encrypted=b"unused",
        id_token_encrypted=b"unused",
        last_refresh=datetime(2026, 10, 28),
        routing_weight=1.0,
    )
    account.spend_control_snapshot = ProviderSpendControl(
        account_id=account_id,
        observed_at=datetime(2026, 10, 28),
        payload_json=SpendControlSnapshot(control=budget(remaining)).model_dump_json(),
    )
    return account


def test_parses_budget_without_rate_windows_and_preserves_decimal_precision():
    payload = UsagePayload.model_validate(
        {"plan_type": "ent26", "rate_limit": None, "spend_control": budget().model_dump(mode="json")}
    )
    assert payload.rate_limit is None
    assert payload.spend_control.individual_limit.remaining == Decimal("116.66873848438263")
    assert '"116.66873848438263"' in payload.model_dump_json()


def test_unknown_values_stay_unknown_and_reported_percent_wins():
    empty = SpendControlPayload(reached=False)
    assert spend_control_remaining_percent(empty) is None
    assert not spend_control_exhausted(empty)
    reported = budget()
    reported.individual_limit.remaining_percent = 58
    assert spend_control_remaining_percent(reported) == 58
    assert spend_control_remaining_percent(budget()) == pytest.approx(58.33436924219131)


@pytest.mark.parametrize(
    "remaining,reached,exhausted",
    [("0", False, True), ("-0.01", False, True), ("10", True, True), (None, False, False)],
)
def test_exhaustion_is_not_equivalent_to_has_credits(remaining, reached, exhausted):
    assert spend_control_exhausted(budget(remaining, reached=reached)) is exhausted


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_money_is_rejected(value):
    with pytest.raises(ValidationError):
        budget(value)


def test_summary_drops_obsolete_subscription_windows_but_not_history():
    account = account_with_budget()
    old = UsageHistory(
        account_id=account.id, used_percent=0, window="primary", window_minutes=0, recorded_at=datetime(2026, 10, 27)
    )
    summary = build_account_summaries(
        accounts=[account],
        primary_usage={account.id: old},
        secondary_usage={},
        encryptor=TokenEncryptor(),
        include_auth=False,
    )[0]
    assert summary.spend_control.remaining == "116.66873848438263"
    assert summary.spend_control.unit == "usd"
    assert summary.spend_control.budget_only
    assert summary.usage.primary_remaining_percent is None
    assert summary.usage.secondary_remaining_percent is None
    assert summary.window_minutes_primary is None
    assert old.used_percent == 0


@pytest.mark.parametrize("strategy", ["round_robin", "usage_weighted", "custom_weighted_quota"])
def test_real_routing_state_and_clones_respect_budget_even_when_standard_quota_bypassed(strategy):
    blocked = _clone_account(account_with_budget(remaining="0"))
    available = _clone_account(account_with_budget("seat-b", "150"))
    states = [
        _state_from_account(
            account=a,
            primary_entry=None,
            secondary_entry=None,
            runtime=RuntimeState(),
            now=1793181600,
            soft_drain_enabled=False,
        )
        for a in (blocked, available)
    ]
    assert states[0].spend_control_exhausted
    assert states[0].status == AccountStatus.ACTIVE
    assert select_account(states, routing_strategy=strategy, ignore_standard_quota=True).account.account_id == "seat-b"
    result = select_account([states[0]], ignore_standard_quota=True)
    assert result.account is None
    assert result.error_code == "usage_limit_reached"
    assert result.resets_at == 1793491200
    assert blocked.status == AccountStatus.ACTIVE


def test_budget_recovery_requires_new_snapshot_not_elapsed_reset():
    blocked = account_with_budget(remaining="0")
    state = _state_from_account(
        account=blocked,
        primary_entry=None,
        secondary_entry=None,
        runtime=RuntimeState(),
        now=1794000000,
        soft_drain_enabled=False,
    )
    result = select_account([state], now=1794000000)
    assert result.account is None
    assert result.resets_at is None
    blocked.spend_control_snapshot.payload_json = SpendControlSnapshot(control=budget("200")).model_dump_json()
    fresh = _state_from_account(
        account=blocked,
        primary_entry=None,
        secondary_entry=None,
        runtime=RuntimeState(),
        now=1794000000,
        soft_drain_enabled=False,
    )
    assert select_account([fresh]).account is not None

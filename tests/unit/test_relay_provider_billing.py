from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.core.usage.pricing import get_pricing_for_model
from app.modules.model_sources.forwarding import SourceUsage, _usage_from_responses_payload
from app.modules.provider_billing.service import quote_usage, source_usage_cost_usd
from app.modules.provider_compatibility.namespaces import source_preserves_tool_call_namespaces


def source():
    return SimpleNamespace(id="source-test", models=[], base_url="https://compass.llm.shopee.io/v1")


@pytest.mark.parametrize(
    "input_tokens,cached,output,tier,expected",
    [
        (100_000, 20_000, 10_000, None, 1.32),
        (272_000, 100_000, 10_000, None, 2.32),
        (272_001, 100_000, 10_000, None, 4.39002),
        (300_000, 100_000, 10_000, None, 4.95),
        (300_000, 100_000, 10_000, "priority", 9.9),
        (300_000, 100_000, 10_000, "flex", 2.475),
    ],
)
def test_standard_cached_long_context_and_tiers(input_tokens, cached, output, tier, expected):
    usage = SourceUsage(input_tokens, output, cached, service_tier=tier)
    quote = quote_usage(source(), "gpt-6-astra", usage)
    assert quote is not None
    assert quote.cost_usd == pytest.approx(expected)
    assert quote.uncached_input_tokens == input_tokens - cached
    assert quote.provider_cost_usd is None
    assert quote.tool_call_cost is None
    assert quote.cache_write_tokens is None


def test_same_usage_keeps_price_snapshot_during_catalog_refresh(monkeypatch):
    from app.modules.provider_billing import service

    usage = SourceUsage(100, 20)
    quote = quote_usage(source(), "gpt-6-astra", usage)
    resolved = get_pricing_for_model("gpt-6-astra")
    assert resolved is not None
    monkeypatch.setattr(service, "get_pricing_for_model", lambda model: (model, replace(resolved[1], input_per_1m=999)))
    assert quote_usage(source(), "gpt-6-astra", usage) is quote
    assert quote_usage(source(), "gpt-6-astra", SourceUsage(100, 20)).pricing_version != quote.pricing_version


def test_provider_tier_is_taken_from_response_not_requested_tier():
    usage = _usage_from_responses_payload(
        {"service_tier": "priority", "usage": {"input_tokens": 100, "output_tokens": 20}}
    )
    assert usage is not None and usage.service_tier == "priority"
    assert source_usage_cost_usd(source(), "gpt-6-astra", usage) == pytest.approx(0.004)


def test_compass_namespace_policy_and_explicit_opt_out():
    provider = source()
    assert source_preserves_tool_call_namespaces(provider, "gpt-6-astra")
    provider.models = [
        SimpleNamespace(
            model="gpt-6-astra", is_enabled=True, raw_metadata_json='{"preserve_tool_call_namespaces":false}'
        )
    ]
    assert not source_preserves_tool_call_namespaces(provider, "gpt-6-astra")
    provider.base_url = "https://legacy.example/v1"
    provider.models = []
    assert not source_preserves_tool_call_namespaces(provider, "gpt-6-astra")

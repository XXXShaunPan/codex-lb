from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from app.core.usage.pricing import ModelPrice, UsageTokens, calculate_cost_breakdown_from_usage, get_pricing_for_model

if TYPE_CHECKING:
    from app.db.models import ModelSource
    from app.modules.model_sources.forwarding import SourceUsage


@dataclass(frozen=True, slots=True)
class BillingQuote:
    model: str
    pricing_source: str
    pricing_version: str
    rates_json: str
    uncached_input_tokens: int
    cached_read_tokens: int
    cache_write_tokens: int | None
    output_tokens: int
    service_tier: str
    input_usd: float
    cached_read_usd: float
    output_usd: float
    cost_usd: float
    # Unknown dimensions must never be confused with an observed zero cost.
    cache_write_usd: float | None = None
    tool_call_cost: float | None = None
    provider_cost_usd: float | None = None


def quote_usage(source: ModelSource, model: str, usage: SourceUsage | None) -> BillingQuote | None:
    if usage is None:
        return None
    cache_key = (source.id, model)
    if cache_key in usage.billing_quotes:
        return usage.billing_quotes[cache_key]
    resolved = get_pricing_for_model(model)
    pricing_source = "account_pool"
    if resolved is not None:
        canonical_model, price = resolved
    else:
        entry = next((entry for entry in source.models if entry.model == model and entry.is_enabled), None)
        if entry is None or all(
            value is None for value in (entry.input_per_1m, entry.cached_input_per_1m, entry.output_per_1m)
        ):
            usage.billing_quotes[cache_key] = None
            return None
        canonical_model = model
        pricing_source = "source_custom"
        price = ModelPrice(
            input_per_1m=entry.input_per_1m or 0.0,
            cached_input_per_1m=entry.cached_input_per_1m,
            output_per_1m=entry.output_per_1m or 0.0,
        )
    tier = usage.service_tier or "standard"
    normalized = UsageTokens(usage.input_tokens, usage.output_tokens, usage.cached_input_tokens)
    breakdown = calculate_cost_breakdown_from_usage(normalized, price, service_tier=tier)
    if breakdown is None or breakdown.total_usd is None:
        return None
    rates = json.dumps(
        {"model": canonical_model, "price": asdict(price), "service_tier": tier, "policy": "relay-account-pool-v1"},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    quote = BillingQuote(
        model=model,
        pricing_source=pricing_source,
        pricing_version="sha256:" + hashlib.sha256(rates.encode()).hexdigest(),
        rates_json=rates,
        uncached_input_tokens=max(0, usage.input_tokens - usage.cached_input_tokens),
        cached_read_tokens=usage.cached_input_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        output_tokens=usage.output_tokens,
        service_tier=tier,
        input_usd=breakdown.input_usd or 0.0,
        cached_read_usd=breakdown.cached_input_usd or 0.0,
        output_usd=breakdown.output_usd or 0.0,
        cost_usd=breakdown.total_usd,
    )
    usage.billing_quotes[cache_key] = quote
    return quote


def source_usage_cost_usd(source: ModelSource, model: str, usage: SourceUsage | None) -> float | None:
    quote = quote_usage(source, model, usage)
    return quote.cost_usd if quote is not None else (0.0 if usage is not None else None)

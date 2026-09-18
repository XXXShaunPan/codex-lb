from __future__ import annotations

import uuid
from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.time import utcnow
from app.db.models import RequestLog
from app.modules.provider_billing.models import ProviderBillingEntry
from app.modules.provider_billing.service import BillingQuote


async def record_quote(
    session: AsyncSession,
    log: RequestLog,
    quote: BillingQuote,
    *,
    charged_usd: float | None = None,
    usage_basis: str = "reported",
) -> None:
    """Persist alongside the request log in the same transaction."""
    entry = ProviderBillingEntry(
        id=uuid.uuid4().hex,
        request_log_id=log.id,
        request_id=log.request_id,
        api_key_id=log.api_key_id,
        source_id=log.model_source_id,
        status=log.status,
        charged_usd=(quote.cost_usd if log.status == "success" else 0.0) if charged_usd is None else charged_usd,
        usage_basis=usage_basis,
        created_at=utcnow(),
        **asdict(quote),
    )
    session.add(entry)

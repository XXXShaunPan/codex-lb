"""Preserve immutable per-attempt billing evidence for relay model sources."""

import sqlalchemy as sa
from alembic import op

revision = "20260918_000000_add_provider_billing_entries"
down_revision = "20260910_000000_request_logs_missing_cost_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_billing_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("request_log_id", sa.Integer(), sa.ForeignKey("request_logs.id", ondelete="SET NULL"), unique=True),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("api_key_id", sa.String()),
        sa.Column("source_id", sa.String()),
        *[
            sa.Column(name, sa.String(), nullable=False)
            for name in ("model", "status", "pricing_source", "pricing_version", "service_tier", "usage_basis")
        ],
        sa.Column("rates_json", sa.Text(), nullable=False),
        *[
            sa.Column(name, sa.Integer(), nullable=False)
            for name in ("uncached_input_tokens", "cached_read_tokens", "output_tokens")
        ],
        sa.Column("cache_write_tokens", sa.Integer()),
        *[
            sa.Column(name, sa.Float(), nullable=False)
            for name in ("input_usd", "cached_read_usd", "output_usd", "cost_usd", "charged_usd")
        ],
        *[sa.Column(name, sa.Float()) for name in ("cache_write_usd", "tool_call_cost", "provider_cost_usd")],
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_provider_billing_entries_request_id", "provider_billing_entries", ["request_id"])
    op.create_index("ix_provider_billing_entries_api_key_id", "provider_billing_entries", ["api_key_id"])


def downgrade() -> None:
    op.drop_table("provider_billing_entries")

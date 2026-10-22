"""Persist routing priority rules and hysteresis independently of upstream tables."""

import sqlalchemy as sa
from alembic import op

revision = "20261022_000000_add_routing_priority_rules"
down_revision = "20261020_000000_add_custom_routing_weights"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "relay_routing_rules",
        sa.Column("scope", sa.String(), primary_key=True),
        sa.Column("target", sa.String(), primary_key=True),
        sa.Column("normal_priority", sa.Integer(), nullable=False),
        sa.Column("low_priority", sa.Integer(), nullable=False),
        sa.Column("downgrade_percent", sa.Float(), nullable=False),
        sa.Column("recovery_percent", sa.Float(), nullable=False),
        sa.Column("quota_basis", sa.String(), nullable=False),
        sa.Column("allow_low_quota", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "relay_routing_quota_bands",
        sa.Column("account_id", sa.String(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("low_quota", sa.Boolean(), nullable=False),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column("sample_at", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("relay_routing_quota_bands")
    op.drop_table("relay_routing_rules")

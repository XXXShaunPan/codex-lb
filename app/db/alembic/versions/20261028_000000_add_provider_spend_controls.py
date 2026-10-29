"""Keep provider spending budgets separate from subscription usage windows."""

import sqlalchemy as sa
from alembic import op

revision = "20261028_000000_add_provider_spend_controls"
down_revision = "20261027_010000_add_image_routing_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_billing_spend_controls",
        sa.Column("account_id", sa.String(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("provider_billing_spend_controls")

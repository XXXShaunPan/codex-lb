"""Add operator weights without changing existing routing strategies."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_000000_add_custom_routing_weights"
down_revision = "20260918_010000_add_visitor_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("accounts", "model_sources"):
        op.add_column(table, sa.Column("routing_weight", sa.Float(), nullable=False, server_default=sa.text("1")))


def downgrade() -> None:
    for table in ("model_sources", "accounts"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("routing_weight")

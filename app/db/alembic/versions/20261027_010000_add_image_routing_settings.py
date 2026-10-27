"""Configure the subscription image-tool host separately from public image models."""

import sqlalchemy as sa
from alembic import op

revision = "20261027_010000_add_image_routing_settings"
down_revision = "20261027_000000_add_codex_config_token_pool"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("request_logs", sa.Column("image_host_model", sa.String(), nullable=True))
    op.create_table(
        "relay_image_routing_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host_model", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("request_logs", "image_host_model")
    op.drop_table("relay_image_routing_settings")

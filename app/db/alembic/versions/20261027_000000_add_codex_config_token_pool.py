"""Store future API tokens without rotating or attempting to recover old hashes."""

import sqlalchemy as sa
from alembic import op

revision = "20261027_000000_add_codex_config_token_pool"
down_revision = "20261022_000000_add_routing_priority_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "codex_config_api_tokens",
        sa.Column("api_key_id", sa.String(), sa.ForeignKey("api_keys.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("codex_config_api_tokens")

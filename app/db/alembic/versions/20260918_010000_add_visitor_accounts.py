"""Move relay visitors under the main database migration lifecycle."""

import sqlalchemy as sa
from alembic import op

revision = "20260918_010000_add_visitor_accounts"
down_revision = "20260918_000000_add_provider_billing_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visitor_accounts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )
    op.create_table(
        "visitor_api_keys",
        sa.Column(
            "visitor_id", sa.String(), sa.ForeignKey("visitor_accounts.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("api_key_id", sa.String(), primary_key=True),
    )
    op.create_index("ix_visitor_api_keys_api_key_id", "visitor_api_keys", ["api_key_id"])


def downgrade() -> None:
    op.drop_table("visitor_api_keys")
    op.drop_table("visitor_accounts")

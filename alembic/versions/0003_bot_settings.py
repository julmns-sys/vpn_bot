"""add bot settings

Revision ID: 0003_bot_settings
Revises: 0002_vpn_alert_flags
Create Date: 2026-06-23 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_bot_settings"
down_revision = "0002_vpn_alert_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("bot_settings")

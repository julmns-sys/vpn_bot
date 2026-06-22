"""add vpn alert flags

Revision ID: 0002_vpn_alert_flags
Revises: 0001_initial
Create Date: 2026-06-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_vpn_alert_flags"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vpn_accounts", sa.Column("alert_3d_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vpn_accounts", sa.Column("alert_1d_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("vpn_accounts", "alert_1d_sent_at")
    op.drop_column("vpn_accounts", "alert_3d_sent_at")

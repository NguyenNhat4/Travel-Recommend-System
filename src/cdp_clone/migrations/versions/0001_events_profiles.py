"""events and profiles

Revision ID: 0001
Revises:
Create Date: 2026-09-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("cdp_user_id", sa.String(64), nullable=False),
        sa.Column("event_name", sa.String(32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_id", sa.String(128)),
        sa.Column("taxonomy", sa.String(16)),
        sa.Column("event_group_id", sa.String(64)),
        sa.Column("quantity", sa.Integer),
        sa.Column("unit_price", sa.Float),
        sa.Column("using_date", sa.Date),
        sa.Column("search_query", sa.String(500)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("cdp_user_id", "event_id", name="uq_events_cdp_user_id_event_id"),
    )
    op.create_index("ix_events_cdp_user_id_timestamp", "events", ["cdp_user_id", "timestamp"])
    op.create_table(
        "profiles",
        sa.Column("cdp_user_id", sa.String(64), primary_key=True),
        sa.Column("lifecycle_stage", sa.String(16)),
        sa.Column("days_since_last_booking", sa.Integer),
        sa.Column("lifetime_order_count", sa.Integer),
        sa.Column("vinclub_tier", sa.String(32)),
        sa.Column("purchased_verticals", sa.JSON, nullable=False),
        sa.Column("home_city", sa.String(128)),
        sa.Column("last_destination", sa.String(128)),
        sa.Column("email_optin", sa.Boolean),
        sa.Column("sms_optin", sa.Boolean),
        sa.Column("push_optin", sa.Boolean),
        sa.Column("gdpr_optin", sa.Boolean),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("profiles")
    op.drop_index("ix_events_cdp_user_id_timestamp", table_name="events")
    op.drop_table("events")

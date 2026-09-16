"""CDP clone tables. Column names follow handbook §6 (snake_case); keep in sync with migrations/versions."""
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

events = Table(
    "events",
    metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("event_id", String(128), nullable=False),
    Column("cdp_user_id", String(64), nullable=False),
    Column("event_name", String(32), nullable=False),
    Column("timestamp", DateTime(timezone=True), nullable=False),
    Column("product_id", String(128)),
    Column("taxonomy", String(16)),
    Column("event_group_id", String(64)),
    Column("quantity", Integer),
    Column("unit_price", Float),
    Column("using_date", Date),
    Column("search_query", String(500)),
    Column("received_at", DateTime(timezone=True), nullable=False),
    Column("cancelled_at", DateTime(timezone=True)),
    UniqueConstraint("cdp_user_id", "event_id", name="uq_events_cdp_user_id_event_id"),
    Index("ix_events_cdp_user_id_timestamp", "cdp_user_id", "timestamp"),
)

profiles = Table(
    "profiles",
    metadata,
    Column("cdp_user_id", String(64), primary_key=True),
    Column("lifecycle_stage", String(16)),
    Column("days_since_last_booking", Integer),
    Column("lifetime_order_count", Integer),
    Column("vinclub_tier", String(32)),
    Column("purchased_verticals", JSON, nullable=False),
    Column("home_city", String(128)),
    Column("last_destination", String(128)),
    Column("email_optin", Boolean),
    Column("sms_optin", Boolean),
    Column("push_optin", Boolean),
    Column("gdpr_optin", Boolean),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

"""SQLAlchemy mappings for the tables this pipeline touches.

**The ``.sql`` files in ``migrations/`` are the source of truth, not this
module.** Spec sections 4.1 and 4.2 ship the DDL verbatim and call it
authoritative; reproducing it a second time in Python would give two definitions
that can drift, and the one the spec wrote would lose. So nothing here creates
tables (there is no ``Base.metadata.create_all`` call anywhere in this project),
and :func:`verify_models_against_db` exists to catch drift in the other
direction.

Things SQLAlchemy cannot express cleanly, and how they are handled:

* ``CHECK (taxonomy IN (...))`` — declared here as a ``CheckConstraint`` for
  documentation value; enforcement is Postgres's.
* ``CHAR(3)`` for ``currency`` — mapped as ``CHAR(3)``, which pads on read.
  Callers must ``.strip()``; see :data:`CURRENCY_LEN`.
* ``events.product_id`` has **no** ForeignKey, deliberately (spec section 4.2:
  "cố tình KHÔNG có FK: phải có event trỏ vào product đã xoá"). Adding one here
  would make the ORM reject exactly the messy-edge rows section 10 requires.
* GIN / trgm / ``NULLS NOT DISTINCT`` indexes are not declared here at all —
  they live in the migrations, because SQLAlchemy's ``Index`` cannot express
  ``gin_trgm_ops`` or PG16 null-distinctness without dialect escapes that read
  worse than the SQL.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CHAR,
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

CURRENCY_LEN = 3

# Frozen copy of the spec section 4.2 `products` column list, in order.
# load.py projects a merged product onto exactly these names and asserts the
# match, so a field that is not a CDP column cannot reach an INSERT.
PRODUCTS_COLUMNS: tuple[str, ...] = (
    "product_id",
    "name",
    "taxonomy",
    "destination",
    "description",
    "attributes",
    "unit_price",
    "currency",
    "available",
    "available_from",
    "available_to",
    "image_url",
    "source_ref",
    "latitude",
    "longitude",
    "images",
    "quality_score",
    "created_at",
    "updated_at",
)

TAXONOMY_VALUES = ("hotel", "flight", "combo", "attraction", "golf")


class Base(DeclarativeBase):
    pass


# =============================================================================
# 001 — crawl layer
# =============================================================================
class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class CrawlTarget(Base):
    __tablename__ = "crawl_targets"
    __table_args__ = (UniqueConstraint("source", "url_hash", "quote_ctx"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(Text, nullable=False)
    page_type: Mapped[str] = mapped_column(Text, nullable=False)
    quote_ctx: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    discovered_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RawPage(Base):
    __tablename__ = "raw_pages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("crawl_runs.id")
    )
    target_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("crawl_targets.id"))
    source: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    quote_ctx: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class ProductStaging(Base):
    __tablename__ = "products_staging"
    __table_args__ = (UniqueConstraint("source", "source_ref", "parser_version"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    raw_page_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("raw_pages.id"))
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parsed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# =============================================================================
# 002 — CDP clone
# =============================================================================
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "taxonomy IN ('hotel','flight','combo','attraction','golf')",
            name="products_taxonomy_check",
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    taxonomy: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="VND")
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    available_from: Mapped[dt.date | None] = mapped_column(Date)
    available_to: Mapped[dt.date | None] = mapped_column(Date)
    image_url: Mapped[str | None] = mapped_column(Text)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    images: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    quality_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProductSource(Base):
    __tablename__ = "product_sources"
    __table_args__ = (PrimaryKeyConstraint("source", "source_ref"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.product_id", ondelete="CASCADE")
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    match_score: Mapped[float | None] = mapped_column(Float)


class Profile(Base):
    __tablename__ = "profiles"

    cdp_user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    lifecycle_stage: Mapped[str | None] = mapped_column(Text)
    days_since_last_booking: Mapped[int | None] = mapped_column(Integer)
    lifetime_order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vinclub_tier: Mapped[str | None] = mapped_column(Text)
    purchased_verticals: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    home_city: Mapped[str | None] = mapped_column(Text)
    last_destination: Mapped[str | None] = mapped_column(Text)
    gdpr_optin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_optin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_optin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    push_optin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cdp_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("profiles.cdp_user_id"), nullable=False
    )
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # No ForeignKey on purpose — see the module docstring.
    product_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    taxonomy: Mapped[str | None] = mapped_column(Text)
    event_group_id: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int | None] = mapped_column(Integer)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    using_date: Mapped[dt.date | None] = mapped_column(Date)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    cdp_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("profiles.cdp_user_id"), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cdp_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_group_id: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    using_date: Mapped[dt.date | None] = mapped_column(Date)
    reference_no: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# =============================================================================
# 004 — crawl-layer support (NOT part of the CDP contract)
# =============================================================================
class ProductNormalised(Base):
    __tablename__ = "products_normalised"
    __table_args__ = (UniqueConstraint("source", "source_ref", "normaliser_version"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    staging_id: Mapped[int | None] = mapped_column(BigInteger)
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)
    normaliser_version: Mapped[str] = mapped_column(Text, nullable=False)

    page_kind: Mapped[str] = mapped_column(Text, nullable=False, default="product")
    parent_source_ref: Mapped[str | None] = mapped_column(Text)

    name: Mapped[str | None] = mapped_column(Text)
    taxonomy: Mapped[str | None] = mapped_column(Text)
    destination: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    description: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, default="VND")
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    available_from: Mapped[dt.date | None] = mapped_column(Date)
    available_to: Mapped[dt.date | None] = mapped_column(Date)
    image_url: Mapped[str | None] = mapped_column(Text)
    images: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    quality_score: Mapped[float | None] = mapped_column(Float)

    name_normalized: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    star_rating: Mapped[float | None] = mapped_column(Float)
    brand: Mapped[str | None] = mapped_column(Text)

    destination_raw: Mapped[str | None] = mapped_column(Text)
    dest_match_method: Mapped[str | None] = mapped_column(Text)
    price_raw: Mapped[str | None] = mapped_column(Text)
    fx_rate_used: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    quote_ctx: Mapped[str | None] = mapped_column(Text)
    normalised_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProductLoadMeta(Base):
    __tablename__ = "product_load_meta"

    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.product_id", ondelete="CASCADE"), primary_key=True
    )
    cluster_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    dedup_version: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    loaded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# Tables this module claims to describe. verify_models_against_db() is scoped to
# this list so the crawl-layer tables that intentionally have no mapping
# (dedup_pairs, product_clusters, source_state, ...) do not register as drift.
OWNED_TABLES: tuple[str, ...] = tuple(
    m.__tablename__
    for m in (
        CrawlRun,
        CrawlTarget,
        RawPage,
        ProductStaging,
        Product,
        ProductSource,
        Profile,
        Event,
        User,
        Booking,
        ProductNormalised,
        ProductLoadMeta,
    )
)


def verify_models_against_db(engine) -> list[str]:  # noqa: ANN001
    """Report where these mappings and the live schema disagree.

    Returns a list of human-readable problems; empty means they agree. Used by
    a test and by ``cli migrate --verify`` — never to mutate the database.
    """
    problems: list[str] = []
    insp = inspect(engine)
    live_tables = set(insp.get_table_names())

    for model in Base.registry.mappers:
        cls = model.class_
        tname = cls.__tablename__
        if tname not in OWNED_TABLES:
            continue
        if tname not in live_tables:
            problems.append(f"{tname}: table missing from database (run `cli migrate`)")
            continue
        live_cols = {c["name"] for c in insp.get_columns(tname)}
        model_cols = {c.name for c in cls.__table__.columns}
        for missing in sorted(model_cols - live_cols):
            problems.append(f"{tname}.{missing}: in models.py but not in the database")
        for extra in sorted(live_cols - model_cols):
            problems.append(f"{tname}.{extra}: in the database but not in models.py")

    # The Week-1 invariant that matters most (spec section 4.3).
    with engine.connect() as conn:
        has_vector = conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).first()
    if has_vector:
        problems.append(
            "the `vector` extension is installed: 003_pgvector.sql was applied, which "
            "freezes the embedding dimension before the Week 2 model decision "
            "(spec section 4.3)"
        )

    return problems

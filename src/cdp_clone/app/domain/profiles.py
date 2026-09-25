from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ProfileAttributes:
    """CDP Profile Store snapshot (handbook §6). Written by seed/Backend, not derived from events."""

    lifecycle_stage: str | None = None
    days_since_last_booking: int | None = None
    lifetime_order_count: int | None = None
    vinclub_tier: str | None = None
    purchased_verticals: tuple[str, ...] = field(default_factory=tuple)
    home_city: str | None = None
    last_destination: str | None = None
    email_optin: bool | None = None
    sms_optin: bool | None = None
    push_optin: bool | None = None
    gdpr_optin: bool | None = None


@dataclass(frozen=True)
class Profile:
    cdp_user_id: str
    attributes: ProfileAttributes
    updated_at: datetime

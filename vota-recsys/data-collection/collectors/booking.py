"""booking.com — breadth of Vietnamese accommodation with structured attributes.

Spec section 7 makes booking.com the winner for structured ``attributes``
(amenities, starRating), which is why it is worth having at all: vinpearl has
the best Vietnamese prose, booking has the most consistent structured fields.

Expected outcome is a block. See ``collectors/ota.py`` for why that is the
correct result rather than a bug, and what is deliberately not implemented.
"""

from __future__ import annotations

from collectors.base import register
from collectors.ota import OtaHotelCollector


@register
class BookingCollector(OtaHotelCollector):
    source = "booking"
    parser_version = "booking-1.0.0"
    rate_limit_rps = 0.5
    # booking embeds a Next.js payload, so that is tried before DOM selectors.
    default_extract_preference = ("jsonld", "next_data", "dom")

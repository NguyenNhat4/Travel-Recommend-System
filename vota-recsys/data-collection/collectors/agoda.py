"""agoda.com — domestic Vietnamese coverage, often better than global sites.

Spec section 1 keeps agoda for coverage rather than for any single field it
wins: it sits below booking in the section 7 precedence order for structured
attributes and below vinpearl for content.

Expected outcome is a block. See ``collectors/ota.py``.
"""

from __future__ import annotations

from collectors.base import register
from collectors.ota import OtaHotelCollector


@register
class AgodaCollector(OtaHotelCollector):
    source = "agoda"
    parser_version = "agoda-1.0.0"
    rate_limit_rps = 0.5
    # agoda uses a Redux-style initial state rather than __NEXT_DATA__.
    default_extract_preference = ("jsonld", "initial_state", "dom")

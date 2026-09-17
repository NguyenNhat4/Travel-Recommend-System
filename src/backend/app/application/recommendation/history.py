"""Read user history for recommendations without letting a CDP outage fail the request."""
import logging
from datetime import datetime

from src.backend.app.application.ports.cdp_client import CdpClient, CdpUnavailableError, UserEvent
from src.backend.app.core.request_context import current_request_id

logger = logging.getLogger(__name__)

# Bounded read keeps /recommendations inside its 300 ms p95 budget for heavy users.
DEFAULT_MAX_EVENTS = 500


async def load_history(
    cdp: CdpClient,
    cdp_user_id: str,
    *,
    since: datetime | None = None,
    max_events: int = DEFAULT_MAX_EVENTS,
) -> list[UserEvent] | None:
    """Newest-first events, or None when the CDP is unavailable.

    None means: answer 200 with strategy "popular", empty because[], diagnostics.coldStart true, eventsUsed 0
    (paths/recommendations.yaml). An empty list means the user genuinely has no history.
    """
    try:
        return await cdp.list_events(cdp_user_id, since=since, max_events=max_events)
    except CdpUnavailableError as exc:
        logger.warning("CDP history unavailable, falling back to popular requestId=%s reason=%s",
                       current_request_id(), exc)
        return None

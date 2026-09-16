"""Keep bookings and purchase events consistent across two services (hop-dong-tich-hop-backend.md §7.4)."""
import logging
from typing import Awaitable, Callable, Sequence, TypeVar

from src.backend.app.application.ports.cdp_client import CdpClient, CdpUnavailableError, PurchaseEvent
from src.backend.app.core.request_context import current_request_id

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def commit_with_purchase_events(
    cdp: CdpClient,
    events: Sequence[PurchaseEvent],
    commit: Callable[[], Awaitable[T]],
) -> T:
    """Write purchases to the CDP, then commit the booking.

    - CDP fails: CdpUnavailableError propagates before commit; the caller rolls back and answers
      500 INTERNAL_ERROR retryable, keeping the cart.
    - Commit fails: the purchases are cancelled on the CDP (compensation), then the commit error propagates.
    """
    await cdp.record_purchases(events)
    try:
        return await commit()
    except BaseException:
        await _cancel_quietly(cdp, events)
        raise


async def _cancel_quietly(cdp: CdpClient, events: Sequence[PurchaseEvent]) -> None:
    try:
        await cdp.cancel_purchases(events)
    except CdpUnavailableError:
        # Orphan purchase left in CDP: needs manual cancellation. bookingItemIds are not personal data.
        booking_item_ids = sorted({e.booking_item_id for e in events})
        logger.error(
            "Could not cancel purchase events after failed booking commit requestId=%s bookingItemIds=%s",
            current_request_id(),
            booking_item_ids,
        )

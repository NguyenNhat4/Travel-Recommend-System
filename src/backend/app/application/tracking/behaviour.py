"""Build browse events from what Backend itself saw, with taxonomy and price taken from the catalog, never the client.

Callers: POST /api/v1/events (product_view), POST /api/v1/search (search), POST /api/v1/cart/items (add_to_cart).
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Protocol

from src.backend.app.application.ports.cdp_client import BrowseEvent, BrowseEventName, BrowseEventRecorder


@dataclass(frozen=True)
class CatalogProduct:
    product_id: str
    taxonomy: str
    unit_price: float | None


class ProductLookup(Protocol):
    async def find_product(self, product_id: str) -> CatalogProduct | None:
        ...


class ProductNotFoundError(Exception):
    def __init__(self, product_id: str):
        super().__init__(product_id)
        self.product_id = product_id


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _event_id(event_name: BrowseEventName) -> str:
    return f"{event_name}:{uuid.uuid4()}"


class BehaviourTracker:
    def __init__(
        self,
        recorder: BrowseEventRecorder,
        products: ProductLookup,
        *,
        clock: Callable[[], datetime] = _utc_now,
        new_event_id: Callable[[BrowseEventName], str] = _event_id,
    ):
        self._recorder = recorder
        self._products = products
        self._clock = clock
        self._new_event_id = new_event_id

    async def track_product_view(self, cdp_user_id: str, product_id: str) -> None:
        """Raises ProductNotFoundError (404 PRODUCT_NOT_FOUND) so unknown IDs never reach the CDP."""
        product = await self._products.find_product(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        self._record(cdp_user_id, "product_view", product_id=product.product_id, taxonomy=product.taxonomy)

    def track_search(self, cdp_user_id: str | None, query: str, offset: int) -> None:
        """Only signed-in users' first page. Agent calls /search without JWT, so its searches are not recorded."""
        if cdp_user_id is None or offset > 0 or not query.strip():
            return
        self._record(cdp_user_id, "search", search_query=query.strip()[:500])

    def track_add_to_cart(self, cdp_user_id: str, product: CatalogProduct, quantity: int, using_date: date) -> None:
        """Call only after the cart write succeeded."""
        self._record(
            cdp_user_id,
            "add_to_cart",
            product_id=product.product_id,
            taxonomy=product.taxonomy,
            quantity=quantity,
            unit_price=product.unit_price,
            using_date=using_date,
        )

    def _record(self, cdp_user_id: str, event_name: BrowseEventName, **fields) -> None:
        self._recorder.record(
            BrowseEvent(
                event_id=self._new_event_id(event_name),
                cdp_user_id=cdp_user_id,
                event_name=event_name,
                timestamp=self._clock(),
                **fields,
            )
        )

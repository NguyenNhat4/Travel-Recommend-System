"""CdpClient adapter for src/cdp_clone (contract: src/shared/contracts/cdp-clone.openapi.yaml)."""
from datetime import date, datetime
from typing import Sequence
from urllib.parse import quote

import httpx

from src.backend.app.application.ports.cdp_client import (
    BrowseEvent,
    CdpProfile,
    CdpUnavailableError,
    PurchaseEvent,
    UserEvent,
)
from src.backend.app.core.request_context import REQUEST_ID_HEADER, current_request_id

MAX_EVENTS_PER_REQUEST = 100
MAX_PAGE_SIZE = 500


class CdpHttpClient:
    def __init__(self, http: httpx.AsyncClient, service_token: str):
        # http carries base_url and timeout; the token stays out of logs and URLs.
        self._http = http
        self._service_token = service_token

    async def record_purchases(self, events: Sequence[PurchaseEvent]) -> None:
        await self._record([_purchase_body(e) for e in events], request_id=None)

    async def cancel_purchases(self, events: Sequence[PurchaseEvent]) -> None:
        for event in events:
            url = f"/cdp/v1/users/{_path(event.cdp_user_id)}/events/{_path(event.event_id)}/cancellation"
            response = await self._send("PUT", url)
            if response.status_code not in (200, 404):
                raise CdpUnavailableError(f"CDP could not cancel event: HTTP {response.status_code}")

    async def record_browse_events(self, events: Sequence[BrowseEvent], *, request_id: str | None = None) -> None:
        await self._record([_browse_body(e) for e in events], request_id=request_id)

    async def list_events(
        self,
        cdp_user_id: str,
        *,
        since: datetime | None = None,
        event_name: str | None = None,
        max_events: int = 500,
    ) -> list[UserEvent]:
        params: dict[str, str | int] = {}
        if since:
            params["since"] = since.isoformat()
        if event_name:
            params["eventName"] = event_name
        events: list[UserEvent] = []
        while len(events) < max_events:
            params["offset"] = len(events)
            params["limit"] = min(MAX_PAGE_SIZE, max_events - len(events))
            response = await self._send("GET", f"/cdp/v1/users/{_path(cdp_user_id)}/events", params=params)
            if response.status_code != 200:
                raise CdpUnavailableError(f"CDP event history unavailable: HTTP {response.status_code}")
            page = response.json()
            events.extend(_to_event(e) for e in page["events"])
            if not page["events"] or len(events) >= page["total"]:
                break
        return events

    async def get_profile(self, cdp_user_id: str) -> CdpProfile | None:
        response = await self._send("GET", f"/cdp/v1/profiles/{_path(cdp_user_id)}")
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise CdpUnavailableError(f"CDP profile unavailable: HTTP {response.status_code}")
        return _to_profile(response.json())

    async def _record(self, bodies: list[dict], request_id: str | None) -> None:
        for start in range(0, len(bodies), MAX_EVENTS_PER_REQUEST):
            chunk = bodies[start:start + MAX_EVENTS_PER_REQUEST]
            response = await self._send("POST", "/cdp/v1/events", json={"events": chunk}, request_id=request_id)
            if response.status_code != 201:
                raise CdpUnavailableError(f"CDP rejected events: HTTP {response.status_code}")
            if len(response.json()["results"]) != len(chunk):
                raise CdpUnavailableError("CDP acknowledged a different number of events")

    async def _send(self, method: str, url: str, *, request_id: str | None = None, **kwargs) -> httpx.Response:
        headers = {"X-Service-Token": self._service_token}
        request_id = request_id or current_request_id()
        if request_id:
            headers[REQUEST_ID_HEADER] = request_id
        try:
            return await self._http.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise CdpUnavailableError(f"CDP request failed: {type(exc).__name__}") from exc


def _path(value: str) -> str:
    return quote(value, safe="")


def _purchase_body(event: PurchaseEvent) -> dict:
    return {
        "eventId": event.event_id,
        "cdpUserId": event.cdp_user_id,
        "eventName": "purchase",
        "timestamp": event.timestamp.isoformat(),
        "productId": event.product_id,
        "taxonomy": event.taxonomy,
        "eventGroupId": event.event_group_id,
        "quantity": event.quantity,
        "unitPrice": event.unit_price,
        "usingDate": event.using_date.isoformat(),
    }


def _browse_body(event: BrowseEvent) -> dict:
    body = {
        "eventId": event.event_id,
        "cdpUserId": event.cdp_user_id,
        "eventName": event.event_name,
        "timestamp": event.timestamp.isoformat(),
        "productId": event.product_id,
        "taxonomy": event.taxonomy,
        "quantity": event.quantity,
        "unitPrice": event.unit_price,
        "usingDate": event.using_date.isoformat() if event.using_date else None,
        "searchQuery": event.search_query,
    }
    return {key: value for key, value in body.items() if value is not None}


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _to_event(data: dict) -> UserEvent:
    return UserEvent(
        event_id=data["eventId"],
        cdp_user_id=data["cdpUserId"],
        event_name=data["eventName"],
        timestamp=_datetime(data["timestamp"]),
        product_id=data["productId"],
        taxonomy=data["taxonomy"],
        event_group_id=data["eventGroupId"],
        quantity=data["quantity"],
        unit_price=data["unitPrice"],
        using_date=date.fromisoformat(data["usingDate"]) if data["usingDate"] else None,
        search_query=data["searchQuery"],
    )


def _to_profile(data: dict) -> CdpProfile:
    attributes = data["attributes"]
    return CdpProfile(
        cdp_user_id=data["cdpUserId"],
        lifecycle_stage=attributes.get("lifecycleStage"),
        days_since_last_booking=attributes.get("daysSinceLastBooking"),
        lifetime_order_count=attributes.get("lifetimeOrderCount"),
        vinclub_tier=attributes.get("vinclubTier"),
        purchased_verticals=tuple(attributes.get("purchasedVerticals") or ()),
        home_city=attributes.get("homeCity"),
        last_destination=attributes.get("lastDestination"),
        email_optin=attributes.get("emailOptin"),
        sms_optin=attributes.get("smsOptin"),
        push_optin=attributes.get("pushOptin"),
        gdpr_optin=attributes.get("gdprOptin"),
        updated_at=_datetime(data["updatedAt"]),
    )

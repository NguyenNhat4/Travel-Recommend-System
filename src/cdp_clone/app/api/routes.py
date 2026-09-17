import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from src.cdp_clone.app.api import schemas
from src.cdp_clone.app.api.auth import require_service_token
from src.cdp_clone.app.api.errors import ApiError
from src.cdp_clone.app.domain.events import EventDraft, EventRuleError, UserEvent, prepare_events
from src.cdp_clone.app.domain.profiles import Profile, ProfileAttributes
from src.cdp_clone.app.infrastructure.repository import CdpRepository

router = APIRouter(prefix="/cdp/v1", dependencies=[Depends(require_service_token)])

CdpUserId = Annotated[str, Path(alias="cdpUserId", min_length=1, max_length=64)]


def get_repository(request: Request) -> CdpRepository:
    return request.app.state.repository


Repository = Annotated[CdpRepository, Depends(get_repository)]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/events", status_code=201, response_model=schemas.RecordEventsResponse, tags=["events"])
def record_events(body: schemas.RecordEventsRequest, repository: Repository):
    now = utc_now()
    drafts = [
        EventDraft(
            cdp_user_id=e.cdp_user_id,
            event_name=e.event_name,
            event_id=e.event_id,
            timestamp=e.timestamp.astimezone(timezone.utc) if e.timestamp else None,
            product_id=e.product_id,
            taxonomy=e.taxonomy,
            event_group_id=e.event_group_id,
            quantity=e.quantity,
            unit_price=e.unit_price,
            using_date=e.using_date,
            search_query=e.search_query,
        )
        for e in body.events
    ]
    try:
        events = prepare_events(drafts, now, lambda: str(uuid.uuid4()))
    except EventRuleError as exc:
        raise ApiError(400, exc.code, exc.message, exc.details) from None
    created = repository.insert_events(events, received_at=now)
    return schemas.RecordEventsResponse(
        results=[
            schemas.RecordedEvent(event_id=e.event_id, status="created" if ok else "duplicate")
            for e, ok in zip(events, created)
        ]
    )


@router.get("/users/{cdpUserId}/events", response_model=schemas.EventListResponse, tags=["events"])
def list_user_events(
    cdp_user_id: CdpUserId,
    repository: Repository,
    event_name: Annotated[schemas.EventName | None, Query(alias="eventName")] = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    include_cancelled: Annotated[bool, Query(alias="includeCancelled")] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    events, total = repository.list_events(
        cdp_user_id,
        event_name=event_name,
        since=_as_utc(since),
        until=_as_utc(until),
        include_cancelled=include_cancelled,
        limit=limit,
        offset=offset,
    )
    return schemas.EventListResponse(events=[_event_out(e) for e in events], total=total, limit=limit, offset=offset)


@router.put("/users/{cdpUserId}/events/{eventId}/cancellation", response_model=schemas.UserEvent, tags=["events"])
def cancel_event(
    cdp_user_id: CdpUserId,
    event_id: Annotated[str, Path(alias="eventId", min_length=1, max_length=128)],
    repository: Repository,
):
    event = repository.cancel_event(cdp_user_id, event_id, cancelled_at=utc_now())
    if event is None:
        raise ApiError(404, "NOT_FOUND", "Không tìm thấy sự kiện.")
    return _event_out(event)


@router.get("/profiles/{cdpUserId}", response_model=schemas.Profile, tags=["profiles"])
def get_profile(cdp_user_id: CdpUserId, repository: Repository):
    profile = repository.get_profile(cdp_user_id)
    if profile is None:
        raise ApiError(404, "NOT_FOUND", "Không tìm thấy hồ sơ khách hàng.")
    return _profile_out(profile)


@router.put("/profiles/{cdpUserId}", response_model=schemas.Profile, tags=["profiles"])
def upsert_profile(cdp_user_id: CdpUserId, body: schemas.ProfileAttributes, repository: Repository):
    attributes = ProfileAttributes(**body.model_dump(exclude={"purchased_verticals"}),
                                   purchased_verticals=tuple(body.purchased_verticals))
    return _profile_out(repository.upsert_profile(cdp_user_id, attributes, updated_at=utc_now()))


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    # Naive query values are read as UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _event_out(event: UserEvent) -> schemas.UserEvent:
    return schemas.UserEvent(**event.__dict__)


def _profile_out(profile: Profile) -> schemas.Profile:
    attributes = profile.attributes.__dict__ | {"purchased_verticals": list(profile.attributes.purchased_verticals)}
    return schemas.Profile(
        cdp_user_id=profile.cdp_user_id,
        attributes=schemas.ProfileAttributes(**attributes),
        updated_at=profile.updated_at,
    )

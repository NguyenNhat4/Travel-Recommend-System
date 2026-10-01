"""DTO request khớp src/shared/contracts/schemas/booking.yaml. Response là dict đã dựng theo contract ở application/booking/views.py.

Cố ý KHÔNG đặt giới hạn giá trị (min, max, độ dài tên) ở đây: sai kiểu dữ liệu thì Pydantic trả `422`, còn vi phạm luật
nghiệp vụ phải đi qua bộ luật `domain/booking/party_rules.py` để Backend trả **mọi** vi phạm trong một lần với `400
VALIDATION_ERROR` và `details.fields[]` (spec checkout-nhieu-buoc-hanh-khach.md §5.1, §8.3). Các giới hạn dưới đây chỉ chặn
payload quá lớn.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class GuestCountsBody(BaseModel):
    adults: int = Field(ge=0, le=99)
    children: int = Field(ge=0, le=99)


class AddCartItemRequest(BaseModel):
    productId: str = Field(min_length=1, max_length=64)
    usingDate: date
    # Không gửi guests thì bắt buộc có quantity; dịch vụ tính theo người gửi guests được phép bỏ quantity (R-CRT-02).
    quantity: int | None = Field(default=None, ge=1, le=99)
    nights: int | None = Field(default=None, ge=1, le=60)
    guests: GuestCountsBody | None = None


class UpdateCartItemRequest(BaseModel):
    usingDate: date | None = None
    quantity: int | None = Field(default=None, ge=1, le=99)
    nights: int | None = Field(default=None, ge=1, le=60)
    guests: GuestCountsBody | None = None

    def has_changes(self) -> bool:
        return bool(self.model_fields_set & {"usingDate", "quantity", "nights", "guests"})


class ContactBody(BaseModel):
    fullName: str = Field(max_length=500)
    email: str = Field(max_length=500)
    phone: str = Field(max_length=50)


class TravelerDocumentsBody(BaseModel):
    """FR-BKG-13. Giá trị kiểu chuỗi để giá trị sai đi qua bộ luật và nhận lỗi theo trường thay vì `422`."""

    title: str | None = Field(default=None, max_length=16)
    nationality: str | None = Field(default=None, max_length=16)
    docType: str | None = Field(default=None, max_length=16)
    docNumber: str | None = Field(default=None, max_length=40)
    docExpiry: str | None = Field(default=None, max_length=32)
    escortTravelerRef: str | None = Field(default=None, max_length=64)


class CheckoutTravelerBody(BaseModel):
    travelerRef: str = Field(pattern=r"^[A-Za-z0-9_-]{1,36}$")
    type: Literal["ADULT", "CHILD"]
    surname: str = Field(max_length=200)
    givenNames: str = Field(max_length=200)
    birthDate: str | None = Field(default=None, max_length=32)
    documents: TravelerDocumentsBody | None = None


class CheckoutRoomBody(BaseModel):
    travelerRefs: list[str] = Field(default_factory=list, max_length=50)
    leadTravelerRef: str | None = Field(default=None, max_length=64)


class CheckoutItemDetailBody(BaseModel):
    cartItemId: str = Field(min_length=1, max_length=64)
    guestNames: list[str] = Field(default_factory=list, max_length=20)
    specialRequest: str | None = Field(default=None, max_length=500)
    travelerRefs: list[str] | None = Field(default=None, max_length=50)
    rooms: list[CheckoutRoomBody] | None = Field(default=None, max_length=20)


class CheckoutRequestBody(BaseModel):
    contact: ContactBody
    # Có `travelers` thì áp luật đoàn khách mới; không có thì theo quy tắc tên cũ, nay được kiểm thật (spec §7.6).
    travelers: list[CheckoutTravelerBody] | None = Field(default=None, max_length=50)
    itemDetails: list[CheckoutItemDetailBody] = Field(default_factory=list, max_length=100)


class CancelBookingBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)

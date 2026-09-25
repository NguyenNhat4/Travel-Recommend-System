"""DTO request khớp src/shared/contracts/schemas/booking.yaml. Response là dict đã dựng theo contract ở application/booking/views.py."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class AddCartItemRequest(BaseModel):
    productId: str = Field(min_length=1, max_length=64)
    usingDate: date
    quantity: int = Field(ge=1, le=99)
    nights: int | None = Field(default=None, ge=1, le=60)


class UpdateCartItemRequest(BaseModel):
    usingDate: date | None = None
    quantity: int | None = Field(default=None, ge=1, le=99)
    nights: int | None = Field(default=None, ge=1, le=60)

    def has_changes(self) -> bool:
        return bool(self.model_fields_set & {"usingDate", "quantity", "nights"})


class ContactBody(BaseModel):
    fullName: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    phone: str = Field(pattern=r"^0[0-9]{9}$")


class CheckoutItemDetailBody(BaseModel):
    cartItemId: str = Field(min_length=1, max_length=64)
    guestNames: list[str] = Field(default_factory=list, max_length=20)
    specialRequest: str | None = Field(default=None, max_length=500)


class CheckoutRequestBody(BaseModel):
    contact: ContactBody
    itemDetails: list[CheckoutItemDetailBody] = Field(default_factory=list, max_length=100)


class CancelBookingBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)

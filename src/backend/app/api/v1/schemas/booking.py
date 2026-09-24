"""DTO request của giỏ và checkout, bám `schemas/booking.yaml`. Response là dict do use case dựng theo contract."""
from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

# Kiểm dạng tối thiểu như DTO auth; không kéo thêm email-validator.
Email = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)


class AddCartItemRequest(BaseModel):
    productId: str = Field(min_length=1, max_length=64)
    usingDate: date
    quantity: int = Field(ge=1)
    nights: int | None = Field(default=None, ge=1)


class UpdateCartItemRequest(BaseModel):
    usingDate: date | None = None
    quantity: int | None = Field(default=None, ge=1)
    nights: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("cần ít nhất một trường")  # contract: minProperties 1
        return self


class Contact(BaseModel):
    fullName: str = Field(min_length=1, max_length=100)
    email: str = Email
    phone: str = Field(pattern=r"^0[0-9]{9}$")


class CheckoutItemDetail(BaseModel):
    cartItemId: str = Field(min_length=1)
    guestNames: list[Annotated[str, Field(min_length=1)]] = Field(default_factory=list)
    specialRequest: str | None = Field(default=None, max_length=500)


class CheckoutRequest(BaseModel):
    contact: Contact
    itemDetails: list[CheckoutItemDetail]

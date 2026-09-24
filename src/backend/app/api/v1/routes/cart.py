"""Giỏ hàng phía server, bắt buộc đăng nhập (backend §7.1). Danh tính chỉ lấy từ JWT đã kiểm."""
from typing import Any

from fastapi import APIRouter, Depends

from src.backend.app.api.deps import current_principal, get_cart_service
from src.backend.app.api.v1.schemas.booking import AddCartItemRequest, UpdateCartItemRequest
from src.backend.app.application.auth.principal import AuthPrincipal

router = APIRouter(tags=["booking"])


@router.get("/cart")
async def get_cart(principal: AuthPrincipal = Depends(current_principal), cart: Any = Depends(get_cart_service)):
    return await cart.get(principal.cdp_user_id)


@router.post("/cart/items")
async def add_cart_item(body: AddCartItemRequest, principal: AuthPrincipal = Depends(current_principal),
                        cart: Any = Depends(get_cart_service)):
    return await cart.add(principal.cdp_user_id, body.productId, body.usingDate, body.quantity, body.nights)


@router.patch("/cart/items/{cart_item_id}")
async def update_cart_item(cart_item_id: str, body: UpdateCartItemRequest,
                           principal: AuthPrincipal = Depends(current_principal),
                           cart: Any = Depends(get_cart_service)):
    return await cart.update(principal.cdp_user_id, cart_item_id, using_date=body.usingDate,
                             quantity=body.quantity, nights=body.nights)


@router.delete("/cart/items/{cart_item_id}")
async def remove_cart_item(cart_item_id: str, principal: AuthPrincipal = Depends(current_principal),
                           cart: Any = Depends(get_cart_service)):
    return await cart.remove(principal.cdp_user_id, cart_item_id)

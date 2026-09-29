from typing import Any

from fastapi import APIRouter, Depends

from src.backend.app.api.deps import get_index, get_use_case
from src.backend.app.application.catalog.views import destination_list
from src.backend.app.core.request_context import current_request_id

router = APIRouter(tags=["catalog"])


@router.get("/destinations")
def destinations(index: Any = Depends(get_index)):
    if index is None:
        return {"destinations": []}
    return destination_list(index.destination)


# Giới hạn limit/offset/sort/taxonomy do use case kiểm để trả 400 VALIDATION_ERROR đúng contract.
@router.get("/products")
async def list_products(destination: str | None = None, taxonomy: str | None = None, availableOnly: bool = False,
                        sort: str = "popular", limit: int = 20, offset: int = 0,
                        parentProductId: str | None = None, use_case=Depends(get_use_case("list_products"))):
    result = await use_case(destination=destination, taxonomy=taxonomy, available_only=availableOnly, sort=sort,
                            limit=limit, offset=offset, parent_product_id=parentProductId)
    return {**result, "requestId": current_request_id() or "catalog"}


@router.get("/products/{product_id}")
async def get_product(product_id: str, use_case=Depends(get_use_case("get_product_detail"))):
    return await use_case(product_id)


@router.get("/products/{product_id}/similar")
async def similar_products(product_id: str, limit: int = 8,
                           use_case=Depends(get_use_case("get_similar_products"))):
    return {**await use_case(product_id, limit=limit), "requestId": current_request_id() or "similar"}

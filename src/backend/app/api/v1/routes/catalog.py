from typing import Any

from fastapi import APIRouter, Depends, Response

from src.backend.app.api.deps import get_index, get_use_case
from src.backend.app.application.catalog.views import destination_list
from src.backend.app.core.request_context import current_request_id

router = APIRouter(tags=["catalog"])

# Catalog công khai, không đọc người dùng: giống nhau cho mọi người nên cache chung được.
PUBLIC_CATALOG_CACHE = "public, max-age=60, s-maxage=300"


@router.get("/destinations")
def destinations(index: Any = Depends(get_index)):
    if index is None:
        return {"destinations": []}
    return destination_list(index.destination)


# Giới hạn limit/offset/sort/taxonomy/diversify do use case kiểm để trả 400 VALIDATION_ERROR đúng contract (kiểu str ở
# đây, không Literal: FastAPI sẽ trả 422, contract không khai). `taxonomy` nhiều giá trị cách nhau bằng dấu phẩy
# (style form, explode false; contract 1.27.0).
# Header chỉ gắn sau khi use case thành công, nên response lỗi (400, 404, 409, 503) không bị cache.
@router.get("/products")
async def list_products(response: Response, destination: str | None = None, taxonomy: str | None = None,
                        availableOnly: bool = False, sort: str = "popular", limit: int = 20, offset: int = 0,
                        parentProductId: str | None = None, diversify: str | None = None,
                        use_case=Depends(get_use_case("list_products"))):
    taxonomies = taxonomy.split(",") if taxonomy is not None else None
    result = await use_case(destination=destination, taxonomy=taxonomies, available_only=availableOnly, sort=sort,
                            limit=limit, offset=offset, parent_product_id=parentProductId, diversify=diversify)
    response.headers["Cache-Control"] = PUBLIC_CATALOG_CACHE
    return {**result, "requestId": current_request_id() or "catalog"}


@router.get("/products/{product_id}")
async def get_product(product_id: str, response: Response, use_case=Depends(get_use_case("get_product_detail"))):
    result = await use_case(product_id)
    response.headers["Cache-Control"] = PUBLIC_CATALOG_CACHE
    return result


@router.get("/products/{product_id}/similar")
async def similar_products(product_id: str, response: Response, limit: int = 8,
                           use_case=Depends(get_use_case("get_similar_products"))):
    result = await use_case(product_id, limit=limit)
    response.headers["Cache-Control"] = PUBLIC_CATALOG_CACHE
    return {**result, "requestId": current_request_id() or "similar"}

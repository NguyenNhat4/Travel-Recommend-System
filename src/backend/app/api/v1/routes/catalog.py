from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends

from src.backend.app.api.deps import get_index, get_product_detail

router = APIRouter(tags=["catalog"])


@router.get("/destinations")
def destinations(index: Any = Depends(get_index)):
    if index is None:
        return {"destinations": []}
    counts = Counter(str(value) for value in index.destination)
    return {"destinations": [{"destination": name, "productCount": count}
                             for name, count in sorted(counts.items())]}


@router.get("/products/{product_id}")
async def product_detail(product_id: str, detail: Any = Depends(get_product_detail)):
    """ProductDetail kèm `variants[]` để chọn hạng phòng/chuyến bay; không ghi `product_view` (backend §4.2)."""
    return await detail(product_id)

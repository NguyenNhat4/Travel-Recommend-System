from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends

from src.backend.app.api.deps import get_index

router = APIRouter(tags=["catalog"])


@router.get("/destinations")
def destinations(index: Any = Depends(get_index)):
    if index is None:
        return {"destinations": []}
    counts = Counter(str(value) for value in index.destination)
    return {"destinations": [{"destination": name, "productCount": count}
                             for name, count in sorted(counts.items())]}

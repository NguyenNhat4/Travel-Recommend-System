from collections import Counter

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get("/destinations")
def destinations(request: Request):
    index = getattr(request.app.state, "index", None)
    if index is None:
        return {"destinations": []}
    counts = Counter(str(value) for value in index.destination)
    return {"destinations": [{"destination": name, "productCount": count}
                             for name, count in sorted(counts.items())]}

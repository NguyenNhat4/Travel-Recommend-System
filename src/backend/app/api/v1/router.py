"""Router v1 duy nhất; `main.py` gắn nó dưới prefix /api/v1. Route con không tự khai prefix."""
from fastapi import APIRouter

from src.backend.app.api.v1.routes.assistant import router as assistant_router
from src.backend.app.api.v1.routes.auth import router as auth_router
from src.backend.app.api.v1.routes.auth import well_known_router
from src.backend.app.api.v1.routes.recommendations import router as recommendations_router
from src.backend.app.api.v1.routes.search import router as search_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(assistant_router)
api_router.include_router(search_router)
api_router.include_router(recommendations_router)

# Ngoài prefix /api/v1: main.py gắn thẳng vào app.
root_router = APIRouter()
root_router.include_router(well_known_router)

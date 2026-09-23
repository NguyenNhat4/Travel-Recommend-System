"""Router v1 duy nhất; `main.py` gắn nó dưới prefix /api/v1. Route con không tự khai prefix."""
from fastapi import APIRouter

from src.backend.app.api.v1.routes.assistant import router as assistant_router
from src.backend.app.api.v1.routes.recommendations import router as recommendations_router
from src.backend.app.api.v1.routes.search import router as search_router

api_router = APIRouter()
api_router.include_router(assistant_router)
api_router.include_router(search_router)
api_router.include_router(recommendations_router)

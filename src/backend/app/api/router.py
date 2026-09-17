from fastapi import APIRouter

from src.backend.app.api.v1.routes.assistant import router as assistant_router

api_router = APIRouter()
api_router.include_router(assistant_router)

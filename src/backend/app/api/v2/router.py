"""Independent assistant-v2 router, mounted under /api/v2 by the composition root."""
from fastapi import APIRouter

from .routes.assistant import router as assistant_router

api_router=APIRouter()
api_router.include_router(assistant_router)

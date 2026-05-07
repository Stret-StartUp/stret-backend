from fastapi import APIRouter

from app.api.v1.endpoints import history, profile, query, upload

api_router = APIRouter()

api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(query.router, tags=["query"])
api_router.include_router(profile.router, tags=["profile"])
api_router.include_router(history.router, tags=["history"])

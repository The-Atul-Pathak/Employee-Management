from __future__ import annotations
from fastapi import APIRouter

from app.api.v1.endpoints import auth, platform, roles, users

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(platform.router, prefix="/platform", tags=["platform"])
api_router.include_router(roles.features_router, prefix="/features", tags=["features"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(users.router, prefix="/users", tags=["users"])

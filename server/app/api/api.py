"""Aggregate all API routers."""
from fastapi import APIRouter

from app.api.routers import (
    aircraft,
    auth,
    dashboard,
    missions,
    reports,
    tiles,
    users,
    weather,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(missions.router)
api_router.include_router(reports.router)
api_router.include_router(weather.router)
api_router.include_router(aircraft.router)
api_router.include_router(tiles.router)

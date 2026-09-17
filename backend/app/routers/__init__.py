from fastapi import APIRouter

from app.routers import accounts, billing, dashboard, demand_caps, history, readings, settings, tiers

api = APIRouter(prefix="/api")
api.include_router(dashboard.router)
api.include_router(accounts.router)
api.include_router(demand_caps.router)
api.include_router(tiers.router)
api.include_router(readings.router)
api.include_router(billing.router)
api.include_router(history.router)
api.include_router(settings.router)

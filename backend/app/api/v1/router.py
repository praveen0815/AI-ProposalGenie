"""Aggregates version 1 routes."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, companies, health, knowledge

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])

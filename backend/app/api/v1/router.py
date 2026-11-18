"""Aggregates version 1 routes."""

from fastapi import APIRouter

from app.api.v1.endpoints import agents, auth, companies, health, knowledge, proposals, rag

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(proposals.router, prefix="/proposals", tags=["proposals"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])

"""Centralized error responses."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.exceptions import register_exception_handlers


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    class Item(BaseModel):
        name: str

    @app.post("/items")
    def create_item(item: Item) -> Item:
        return item

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("postgres password leaked-token")

    return app


def test_validation_error_uses_stable_envelope() -> None:
    with TestClient(_app()) as client:
        response = client.post("/items", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["message"] == "Request validation failed"
    assert isinstance(body["details"], list)
    assert body["details"][0]["loc"][-1] == "name"


def test_unhandled_error_hides_exception_text() -> None:
    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal_error"
    assert body["message"] == "An unexpected error occurred"
    assert "leaked-token" not in response.text

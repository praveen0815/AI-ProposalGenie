"""Health, readiness, and API contract tests."""

from datetime import datetime

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.schemas.health import DependencyCheck
from app.services.health import collect_health


def test_liveness(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_method_not_allowed_uses_error_envelope(client: TestClient) -> None:
    response = client.post("/health")

    assert response.status_code == 405
    body = response.json()
    assert body["error"] == "method_not_allowed"
    assert "message" in body
    assert response.headers["content-type"].startswith("application/json")


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/missing")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_cors_allows_frontend_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_openapi_lists_health_paths_without_secrets(client: TestClient) -> None:
    response = client.get("/openapi.json")
    settings = get_settings()

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/api/v1/health" in paths
    assert "/api/v1/ready" in paths
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/companies" in paths
    assert "/api/v1/knowledge/documents/upload" in paths
    assert settings.postgres_password not in response.text
    assert settings.redis_password not in response.text
    assert settings.jwt_secret not in response.text


def test_collect_health_is_degraded_when_a_dependency_is_down(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.health.check_postgres",
        lambda: DependencyCheck(name="postgresql", status="down", detail="OperationalError"),
    )
    monkeypatch.setattr(
        "app.services.health.check_redis",
        lambda: DependencyCheck(name="redis", status="up", latency_ms=1.25),
    )

    report = collect_health()

    assert report.status == "degraded"
    assert [check.name for check in report.checks] == ["postgresql", "redis"]


def test_dependency_health_reports_live_services(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    settings = get_settings()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == settings.app_name
    assert body["version"] == settings.app_version
    assert body["environment"] == settings.environment
    datetime.fromisoformat(body["checked_at"])
    checks = {item["name"]: item for item in body["checks"]}
    assert set(checks) == {"postgresql", "redis"}
    for check in checks.values():
        assert check["status"] == "up"
        assert check["latency_ms"] >= 0
        assert check["detail"] is None
    assert settings.postgres_password not in response.text
    assert settings.redis_password not in response.text


def test_readiness_is_ok_when_dependencies_are_up(client: TestClient) -> None:
    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

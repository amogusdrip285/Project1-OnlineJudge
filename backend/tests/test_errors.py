"""Every non-2xx response uses the envelope {"error": {"code", "message"}} (MASTER_PLAN 6.1)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import AppError


@pytest.fixture
def app_with_test_routes(app: FastAPI) -> FastAPI:
    @app.get("/api/_test/items/{item_id}")
    def get_item(item_id: int) -> dict:
        return {"id": item_id}

    @app.get("/api/_test/app-error")
    def raise_app_error() -> None:
        raise AppError(409, "CONFLICT", "Username already exists")

    @app.get("/api/_test/crash")
    def crash() -> None:
        raise RuntimeError("secret internal detail")

    return app


@pytest.fixture
def test_client(app_with_test_routes: FastAPI) -> TestClient:
    return TestClient(app_with_test_routes, raise_server_exceptions=False)


def test_unknown_route_returns_not_found_envelope(test_client: TestClient) -> None:
    response = test_client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["message"]


def test_validation_error_returns_400_envelope(test_client: TestClient) -> None:
    response = test_client.get("/api/_test/items/not-a-number")

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "item_id" in body["error"]["message"]


def test_app_error_uses_its_status_and_code(test_client: TestClient) -> None:
    response = test_client.get("/api/_test/app-error")

    assert response.status_code == 409
    assert response.json() == {"error": {"code": "CONFLICT", "message": "Username already exists"}}


def test_unhandled_exception_returns_500_without_leaking_details(
    test_client: TestClient,
) -> None:
    response = test_client.get("/api/_test/crash")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in response.text


def test_wrong_method_returns_envelope(test_client: TestClient) -> None:
    response = test_client.post("/api/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"

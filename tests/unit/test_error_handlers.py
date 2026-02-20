"""Unit tests for shared API error envelope handlers."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import APIError
from app.core.errors import NotFoundError
from app.core.errors import register_error_handlers
from app.schemas.error import ErrorDetail


def _build_client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/query")
    def query(limit: int) -> dict[str, int]:
        return {"limit": limit}

    @app.get("/not-found")
    def not_found() -> None:
        raise NotFoundError(message="Pipeline not found")

    @app.get("/domain")
    def domain_error() -> None:
        raise APIError(
            status_code=400,
            code="validation_error",
            message="Invalid run payload",
            details=[ErrorDetail(field="status", issue="Unsupported value")],
        )

    @app.get("/http")
    def http_error() -> None:
        raise StarletteHTTPException(status_code=404, detail="Client not found")

    return TestClient(app)


def test_request_validation_errors_are_normalized_to_envelope() -> None:
    client = _build_client()

    response = client.get("/query")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["message"] == "Request validation failed"
    assert payload["error"]["details"][0]["field"] == "limit"


def test_domain_errors_use_shared_envelope() -> None:
    client = _build_client()

    response = client.get("/domain")

    assert response.status_code == 400
    payload = response.json()
    assert payload == {
        "error": {
            "code": "validation_error",
            "message": "Invalid run payload",
            "details": [{"field": "status", "issue": "Unsupported value"}],
        }
    }


def test_not_found_errors_use_shared_envelope() -> None:
    client = _build_client()

    response = client.get("/not-found")

    assert response.status_code == 404
    payload = response.json()
    assert payload == {
        "error": {
            "code": "not_found",
            "message": "Pipeline not found",
        }
    }


def test_http_errors_are_wrapped_in_shared_envelope() -> None:
    client = _build_client()

    response = client.get("/http")

    assert response.status_code == 404
    payload = response.json()
    assert payload == {
        "error": {
            "code": "not_found",
            "message": "Client not found",
        }
    }

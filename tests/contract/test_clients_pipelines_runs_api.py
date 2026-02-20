"""Contract tests for clients, pipelines, and runs API endpoints."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
import uuid

from fastapi.testclient import TestClient

API_PREFIX = "/api/v1"


def _assert_uuid(value: str) -> None:
    uuid.UUID(value)


def _assert_datetime(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.tzinfo.utcoffset(parsed) == timezone.utc.utcoffset(parsed)


def _assert_error_envelope(payload: dict) -> None:
    assert "error" in payload
    error = payload["error"]
    assert isinstance(error, dict)
    assert isinstance(error.get("code"), str) and error["code"]
    assert isinstance(error.get("message"), str) and error["message"]

    if "details" in error:
        assert isinstance(error["details"], list)
        for item in error["details"]:
            assert isinstance(item, dict)
            assert isinstance(item.get("field"), str)
            assert isinstance(item.get("issue"), str)


def _assert_client_contract(payload: dict) -> None:
    for field in ("id", "name", "is_active", "created_at", "updated_at"):
        assert field in payload

    _assert_uuid(payload["id"])
    assert isinstance(payload["name"], str)
    assert isinstance(payload["is_active"], bool)
    _assert_datetime(payload["created_at"])
    _assert_datetime(payload["updated_at"])


def _assert_pipeline_contract(payload: dict) -> None:
    for field in (
        "id",
        "client_id",
        "name",
        "platform",
        "pipeline_type",
        "is_active",
        "created_at",
        "updated_at",
    ):
        assert field in payload

    _assert_uuid(payload["id"])
    _assert_uuid(payload["client_id"])
    assert isinstance(payload["name"], str)
    assert isinstance(payload["platform"], str)
    assert isinstance(payload["pipeline_type"], str)
    assert isinstance(payload["is_active"], bool)
    _assert_datetime(payload["created_at"])
    _assert_datetime(payload["updated_at"])


def _assert_run_contract(payload: dict) -> None:
    for field in (
        "id",
        "pipeline_id",
        "external_run_id",
        "status",
        "ingested_at",
        "created_at",
        "updated_at",
    ):
        assert field in payload

    _assert_uuid(payload["id"])
    _assert_uuid(payload["pipeline_id"])
    assert isinstance(payload["external_run_id"], str)
    assert isinstance(payload["status"], str)
    _assert_datetime(payload["ingested_at"])
    _assert_datetime(payload["created_at"])
    _assert_datetime(payload["updated_at"])


def _create_client(test_client: TestClient, name: str = "acme") -> dict:
    response = test_client.post(f"{API_PREFIX}/clients", json={"name": name})
    assert response.status_code == 201
    payload = response.json()
    _assert_client_contract(payload)
    return payload


def _create_pipeline(test_client: TestClient, client_id: str, name: str = "orders") -> dict:
    response = test_client.post(
        f"{API_PREFIX}/clients/{client_id}/pipelines",
        json={
            "name": name,
            "platform": "airflow",
            "pipeline_type": "ingestion",
            "environment": "prod",
            "external_id": f"ext-{name}",
            "description": "Pipeline contract test",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    _assert_pipeline_contract(payload)
    return payload


def test_clients_crud_contract(client: TestClient) -> None:
    created = _create_client(client, name="acme-us")
    client_id = created["id"]

    response = client.get(f"{API_PREFIX}/clients")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)
    assert any(item["id"] == client_id for item in payload["items"])

    response = client.get(f"{API_PREFIX}/clients/{client_id}")
    assert response.status_code == 200
    retrieved = response.json()
    _assert_client_contract(retrieved)
    assert retrieved["id"] == client_id

    response = client.patch(
        f"{API_PREFIX}/clients/{client_id}",
        json={"name": "acme-us-renamed", "is_active": False},
    )
    assert response.status_code == 200
    updated = response.json()
    _assert_client_contract(updated)
    assert updated["name"] == "acme-us-renamed"
    assert updated["is_active"] is False

    response = client.delete(f"{API_PREFIX}/clients/{client_id}")
    assert response.status_code == 204

    response = client.get(f"{API_PREFIX}/clients/{client_id}")
    assert response.status_code == 200
    disabled = response.json()
    _assert_client_contract(disabled)
    assert disabled["is_active"] is False


def test_pipelines_crud_contract(client: TestClient) -> None:
    created_client = _create_client(client, name="acme-pipeline")
    client_id = created_client["id"]

    created_pipeline = _create_pipeline(client, client_id=client_id, name="daily-health")
    pipeline_id = created_pipeline["id"]

    response = client.get(f"{API_PREFIX}/clients/{client_id}/pipelines")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)
    assert any(item["id"] == pipeline_id for item in payload["items"])

    response = client.get(f"{API_PREFIX}/pipelines/{pipeline_id}")
    assert response.status_code == 200
    retrieved = response.json()
    _assert_pipeline_contract(retrieved)
    assert retrieved["client_id"] == client_id

    response = client.patch(
        f"{API_PREFIX}/pipelines/{pipeline_id}",
        json={
            "description": "Updated description",
            "is_active": False,
        },
    )
    assert response.status_code == 200
    updated = response.json()
    _assert_pipeline_contract(updated)
    assert updated["description"] == "Updated description"
    assert updated["is_active"] is False


def test_runs_create_list_and_latest_contract(client: TestClient) -> None:
    created_client = _create_client(client, name="acme-runs")
    created_pipeline = _create_pipeline(
        client,
        client_id=created_client["id"],
        name="hourly-ingestion",
    )
    pipeline_id = created_pipeline["id"]

    response = client.post(
        f"{API_PREFIX}/pipelines/{pipeline_id}/runs",
        json={
            "status": "running",
            "started_at": "2026-02-20T12:00:00Z",
            "payload": {"source": "manual"},
        },
    )
    assert response.status_code == 201
    created_run = response.json()
    _assert_run_contract(created_run)
    assert created_run["pipeline_id"] == pipeline_id
    assert created_run["status"] == "running"

    response = client.get(f"{API_PREFIX}/pipelines/{pipeline_id}/runs")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)
    assert any(item["id"] == created_run["id"] for item in payload["items"])

    response = client.get(f"{API_PREFIX}/pipelines/{pipeline_id}/runs/latest")
    assert response.status_code == 200
    latest = response.json()
    _assert_run_contract(latest)
    assert latest["id"] == created_run["id"]


def test_clients_validation_error_contract(client: TestClient) -> None:
    response = client.post(f"{API_PREFIX}/clients", json={})
    assert response.status_code == 400
    _assert_error_envelope(response.json())


def test_pipeline_not_found_error_contract(client: TestClient) -> None:
    missing_client_id = str(uuid.uuid4())
    response = client.post(
        f"{API_PREFIX}/clients/{missing_client_id}/pipelines",
        json={
            "name": "missing-parent",
            "platform": "airflow",
            "pipeline_type": "ingestion",
        },
    )
    assert response.status_code == 404
    _assert_error_envelope(response.json())


def test_runs_validation_error_contract(client: TestClient) -> None:
    created_client = _create_client(client, name="acme-run-errors")
    created_pipeline = _create_pipeline(
        client,
        client_id=created_client["id"],
        name="invalid-run-status",
    )

    response = client.post(
        f"{API_PREFIX}/pipelines/{created_pipeline['id']}/runs",
        json={"status": "unknown_status"},
    )
    assert response.status_code == 400
    _assert_error_envelope(response.json())

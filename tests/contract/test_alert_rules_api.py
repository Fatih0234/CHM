"""Contract tests for alert-rule API endpoints."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
import uuid

from fastapi.testclient import TestClient

API_PREFIX = "/api/v1"


def _assert_uuid(value: str | None) -> None:
    assert isinstance(value, str)
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


def _assert_alert_rule_contract(payload: dict) -> None:
    for field in (
        "id",
        "client_id",
        "pipeline_id",
        "rule_type",
        "threshold",
        "window_minutes",
        "channel",
        "destination",
        "is_enabled",
        "created_at",
        "updated_at",
    ):
        assert field in payload

    _assert_uuid(payload["id"])
    if payload["client_id"] is not None:
        _assert_uuid(payload["client_id"])
    if payload["pipeline_id"] is not None:
        _assert_uuid(payload["pipeline_id"])
    assert isinstance(payload["rule_type"], str)
    assert payload["threshold"] is None or isinstance(payload["threshold"], int)
    assert payload["window_minutes"] is None or isinstance(payload["window_minutes"], int)
    assert isinstance(payload["channel"], str)
    assert isinstance(payload["destination"], str)
    assert isinstance(payload["is_enabled"], bool)
    _assert_datetime(payload["created_at"])
    _assert_datetime(payload["updated_at"])


def _create_client(test_client: TestClient, name: str) -> dict:
    unique_name = f"{name}-{uuid.uuid4().hex[:8]}"
    response = test_client.post(f"{API_PREFIX}/clients", json={"name": unique_name})
    assert response.status_code == 201
    return response.json()


def _create_pipeline(test_client: TestClient, client_id: str, name: str) -> dict:
    response = test_client.post(
        f"{API_PREFIX}/clients/{client_id}/pipelines",
        json={
            "name": name,
            "platform": "airflow",
            "pipeline_type": "ingestion",
            "environment": "prod",
            "external_id": f"ext-{name}",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_alert_rules_crud_contract(client: TestClient) -> None:
    account = _create_client(client, name="acme-alert-contract")
    pipeline = _create_pipeline(client, client_id=account["id"], name="alert-contract-pipe")

    response = client.post(
        f"{API_PREFIX}/alert_rules",
        json={
            "client_id": account["id"],
            "pipeline_id": pipeline["id"],
            "rule_type": "on_failure",
            "channel": "slack",
            "destination": "#alerts",
            "is_enabled": True,
        },
    )
    assert response.status_code == 201
    created = response.json()
    _assert_alert_rule_contract(created)
    rule_id = created["id"]

    response = client.get(f"{API_PREFIX}/alert_rules", params={"pipeline_id": pipeline["id"]})
    assert response.status_code == 200
    listed = response.json()
    assert "items" in listed
    assert isinstance(listed["items"], list)
    assert any(item["id"] == rule_id for item in listed["items"])
    for item in listed["items"]:
        _assert_alert_rule_contract(item)

    response = client.get(f"{API_PREFIX}/alert_rules/{rule_id}")
    assert response.status_code == 200
    retrieved = response.json()
    _assert_alert_rule_contract(retrieved)
    assert retrieved["id"] == rule_id

    response = client.patch(
        f"{API_PREFIX}/alert_rules/{rule_id}",
        json={
            "rule_type": "failures_in_window",
            "threshold": 2,
            "window_minutes": 60,
            "channel": "email",
            "destination": "oncall@example.com",
            "is_enabled": False,
        },
    )
    assert response.status_code == 200
    updated = response.json()
    _assert_alert_rule_contract(updated)
    assert updated["rule_type"] == "failures_in_window"
    assert updated["threshold"] == 2
    assert updated["window_minutes"] == 60
    assert updated["channel"] == "email"
    assert updated["destination"] == "oncall@example.com"
    assert updated["is_enabled"] is False

    response = client.delete(f"{API_PREFIX}/alert_rules/{rule_id}")
    assert response.status_code == 204

    response = client.get(f"{API_PREFIX}/alert_rules/{rule_id}")
    assert response.status_code == 404
    _assert_error_envelope(response.json())


def test_alert_rule_validation_contract_failures_in_window_requires_threshold_and_window(
    client: TestClient,
) -> None:
    account = _create_client(client, name="acme-alert-validation")
    response = client.post(
        f"{API_PREFIX}/alert_rules",
        json={
            "client_id": account["id"],
            "rule_type": "failures_in_window",
            "channel": "slack",
            "destination": "#alerts",
        },
    )
    assert response.status_code == 400
    _assert_error_envelope(response.json())


def test_alert_rule_validation_contract_on_failure_allows_empty_threshold_and_window(
    client: TestClient,
) -> None:
    account = _create_client(client, name="acme-alert-on-failure")
    response = client.post(
        f"{API_PREFIX}/alert_rules",
        json={
            "client_id": account["id"],
            "rule_type": "on_failure",
            "channel": "webhook",
            "destination": "https://hooks.example.com/chm",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    _assert_alert_rule_contract(payload)
    assert payload["threshold"] is None
    assert payload["window_minutes"] is None

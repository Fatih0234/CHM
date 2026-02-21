"""Integration tests for alert-rule scope precedence and lifecycle behavior."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

API_PREFIX = "/api/v1"


def _create_client(test_client: TestClient, name_prefix: str) -> dict:
    response = test_client.post(
        f"{API_PREFIX}/clients",
        json={"name": f"{name_prefix}-{uuid.uuid4().hex[:8]}"},
    )
    assert response.status_code == 201
    return response.json()


def _create_pipeline(test_client: TestClient, client_id: str, name_prefix: str) -> dict:
    unique = f"{name_prefix}-{uuid.uuid4().hex[:6]}"
    response = test_client.post(
        f"{API_PREFIX}/clients/{client_id}/pipelines",
        json={
            "name": unique,
            "platform": "airflow",
            "pipeline_type": "ingestion",
            "environment": "prod",
            "external_id": f"ext-{unique}",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_pipeline_scope_precedence_excludes_dual_scope_rule_from_client_only_filter(
    client: TestClient,
) -> None:
    client_a = _create_client(client, "scope-a")
    client_b = _create_client(client, "scope-b")
    pipeline_b = _create_pipeline(client, client_id=client_b["id"], name_prefix="pipeline-b")

    response = client.post(
        f"{API_PREFIX}/alert_rules",
        json={
            "client_id": client_a["id"],
            "pipeline_id": pipeline_b["id"],
            "rule_type": "on_failure",
            "channel": "slack",
            "destination": "#ops-alerts",
        },
    )
    assert response.status_code == 201
    rule_id = response.json()["id"]

    by_pipeline = client.get(f"{API_PREFIX}/alert_rules", params={"pipeline_id": pipeline_b["id"]})
    assert by_pipeline.status_code == 200
    pipeline_ids = {item["id"] for item in by_pipeline.json()["items"]}
    assert rule_id in pipeline_ids

    by_client_only = client.get(f"{API_PREFIX}/alert_rules", params={"client_id": client_a["id"]})
    assert by_client_only.status_code == 200
    client_ids = {item["id"] for item in by_client_only.json()["items"]}
    assert rule_id not in client_ids


def test_alert_rule_enable_disable_lifecycle_via_is_enabled_filter(client: TestClient) -> None:
    owner = _create_client(client, "lifecycle")

    response = client.post(
        f"{API_PREFIX}/alert_rules",
        json={
            "client_id": owner["id"],
            "rule_type": "on_failure",
            "channel": "email",
            "destination": "alerts@example.com",
        },
    )
    assert response.status_code == 201
    created = response.json()
    rule_id = created["id"]
    assert created["is_enabled"] is True

    disable_response = client.patch(f"{API_PREFIX}/alert_rules/{rule_id}", json={"is_enabled": False})
    assert disable_response.status_code == 200
    assert disable_response.json()["is_enabled"] is False

    enabled_list = client.get(f"{API_PREFIX}/alert_rules", params={"is_enabled": True})
    assert enabled_list.status_code == 200
    enabled_ids = {item["id"] for item in enabled_list.json()["items"]}
    assert rule_id not in enabled_ids

    disabled_list = client.get(f"{API_PREFIX}/alert_rules", params={"is_enabled": False})
    assert disabled_list.status_code == 200
    disabled_ids = {item["id"] for item in disabled_list.json()["items"]}
    assert rule_id in disabled_ids

    enable_response = client.patch(f"{API_PREFIX}/alert_rules/{rule_id}", json={"is_enabled": True})
    assert enable_response.status_code == 200
    assert enable_response.json()["is_enabled"] is True


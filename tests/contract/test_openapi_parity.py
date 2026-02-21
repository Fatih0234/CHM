"""OpenAPI parity checks against the feature contract for implemented endpoints."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re

from app.main import app

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
US1_CONTRACT_PATHS = {
    "/clients",
    "/clients/{client_id}",
    "/clients/{client_id}/pipelines",
    "/pipelines/{pipeline_id}",
    "/pipelines/{pipeline_id}/runs",
    "/pipelines/{pipeline_id}/runs/latest",
    "/clients/{client_id}/runs/summary",
}
API_PREFIX = "/api/v1"
CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "001-chm-api-ingestion"
    / "contracts"
    / "openapi.yaml"
)


def _parse_contract_paths() -> dict[str, dict[str, set[str]]]:
    contract_map: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    in_paths = False
    current_path: str | None = None
    current_method: str | None = None
    in_responses = False

    for raw_line in CONTRACT_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if stripped == "paths:":
            in_paths = True
            continue
        if in_paths and stripped == "components:":
            break
        if not in_paths:
            continue

        path_match = re.match(r"^(/[^:]+):$", stripped)
        if indent == 2 and path_match:
            current_path = path_match.group(1)
            current_method = None
            in_responses = False
            continue

        method_match = re.match(r"^(get|post|put|patch|delete):$", stripped)
        if indent == 4 and current_path and method_match:
            current_method = method_match.group(1)
            contract_map[current_path][current_method]
            in_responses = False
            continue

        if indent == 6 and stripped == "responses:" and current_path and current_method:
            in_responses = True
            continue

        if in_responses and indent == 8 and current_path and current_method:
            status_match = re.match(r"^'(\d{3})':$", stripped)
            if status_match:
                contract_map[current_path][current_method].add(status_match.group(1))
                continue

        if indent <= 6 and stripped != "responses:":
            in_responses = False

    return contract_map


def test_openapi_parity_for_us1_paths() -> None:
    contract_paths = _parse_contract_paths()
    generated = app.openapi()["paths"]

    for contract_path in sorted(US1_CONTRACT_PATHS):
        assert contract_path in contract_paths, f"Missing contract path: {contract_path}"
        generated_path = f"{API_PREFIX}{contract_path}"
        assert generated_path in generated, f"Missing implemented path: {generated_path}"

        expected_methods = set(contract_paths[contract_path].keys()) & HTTP_METHODS
        actual_methods = set(generated[generated_path].keys()) & HTTP_METHODS
        assert expected_methods == actual_methods, (
            f"Method mismatch for {contract_path}: "
            f"expected {sorted(expected_methods)} got {sorted(actual_methods)}"
        )

        for method in expected_methods:
            expected_success = {
                code for code in contract_paths[contract_path][method] if code.startswith("2")
            }
            actual_codes = set(generated[generated_path][method].get("responses", {}).keys())
            assert expected_success <= actual_codes, (
                f"Success status mismatch for {contract_path} {method.upper()}: "
                f"expected {sorted(expected_success)} to be present in {sorted(actual_codes)}"
            )

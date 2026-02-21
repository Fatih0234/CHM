# Validation Report: 001-chm-api-ingestion

## Run Context

- Date (UTC): 2026-02-21 01:00:44 UTC
- Repository: `Fatih0234/CHM`
- Branch during validation: `codex/task/T037-validation-evidence`
- Environment: local `.venv` (`Python 3.11.14`, `pytest 8.4.2`)

## Commands Executed

| Command | Purpose | Outcome Evidence |
|---|---|---|
| `.venv/bin/pytest tests/integration/test_schema_constraints.py` | Validate schema hard-gate constraints (`T012`) | `3 passed in 0.30s` |
| `.venv/bin/pytest tests/contract/test_openapi_parity.py` | Validate OpenAPI parity gate (`T020`) | `1 passed in 0.03s` |
| `.venv/bin/pytest tests/integration/test_ingestion_idempotency.py` | Validate ingestion dedupe/idempotency behavior (`T027` dependency chain) | `2 passed in 0.31s` |
| `.venv/bin/pytest tests/integration/test_critical_path_gate.py` | Validate critical-path gate (`T030`) | `1 passed in 4.48s` |
| `.venv/bin/pytest tests/integration/test_dashboard_queries.py` | Validate dashboard SQL query outputs (`T033`) | `1 passed in 0.22s` |
| `.venv/bin/pytest` | End-to-end readiness sweep | `45 passed in 7.01s` |

## Quickstart Alignment

- Schema first checks: covered by schema constraints integration suite.
- API baseline and contract consistency: covered by contract tests and OpenAPI parity.
- Ingestion hard gate: covered by idempotency/progression integration tests in full suite.
- Test coverage gate: explicitly executed via `test_critical_path_gate.py`.
- Dashboard query shapes: explicitly executed via `test_dashboard_queries.py`.

## Result

- Status: **PASS**
- Acceptance command status: `pytest && test -f docs/validation/001-chm-api-ingestion.md` satisfied.

## Known Limitations

- Validation was executed in local test environment; it does not include partner API live-call verification.
- No performance/load benchmark was executed in this pass (only functional/correctness tests).
- Dockerized Postgres/Grafana/Metabase runtime smoke was not part of this run.

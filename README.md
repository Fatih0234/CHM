# CHM Core Inventory and Run Health

CHM is an internal monitoring backend for data engineering teams to track client pipelines, ingest run events idempotently, and provide dashboard-ready operational health views for business and governance reporting.

## User Need and Problem Statement

Data engineers need a reliable system to monitor customer data pipelines across clients, detect failures quickly, and review historical reliability trends. CHM provides a canonical data model, ingestion flow, and analytics outputs so teams can answer what is failing now, what changed recently, and which pipelines are unstable.

## Requirements Overview (Q1-Q10 Monitoring Goals)

- Q1-Q5 (Business Monitoring): visibility into failures over time, latest status by client/pipeline, and trend summaries that support stakeholder reporting.
- Q6-Q10 (Operations and Governance): operational triage views, flaky pipeline ranking, platform-level failure rates, and governance-friendly documented workflows.
- Hard constraints:
  - Exactly four domain entities in MVP (`clients`, `pipelines`, `runs`, `alert_rules`).
  - Idempotent ingestion keyed by `(pipeline_id, external_run_id)`.
  - Consistent, dashboard-ready query outputs for Grafana and Metabase.

## Data Model Summary

- `clients`: customer/account scope.
- `pipelines`: pipeline definitions owned by one client.
- `runs`: time-based run history events linked to pipelines.
- `alert_rules`: stored alert definitions scoped to client/pipeline.

Key relationships and invariants:

- `pipelines.client_id -> clients.id`
- `runs.pipeline_id -> pipelines.id`
- `alert_rules.client_id/pipeline_id` reference client/pipeline scope
- idempotent ingestion identity: unique `(pipeline_id, external_run_id)`

## Architecture and Stack

- API: FastAPI
- ORM/Migrations: SQLAlchemy 2.x + Alembic
- Validation: Pydantic v2
- Database: PostgreSQL 15
- Dashboards: Grafana + Metabase
- Language/runtime: Python 3.11

Project layout:

```text
app/           # API, services, db, ingestion, synthetic orchestrator
tests/         # unit, integration, contract tests
docker/        # postgres/grafana/metabase compose + provisioning
data/          # synthetic dataset artifacts
docs/          # workflow, validation, and prompt/playbook docs
```

## Local Run Instructions

### 1) Python Environment

```bash
cd /Volumes/T7/CHM
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2) Start Docker Stack

```bash
docker compose -f /Volumes/T7/CHM/docker/docker-compose.yml up -d
```

Notes:

- Postgres is exposed on host `55432` and runs internally on `5432`.
- Metabase app database is `metabase_app`.
- Grafana dashboards/datasources are provisioned from `docker/grafana/provisioning/`.

### 3) Migrations and Validation

```bash
cd /Volumes/T7/CHM
alembic upgrade head
ruff check .
pytest
docker compose -f /Volumes/T7/CHM/docker/docker-compose.yml config
```

## Synthetic Data Workflow

Synthetic dataset artifacts live under:

- `/Volumes/T7/CHM/data/synthetic/v1/base/`
- `/Volumes/T7/CHM/data/synthetic/v1/batches/`
- `/Volumes/T7/CHM/data/synthetic/v1/context/`

Orchestrator entrypoint:

```bash
chm-synthetic-orchestrator --state-file /Volumes/T7/CHM/data/synthetic/v1/context/session_state.json
```

Related workflow docs:

- `/Volumes/T7/CHM/docs/synthetic-data-playbook.md`
- `/Volumes/T7/CHM/docs/synthetic-orchestrator-prompt.md`
- `/Volumes/T7/CHM/docs/synthetic-subagent-prompts.md`

## Dashboard Evidence

Q1-Q5 Business Monitoring:

![CHM Q1-Q5 Business Monitoring](artifacts/CHM%20Q1-Q5%20Business%20Monitoring.png)

Q6-Q10 Operations & Governance:

![CHM Q6-Q10 Operations and Governance](artifacts/CHM%20Q6-Q10%20Operations%20%26%20Governance.png)

## Repository Collaboration Workflow

This repository follows issue-linked PR delivery:

- one issue per task
- branch from `main`, target PR base `main`
- include `Closes #<issue-number>` in PR body

Reference:

- `/Volumes/T7/CHM/docs/project-management/pr-workflow.md`

## Deliverables Checklist and Current Status

- [x] CHM schema-first backend with four core entities
- [x] Idempotent ingestion flow and tests
- [x] Dashboard query contracts and Grafana provisioning
- [x] Synthetic dataset pack (`v1`) with validation report
- [x] Dashboard screenshots captured in `artifacts/`
- [x] Final project documentation and workflow guidance

# Implementation Plan: CHM Core Inventory and Run Health

**Branch**: `001-chm-api-ingestion` | **Date**: 2026-02-20 | **Spec**: `/Volumes/T7/CHM/specs/001-chm-api-ingestion/spec.md`
**Input**: Feature specification from `/Volumes/T7/CHM/specs/001-chm-api-ingestion/spec.md`

## Summary

Deliver CHM MVP incrementally with schema-first execution and idempotent ingestion as hard
constraints. Phase delivery order is: core schema and constraints, baseline REST API,
external ingestion with upsert semantics, test hardening, and dashboard-ready query shapes
for Grafana and Metabase.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, requests  
**Storage**: PostgreSQL 15  
**Testing**: pytest, pytest-asyncio, httpx (API tests)  
**Target Platform**: Linux containerized service runtime  
**Project Type**: Backend API service  
**Performance Goals**: latest-run endpoint p95 <= 250ms; client summary endpoint p95 <= 500ms;
ingestion sustained >= 50 runs/sec for batched partner pages in non-prod load testing  
**Constraints**: hard schema boundary (`clients`, `pipelines`, `runs`, `alert_rules`),
idempotent ingestion by `(pipeline_id, external_run_id)`, UTC timestamps, consistent JSON
errors, no secret logging  
**Scale/Scope**: initial target 200 clients, 10,000 pipelines, up to 5 million runs/year

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Initial Gate Assessment (Pre-Phase 0)

- [x] Scope remains within `clients`, `pipelines`, `runs`, and `alert_rules`.
- [x] Ingestion design enforces idempotency with stable dedupe keys and upsert behavior.
- [x] Run history is preserved as events over time; no latest-status overwrite design.
- [x] API contracts define schemas, validation errors, filtering, and pagination.
- [x] Grafana time-series outputs and Metabase exploration outputs are identified.
- [x] Database integrity includes FKs, uniqueness constraints, status validation, and migration plan.
- [x] Test plan includes ingestion idempotency/mapping, summary endpoints, and CRUD smoke coverage.
- [x] Security/reproducibility includes least-privilege secret handling and local Postgres/Grafana/Metabase.

## Project Structure

### Documentation (this feature)

```text
/Volumes/T7/CHM/specs/001-chm-api-ingestion/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   └── dashboard-queries.sql
└── tasks.md
```

### Source Code (repository root)

```text
/Volumes/T7/CHM/
├── app/
│   ├── api/
│   │   ├── clients.py
│   │   ├── pipelines.py
│   │   ├── runs.py
│   │   └── alert_rules.py
│   ├── core/
│   │   ├── config.py
│   │   └── errors.py
│   ├── db/
│   │   ├── base.py
│   │   ├── models/
│   │   └── repository/
│   ├── ingestion/
│   │   ├── client.py
│   │   ├── mapper.py
│   │   └── job.py
│   ├── schemas/
│   └── services/
├── migrations/
├── tests/
│   ├── contract/
│   ├── integration/
│   └── unit/
└── docker/
```

**Structure Decision**: Single backend service with domain modules grouped by API,
persistence, ingestion, and services. This supports incremental rollout while preserving
clear boundaries for schema-first evolution and ingestion idempotency.

## Phase Plan

### Phase 0: Research and Decision Lock

- Produce `research.md` with decision records for ambiguous implementation choices.
- Lock non-negotiables: soft-disable semantics, latest-run ordering, alert scope precedence,
  idempotent run upsert behavior, and partner API retry/backoff strategy.

### Phase 1: Design and Contracts

- Produce `data-model.md` with table fields, constraints, relationships, and run state transitions.
- Produce API contract in `/Volumes/T7/CHM/specs/001-chm-api-ingestion/contracts/openapi.yaml`.
- Produce dashboard query contract in `/Volumes/T7/CHM/specs/001-chm-api-ingestion/contracts/dashboard-queries.sql`.
- Produce implementation quickstart in `quickstart.md` for local validation.

### Phase 2: Incremental Delivery Milestones

1. **Milestone A - Schema First (Hard Gate)**
   - Create four-table schema, FKs, enums/check constraints, unique keys, and migrations.
   - Ensure run dedupe constraint `(pipeline_id, external_run_id)` is enforced.
2. **Milestone B - API Baseline**
   - Implement CRUD and query endpoints for clients, pipelines, runs, and alert rules.
   - Implement latest-run and client-summary behavior with deterministic ordering/filtering.
3. **Milestone C - Ingestion Job (Idempotent Hard Gate)**
   - Implement partner run ingestion with pagination, timeout, retry/backoff, and status mapping.
   - Upsert run records without duplication and support status progression updates.
4. **Milestone D - Test Coverage Gate**
   - Add tests for ingestion idempotency/mapping correctness, summary/latest behavior,
     and CRUD smoke flows.
5. **Milestone E - Dashboard-Ready Query Shapes**
   - Deliver stable query shapes for failures over time, latest status by pipeline,
     failure counts by client, top flaky pipelines, and failure rate by platform.

## Post-Design Constitution Re-Check

- [x] Scope remains constrained to four entities; no extra domain tables introduced.
- [x] Idempotent ingestion contract and dedupe key captured in design + contracts.
- [x] Run event history and latest-run logic are explicit and testable.
- [x] API contract stability and consistent error envelope captured in OpenAPI.
- [x] Grafana/Metabase query shapes are formalized in `dashboard-queries.sql`.
- [x] Data integrity constraints are defined in data model design.
- [x] Test obligations for critical paths are explicit in quickstart validation.
- [x] Security and reproducible local setup requirements are documented.

## Complexity Tracking

No constitution violations identified; no complexity waiver required.

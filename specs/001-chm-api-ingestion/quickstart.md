# Quickstart: CHM Core Inventory and Run Health

## Purpose

Validate incremental delivery milestones for schema-first API and idempotent ingestion.

## Prerequisites

- Docker and Docker Compose available locally
- Python 3.11 environment
- PostgreSQL, Grafana, and Metabase container definitions available in project compose config

## Milestone Validation Flow

1. **Schema First**
   - Start Postgres container.
   - Run migrations to create `clients`, `pipelines`, `runs`, and `alert_rules`.
   - Verify constraints:
     - uniqueness on client name
     - uniqueness on `(client_id, pipeline name)`
     - uniqueness on `(pipeline_id, external_run_id)`
     - alert rule scope/rule-type checks

2. **API Baseline**
   - Start service locally.
   - Execute CRUD smoke tests for clients, pipelines, runs, and alert rules.
   - Verify run list filtering by status and time window.
   - Verify latest-run ordering logic and client summary output.

3. **Ingestion Job**
   - Configure partner API base URL and credentials through environment variables.
   - Run ingestion for pipelines with `external_id` values.
   - Re-run ingestion with identical source payload and confirm no duplicate runs.
   - Validate status progression updates on existing runs.

4. **Test Gate**
   - Run test suite sections:
     - ingestion idempotency and mapping correctness
     - latest-run + client-summary behaviors
     - CRUD smoke coverage
   - Confirm all critical-path tests pass.

5. **Dashboard Query Shapes**
   - Execute SQL in `contracts/dashboard-queries.sql` against seeded data.
   - Confirm outputs answer:
     - what is failing now
     - what changed since yesterday
     - latest status per pipeline/client
     - flaky pipelines over time

## Recommended Execution Order

1. Implement and validate schema + migrations.
2. Implement API endpoints and response/error contracts.
3. Implement ingestion client/mapping/upsert behavior.
4. Add integration and contract tests for hard constraints.
5. Validate dashboard query shapes with representative run history.

## Exit Criteria

- Hard constraints satisfied:
  - schema-first four-table model
  - idempotent ingestion on `(pipeline_id, external_run_id)`
- Functional criteria met:
  - CRUD and core query behavior verified
  - latest run and summary logic verified
  - dashboard-ready query shapes validated

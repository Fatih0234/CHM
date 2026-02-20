# Phase 0 Research: CHM Core Inventory and Run Health

## Decision 1: Deletion Strategy for Clients and Pipelines

- **Decision**: Use soft disable (`is_active=false`) as default behavior; hard delete is not
  part of MVP flows.
- **Rationale**: Preserves historical runs and trend analysis while reducing accidental data loss.
- **Alternatives considered**:
  - Hard delete with cascading cleanup: simpler storage management but breaks history analysis.
  - Hybrid delete by role: adds policy complexity without MVP value.

## Decision 2: Latest Run Ordering Rule

- **Decision**: Sort by `started_at DESC`, then `finished_at DESC`, then `id DESC`; null
  timestamps are sorted last.
- **Rationale**: Reflects operational recency while remaining deterministic even with partial
  timestamp data.
- **Alternatives considered**:
  - `finished_at` only: inaccurate for long-running active executions.
  - `created_at` only: can diverge from true external run timeline.

## Decision 3: Manual Run Identity Handling

- **Decision**: Manual run creation accepts client-provided `external_run_id`; if omitted,
  CHM generates a stable UUID-like identifier.
- **Rationale**: Supports ad-hoc/manual entries without compromising uniqueness constraints.
- **Alternatives considered**:
  - Always require caller-provided ID: increases operator friction.
  - Separate ID namespace by source: unnecessary complexity for MVP.

## Decision 4: Alert Rule Scope Resolution

- **Decision**: Allow client-scoped and pipeline-scoped rules; require at least one scope;
  if both exist, pipeline scope has precedence.
- **Rationale**: Matches feature requirements while preserving future evaluation semantics.
- **Alternatives considered**:
  - Pipeline-only rules: too restrictive for client-wide fallback policies.
  - Client-only rules: insufficient granularity for noisy pipelines.

## Decision 5: Idempotent Ingestion Write Pattern

- **Decision**: Use database upsert keyed by `(pipeline_id, external_run_id)` and update
  mutable run fields (`status`, timestamps, metrics, payload, `updated_at`, `ingested_at`).
- **Rationale**: Guarantees duplicate-safe replay and supports lifecycle transitions like
  running -> success.
- **Alternatives considered**:
  - Read-before-write dedupe in application code: race-prone under concurrency.
  - Append-only duplicate rows with reconciliation queries: violates idempotency requirement.

## Decision 6: Partner API Retry and Backoff Policy

- **Decision**: Apply connect/read timeouts, bounded retries for network/5xx errors,
  and exponential backoff with jitter for HTTP 429/5xx.
- **Rationale**: Improves ingestion resilience without creating unbounded retry storms.
- **Alternatives considered**:
  - No retries: fragile under transient outages.
  - Infinite retries: operationally unsafe and can block ingest cycles.

## Decision 7: Dashboard Query Shape Strategy

- **Decision**: Define stable SQL query shapes (or views) for time-series and aggregation
  outputs in `contracts/dashboard-queries.sql`.
- **Rationale**: Ensures Grafana and Metabase can consume consistent, reviewable contracts.
- **Alternatives considered**:
  - Build dashboard-specific API endpoints only: less reusable for BI exploration.
  - Ad-hoc dashboard queries per tool: high drift risk and poor governance.

## Decision 8: API Error Contract Consistency

- **Decision**: Use one JSON error envelope for validation and domain/business-rule errors,
  including a machine-readable code and field-level detail list.
- **Rationale**: Keeps client integration predictable and simplifies monitoring/debugging.
- **Alternatives considered**:
  - Endpoint-specific error formats: inconsistent and expensive to maintain.
  - Plain text errors: poor machine readability.

## Decision 9: Incremental Milestone Order

- **Decision**: Implement in this order: schema/migrations -> API baseline -> ingestion job
  -> test hardening -> dashboard query shapes.
- **Rationale**: Enforces schema-first and idempotent ingestion constraints while delivering
  usable value early.
- **Alternatives considered**:
  - Ingestion before schema hardening: high rework risk.
  - Dashboards before validated API/ingestion: unreliable operational outputs.

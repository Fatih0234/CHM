<!--
Sync Impact Report
- Version change: template (unversioned) -> 1.0.0
- Modified principles:
  - Template Principle 1 -> I. Schema-First, Scope-Controlled Domain
  - Template Principle 2 -> II. Idempotent, History-Preserving Ingestion
  - Template Principle 3 -> III. Observability-First Contracts
  - Template Principle 4 -> IV. Data Integrity, Security, and Reproducibility
  - Template Principle 5 -> V. Pragmatic Incremental Delivery
- Added sections:
  - Operational Constraints
  - Delivery Workflow & Quality Gates
- Removed sections:
  - None
- Templates requiring updates:
  - ✅ updated: .specify/templates/plan-template.md
  - ✅ updated: .specify/templates/spec-template.md
  - ✅ updated: .specify/templates/tasks-template.md
  - ⚠ pending: .specify/templates/commands/*.md (directory not present)
- Follow-up TODOs:
  - None
-->
# CHM Constitution

## Core Principles

### I. Schema-First, Scope-Controlled Domain
The canonical data model for CHM MUST remain limited to `clients`, `pipelines`,
`runs`, and `alert_rules`. New entities or major relationship changes MUST be
accepted only when they are required for ingestion, health summaries,
monitoring dashboards, BI exploration, or alerting. Database changes MUST
preserve foreign keys, uniqueness constraints, and explicit status validation.
Rationale: strict domain boundaries prevent scope creep and keep the service
operationally understandable.

### II. Idempotent, History-Preserving Ingestion
Ingestion MUST be idempotent. Reprocessing the same external run MUST NOT create
duplicate `runs` records; implementations MUST use stable dedupe keys and
upsert semantics (default key: `pipeline_id + external_run_id`). `runs` are
events over time and MUST be preserved as history, not collapsed into a single
latest-status overwrite. Rationale: reliable re-ingestion and complete run
history are required for trend analysis and incident debugging.

### III. Observability-First Contracts
The API MUST expose consistent JSON contracts with explicit validation errors,
predictable filtering, and predictable pagination for list endpoints.
Time-oriented query shapes MUST support Grafana dashboards, and exploration-
friendly tables/aggregations MUST support Metabase reporting. Timestamps MUST be
stored and served in UTC. Rationale: consistent contracts reduce client churn,
while observability-first data shapes accelerate operations and analysis.

### IV. Data Integrity, Security, and Reproducibility
Correctness and auditability take priority over convenience. Referential
integrity and meaningful constraints are mandatory. Minimum test coverage MUST
include ingestion idempotency and mapping correctness, summary endpoints (client
health and latest run), and CRUD smoke paths. Secrets and tokens MUST be
least-privilege, environment-scoped, and never logged. Local development MUST
be reproducible with containerized PostgreSQL, Grafana, and Metabase.
Rationale: these controls reduce production risk and keep developer onboarding
repeatable.

### V. Pragmatic Incremental Delivery
Engineering decisions MUST choose the simplest approach that satisfies the
active requirement set (80/20). Delivery MUST proceed incrementally in this
order unless a justified dependency requires change: baseline schema/API/
ingestion first, dashboards second, alerts execution later. Rationale:
incremental delivery reduces risk and preserves momentum without overdesign.

## Operational Constraints

- Service stack MUST remain FastAPI + PostgreSQL unless a constitution amendment
  is ratified.
- External pipeline/run ingestion MUST use clearly bounded adapters and
  deterministic field mapping.
- Database migrations MUST be explicit, reversible where practical, and reviewed
  for data integrity impacts.
- Monitoring and BI outputs MUST be defined as stable SQL queries or views that
  can be consumed by Grafana and Metabase.

## Delivery Workflow & Quality Gates

- Every spec/plan/tasks artifact MUST include a constitution compliance check
  before implementation starts.
- Every feature touching ingestion MUST include an idempotency test and a
  mapping correctness test before merge.
- Every feature touching summary endpoints MUST include automated coverage for
  client health and latest run behavior.
- Every change affecting setup MUST keep local container-based startup
  instructions current and verifiable.
- Pull requests MUST document scope impact, migration impact, test evidence, and
  security/secret handling decisions.

## Governance

This constitution overrides conflicting project conventions. Amendments require a
reviewed change in `.specify/memory/constitution.md`, explicit rationale,
propagation updates to dependent templates/docs, and a version bump justified by
semantic impact.

Versioning policy:
- MAJOR: backward-incompatible governance changes, principle removals, or
  principle redefinitions that invalidate prior plans.
- MINOR: new principles/sections or materially expanded mandatory guidance.
- PATCH: clarifications, wording improvements, and non-semantic refinements.

Compliance policy:
- Plans MUST pass Constitution Check gates before research/design advances.
- Specs and tasks MUST map requirements and work items to constitution rules.
- Exceptions MUST be documented in the relevant plan with rationale,
  approver, and expiration date.

**Version**: 1.0.0 | **Ratified**: 2026-02-20 | **Last Amended**: 2026-02-20

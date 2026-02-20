# Feature Specification: CHM Core Inventory and Run Health

**Feature Branch**: `001-chm-api-ingestion`  
**Created**: 2026-02-20  
**Status**: Draft  
**Input**: User description: "CHM canonical inventory, run history, idempotent external ingestion, and dashboard-ready health queries"

## Scope Boundaries

### In Scope

- Canonical inventory and lifecycle management for clients, pipelines, runs, and alert rules.
- Historical run storage, latest-status retrieval, and client-level health summaries.
- Repeatable external run ingestion with idempotent replay behavior.
- Dashboard-ready operational and BI output shapes for trend and failure analysis.

### Out of Scope (MVP)

- Full observability platform beyond run-event monitoring outputs.
- End-user authentication and multi-tenant productization.
- End-user UI frontend experiences.
- Alert notification execution workflows.
- Advanced scheduling or SLA breach automation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Maintain Canonical Inventory and Latest Status (Priority: P1)

An operations analyst can manage clients and pipelines, record run events, and see
current/latest run state per pipeline so incident triage starts immediately.

**Why this priority**: This is the minimum workflow needed to answer "what is failing
right now" and "what is the latest run status per pipeline per client."

**Independent Test**: Create clients and pipelines, record multiple runs per pipeline,
then verify list filtering and latest-status retrieval are correct without any external
integration.

**Acceptance Scenarios**:

1. **Given** an active client and pipeline, **When** a new run is recorded, **Then** the
   run appears in that pipeline's history with status and timestamps.
2. **Given** multiple runs for one pipeline, **When** latest status is requested,
   **Then** the most recent run is returned using the defined ordering rule.
3. **Given** a time window and status filter, **When** run history is queried,
   **Then** only matching runs are returned.

---

### User Story 2 - Reingest External Runs Idempotently (Priority: P2)

A platform operator can re-run ingestion safely from external systems without creating
duplicate runs, while still reflecting status progression for the same external run.

**Why this priority**: Reliable re-ingestion is required for operational trust,
backfills, and recovery from partner/API interruptions.

**Independent Test**: Run ingestion against the same external run pages multiple times;
verify that run counts do not increase for duplicates and status updates are applied to
existing runs.

**Acceptance Scenarios**:

1. **Given** external runs already ingested, **When** the same external page is ingested
   again, **Then** no duplicate run records are created.
2. **Given** an existing run recorded as running, **When** re-ingestion receives the same
   external run as success, **Then** the existing run is updated to success.
3. **Given** paginated external results, **When** ingestion executes, **Then** all pages
   are consumed until no next cursor remains.

---

### User Story 3 - Analyze Trends and Configure Alert Rules (Priority: P3)

A delivery lead can review client and pipeline health trends over time and maintain
alert rule definitions for future alert execution.

**Why this priority**: Trend and flakiness analysis drives proactive remediation and
client reporting, while stored alert rules prepare future alerting rollout.

**Independent Test**: Load representative run history, retrieve summary outputs for
trend questions, and create/edit/disable rules with scope and rule-type validation.

**Acceptance Scenarios**:

1. **Given** run history over several days, **When** trend views are requested,
   **Then** failures over time, failure counts by client, and top flaky pipelines are
   available.
2. **Given** a rule scoped to a client or pipeline, **When** it is created or updated,
   **Then** rule-type parameter validation is enforced.
3. **Given** both client and pipeline are set on a rule, **When** scope is interpreted,
   **Then** pipeline scope takes precedence.

### Edge Cases

- External ingestion receives rate limiting; retries MUST back off and continue safely.
- External runs missing one or both timestamps MUST still be recorded when identity and
  status are present.
- Unknown source statuses MUST be normalized to a supported internal status and retain
  source detail for review.
- Ingestion replays with partial overlap across pages MUST remain duplicate-free.
- Manual run creation without an external identifier MUST still create a uniquely
  identifiable run.
- Disabled clients or pipelines MUST not be treated as active inventory in standard
  listings.
- Alert rules with invalid threshold/window combinations MUST be rejected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST maintain exactly four business entities for MVP:
  clients, pipelines, runs, and alert rules.
- **FR-002**: Users MUST be able to create, list, retrieve, and update clients, with
  unique client naming and active/inactive state.
- **FR-003**: Users MUST be able to create, list, retrieve, and update pipelines under
  exactly one client, including platform/type/environment metadata.
- **FR-004**: Users MUST be able to record and retrieve run history per pipeline as
  time-based events.
- **FR-005**: Run history queries MUST support filtering by run status and time window,
  with bounded result limits and deterministic ordering.
- **FR-006**: The system MUST provide latest-run retrieval per pipeline using this
  ordering rule: started time descending, then finished time descending, with null
  timestamps sorted last.
- **FR-007**: The system MUST support a client-level run summary for a time window that
  returns status counts and latest status per pipeline.
- **FR-008**: Users MUST be able to create, list, retrieve, update, enable/disable, and
  delete alert rule definitions.
- **FR-009**: Alert rules MUST allow client scope, pipeline scope, or both; at least one
  scope is required.
- **FR-010**: For rule type "on failure", threshold and window may be empty; for
  "failures in window", threshold and window are required and must be positive.
- **FR-011**: External ingestion MUST process run events for pipelines that have external
  mapping identifiers.
- **FR-012**: External ingestion MUST consume paginated partner responses until no
  continuation cursor is returned.
- **FR-013**: External run events MUST be normalized to canonical run attributes,
  including status, timestamps, optional metrics, and full source payload retention.
- **FR-014**: Ingestion MUST be idempotent using pipeline plus external run identity;
  repeated ingestion MUST update existing runs instead of creating duplicates.
- **FR-015**: Ingestion interactions with external systems MUST apply request timeouts,
  transient-failure retries, and rate-limit backoff behavior.
- **FR-016**: Service responses MUST be JSON and use a consistent error structure across
  validation and business-rule failures.
- **FR-017**: The system MUST provide dashboard-ready outputs for failures over time,
  latest status by pipeline, failure counts by client, flaky pipelines, and failure
  rate by platform.
- **FR-018**: Client and pipeline deletion behavior MUST default to soft disable;
  historical run records MUST remain available for analysis.
- **FR-019**: Manual run creation MUST accept caller-provided run identity and MUST
  auto-generate one when omitted.
- **FR-020**: All entities MUST include auditable creation and update timestamps.

### Key Entities *(include if feature involves data)*

- **Client**: Represents a consulting customer scope for health monitoring; includes
  unique name, active flag, timestamps, and ownership of pipelines.
- **Pipeline**: Represents a recurring job definition belonging to one client; includes
  name, platform, pipeline type, environment, optional external mapping, active flag,
  and timestamps.
- **Run**: Represents one execution attempt of a pipeline; includes external run
  identity, lifecycle status, start/finish times, derived/ingested metrics,
  optional failure context, raw source payload, ingest timestamp, and audit timestamps.
- **Alert Rule**: Represents stored alert conditions for future execution; includes
  rule type, scope (client and/or pipeline), destination channel, threshold/window
  parameters when required, enabled state, and timestamps.

### Data Integrity & Invariants *(mandatory for data changes)*

- **DI-001**: Client name is globally unique.
- **DI-002**: Pipeline name is unique within a client.
- **DI-003**: When external mapping identifiers are present, platform plus external
  identifier is unique within a client.
- **DI-004**: Run identity for ingestion is unique per pipeline and external run
  identifier.
- **DI-005**: Run status values are restricted to supported lifecycle states.
- **DI-006**: Each pipeline references exactly one valid client; each run references one
  valid pipeline.
- **DI-007**: Alert rules require at least one scope target (client or pipeline).
- **DI-008**: Duplicate active alert rules for the same scope, rule type, and
  destination are not allowed.

### API Contracts & Query Patterns *(mandatory for endpoint changes)*

- **AC-001**: Create, list, retrieve, update, and delete/disable contracts are available
  for each relevant entity according to scope.
- **AC-002**: Validation failures return a consistent machine-readable error payload with
  field-level issue details.
- **AC-003**: List contracts support predictable filtering, limit bounds, and stable
  sort behavior.
- **AC-004**: Run-query contracts support status and time-window filters and a latest-run
  contract with the defined ordering behavior.
- **AC-005**: Client summary contracts provide both aggregate status counts and latest
  status snapshot per pipeline for the selected period.

### Observability & BI Outputs *(mandatory for reporting-impacting work)*

- **OB-001**: Provide a time-series output of failed run counts by time bucket.
- **OB-002**: Provide a latest-status output by pipeline including client context.
- **OB-003**: Provide failed-run counts by client for rolling 24-hour and 7-day windows.
- **OB-004**: Provide a "top flaky pipelines" output for the prior 30 days based on
  failure frequency.
- **OB-005**: Provide failure-rate output by platform (failed runs divided by total
  runs).
- **OB-006**: Provide run-duration distribution output when duration data is available.

### Security & Environment Scope *(mandatory)*

- **SE-001**: Integration credentials and tokens MUST be least-privilege and scoped to
  environment boundaries.
- **SE-002**: Secrets MUST not be exposed in logs, errors, or dashboard outputs.
- **SE-003**: Raw run payload storage MUST avoid storing secrets when source payloads
  contain sensitive values.
- **SE-004**: Configuration for development and production contexts MUST remain clearly
  separated to prevent accidental cross-environment access.

## Assumptions

- MVP is internal-only and does not include end-user authentication flows.
- Client and pipeline deletion defaults to soft disable to preserve history.
- Latest run selection uses started time first, then finished time, with nulls last.
- Alert rules allow both client and pipeline scope; pipeline scope takes precedence when
  both are present.
- If manual run identity is not provided, the system generates a unique run identifier.

## Dependencies

- External partner systems provide run-event feeds with stable per-run identity values.
- Internal consumers can access output shapes for operational monitoring and BI analysis.
- Business owners provide valid destination values for stored alert-rule configurations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a given client, operations users can determine current failing
  pipelines and latest pipeline status within 2 minutes in at least 95% of test runs.
- **SC-002**: Replaying the same ingestion dataset three consecutive times results in no
  increase in unique run count beyond the first ingest.
- **SC-003**: For a controlled test dataset, latest-run and client-summary outputs match
  expected reference results with 100% accuracy.
- **SC-004**: Stakeholders can answer all four core questions (current failures,
  changes since yesterday, latest status per pipeline/client, flaky pipelines over time)
  using provided outputs without custom data extraction.
- **SC-005**: Core CRUD operations for clients, pipelines, runs, and alert rules succeed
  for valid input and reject invalid input with clear validation feedback in 100% of
  acceptance tests.

---

description: "Executable task list for CHM core inventory, idempotent ingestion, and dashboard readiness"
---

# Tasks: CHM Core Inventory and Run Health

**Input**: Design documents from `/Volumes/T7/CHM/specs/001-chm-api-ingestion/`  
**Prerequisites**: `/Volumes/T7/CHM/specs/001-chm-api-ingestion/plan.md`, `/Volumes/T7/CHM/specs/001-chm-api-ingestion/spec.md`, `/Volumes/T7/CHM/specs/001-chm-api-ingestion/research.md`, `/Volumes/T7/CHM/specs/001-chm-api-ingestion/data-model.md`, `/Volumes/T7/CHM/specs/001-chm-api-ingestion/contracts/openapi.yaml`, `/Volumes/T7/CHM/specs/001-chm-api-ingestion/contracts/dashboard-queries.sql`

**Tests**: Required. Critical-path coverage MUST include schema constraints, ingestion idempotency/mapping, latest/summary logic, CRUD smoke, and dashboard query validation.

**Organization**: Tasks are grouped for incremental delivery by milestone order (Schema -> API -> Ingestion -> Tests -> Dashboards) while preserving user-story traceability (`US1`, `US2`, `US3`).

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Parallelizable task (different files, no direct dependency)
- **[Story]**: User story mapping label (`[US1]`, `[US2]`, `[US3]`)
- Each task includes: Goal, DoD, dependencies, GitHub issue title, and acceptance checks

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize project scaffolding and delivery workflow prerequisites.

- [ ] T001 Create service skeleton and app entrypoint in `app/main.py`, `app/__init__.py`, and `app/api/__init__.py` | Goal: establish runnable API base for all milestones | DoD: app package imports cleanly and health route stub exists | Depends: none | Issue: `CHM T001: Scaffold FastAPI service skeleton` | Verify: `python -c "import app.main"`
- [ ] T002 Initialize runtime and dev configuration in `pyproject.toml`, `requirements-dev.txt`, and `.env.example` | Goal: lock dependencies and environment shape | DoD: dependency files include FastAPI, SQLAlchemy, Alembic, requests, pytest stack | Depends: T001 | Issue: `CHM T002: Configure project dependencies and env template` | Verify: `pip install -r requirements-dev.txt`
- [ ] T003 [P] Add local stack definitions for Postgres, Grafana, and Metabase in `docker/docker-compose.yml` | Goal: reproducible local dependencies | DoD: compose file starts all required services with stable ports | Depends: T002 | Issue: `CHM T003: Add local Postgres Grafana Metabase stack` | Verify: `docker compose -f docker/docker-compose.yml config`
- [ ] T004 [P] Add pytest scaffolding and shared fixtures in `tests/conftest.py`, `tests/contract/__init__.py`, and `tests/integration/__init__.py` | Goal: consistent test harness for all stories | DoD: pytest collection succeeds with empty baseline tests | Depends: T002 | Issue: `CHM T004: Initialize contract and integration test scaffold` | Verify: `pytest --collect-only`
- [ ] T005 [P] Add issue and PR templates in `.github/ISSUE_TEMPLATE/chm-task.md` and `.github/pull_request_template.md` | Goal: support issue-per-task and PR linking workflow | DoD: templates include issue reference and base branch main checklist item | Depends: none | Issue: `CHM T005: Add GitHub issue and PR templates for task workflow` | Verify: `test -f .github/ISSUE_TEMPLATE/chm-task.md && test -f .github/pull_request_template.md`

---

## Phase 2: Foundational (Blocking Prerequisites) - Milestone 1 Schema First (Hard Gate)

**Purpose**: Implement schema-first foundation and hard constraints before any story implementation.

**CRITICAL**: No user story work starts before this phase is complete.

- [ ] T006 Create enum migration for platform, pipeline_type, run_status, rule_type, and channel in `migrations/versions/001_create_enums.py` | Goal: enforce canonical categorical values at DB level | DoD: migration applies/rolls back cleanly | Depends: T001,T002 | Issue: `CHM T006: Create enum types migration` | Verify: `alembic upgrade +1 && alembic downgrade -1`
- [ ] T007 Create `clients` and `pipelines` tables with FK and uniqueness constraints in `migrations/versions/002_clients_pipelines.py` | Goal: establish client/pipeline inventory integrity | DoD: `(client_id,name)` uniqueness and FK behavior are enforced | Depends: T006 | Issue: `CHM T007: Add clients and pipelines schema migration` | Verify: `pytest tests/integration/test_schema_constraints.py -k clients_pipelines`
- [ ] T008 Create `runs` and `alert_rules` tables with idempotency and rule checks in `migrations/versions/003_runs_alert_rules.py` | Goal: enforce ingestion and alert invariants in schema | DoD: unique `(pipeline_id,external_run_id)` and alert scope/rule checks enforce correctly | Depends: T007 | Issue: `CHM T008: Add runs and alert_rules schema migration with hard constraints` | Verify: `pytest tests/integration/test_schema_constraints.py -k runs_alert_rules`
- [ ] T009 [P] Add query/performance indexes for latest, filters, and dashboard aggregations in `migrations/versions/004_run_indexes.py` | Goal: support API and dashboard query performance | DoD: indexes exist for run status/time and key joins | Depends: T008 | Issue: `CHM T009: Add run query indexes for API and dashboards` | Verify: `pytest tests/integration/test_schema_constraints.py -k indexes`
- [ ] T010 Implement SQLAlchemy models for four-table domain in `app/db/models/client.py`, `app/db/models/pipeline.py`, `app/db/models/run.py`, and `app/db/models/alert_rule.py` | Goal: align ORM with migration constraints | DoD: model metadata matches migration schema and relationships | Depends: T008 | Issue: `CHM T010: Implement SQLAlchemy models for CHM entities` | Verify: `pytest tests/unit/test_model_metadata.py`
- [ ] T011 Implement DB session and base repositories in `app/db/base.py`, `app/db/repository/clients.py`, `app/db/repository/pipelines.py`, `app/db/repository/runs.py`, and `app/db/repository/alert_rules.py` | Goal: provide shared data-access primitives | DoD: CRUD repository operations pass repository smoke tests | Depends: T010 | Issue: `CHM T011: Implement repository layer foundation` | Verify: `pytest tests/unit/test_repositories_smoke.py`
- [ ] T012 Add schema hard-gate tests for constraints and uniqueness in `tests/integration/test_schema_constraints.py` | Goal: prevent regression of schema-first guarantees | DoD: tests fail without constraints and pass with migrations applied | Depends: T007,T008,T009 | Issue: `CHM T012: Add schema hard gate integration tests` | Verify: `pytest tests/integration/test_schema_constraints.py`

**Checkpoint**: Schema-first hard gate is complete and validated.

---

## Phase 3: User Story 1 - Maintain Canonical Inventory and Latest Status (Priority: P1) - Milestone 2 API Baseline

**Goal**: Deliver CRUD and core run query endpoints to answer current/latest status questions.

**Independent Test**: Create clients/pipelines/runs, query filtered run history, retrieve latest run, and fetch client summary with deterministic results.

### Tests for User Story 1

- [ ] T013 [P] [US1] Add contract tests for client/pipeline/run endpoints in `tests/contract/test_clients_pipelines_runs_api.py` | Goal: lock API contract behavior for core resources | DoD: create/list/get/patch/delete contracts validated for required endpoints | Depends: T011 | Issue: `CHM T013: Add contract tests for clients pipelines runs endpoints` | Verify: `pytest tests/contract/test_clients_pipelines_runs_api.py`
- [ ] T014 [P] [US1] Add integration tests for run filters and latest ordering in `tests/integration/test_runs_latest_and_filters.py` | Goal: validate operational run-query correctness | DoD: status filters, since/until, limit/order, and latest-run tie-breaking are covered | Depends: T011 | Issue: `CHM T014: Add integration tests for run filtering and latest selection` | Verify: `pytest tests/integration/test_runs_latest_and_filters.py`

### Implementation for User Story 1

- [ ] T015 [US1] Implement JSON error envelope and validation handlers in `app/core/errors.py` and `app/schemas/error.py` | Goal: ensure consistent API error contracts | DoD: validation/domain errors return common code/message/details structure | Depends: T013 | Issue: `CHM T015: Implement consistent API error envelope` | Verify: `pytest tests/contract/test_clients_pipelines_runs_api.py -k error`
- [ ] T016 [US1] Implement client schemas, service, and router in `app/schemas/client.py`, `app/services/clients.py`, and `app/api/clients.py` | Goal: support client CRUD and soft disable behavior | DoD: `/clients` and `/clients/{client_id}` contract tests pass | Depends: T015 | Issue: `CHM T016: Implement clients API and service layer` | Verify: `pytest tests/contract/test_clients_pipelines_runs_api.py -k clients`
- [ ] T017 [US1] Implement pipeline schemas, service, and router in `app/schemas/pipeline.py`, `app/services/pipelines.py`, and `app/api/pipelines.py` | Goal: support pipeline CRUD under client scope | DoD: `/clients/{client_id}/pipelines` and `/pipelines/{pipeline_id}` behaviors pass tests | Depends: T016 | Issue: `CHM T017: Implement pipelines API and service layer` | Verify: `pytest tests/contract/test_clients_pipelines_runs_api.py -k pipelines`
- [ ] T018 [US1] Implement run create/list/latest schemas, service, and router in `app/schemas/run.py`, `app/services/runs.py`, and `app/api/runs.py` | Goal: deliver run event storage and latest-run query behavior | DoD: `/pipelines/{pipeline_id}/runs` and `/runs/latest` tests pass | Depends: T017 | Issue: `CHM T018: Implement runs API including latest run endpoint` | Verify: `pytest tests/contract/test_clients_pipelines_runs_api.py -k runs`
- [ ] T019 [US1] Implement client summary service and route in `app/services/summaries.py` and `app/api/clients.py` | Goal: return counts by status and latest pipeline status per client | DoD: `/clients/{client_id}/runs/summary` returns deterministic tested payload | Depends: T018 | Issue: `CHM T019: Implement client run summary endpoint` | Verify: `pytest tests/integration/test_runs_latest_and_filters.py -k summary`
- [ ] T020 [US1] Add API parity gate between implementation and `specs/001-chm-api-ingestion/contracts/openapi.yaml` in `tests/contract/test_openapi_parity.py` | Goal: enforce API parity hard check | DoD: test fails for route/schema drift and passes when parity is restored | Depends: T016,T017,T018,T019 | Issue: `CHM T020: Add OpenAPI parity gate for implemented endpoints` | Verify: `pytest tests/contract/test_openapi_parity.py`

**Checkpoint**: US1 is independently functional and API baseline milestone is satisfied.

---

## Phase 4: User Story 2 - Reingest External Runs Idempotently (Priority: P2) - Milestone 3 Ingestion Job (Hard Gate)

**Goal**: Implement resilient external ingestion with duplicate-safe upsert and status progression updates.

**Independent Test**: Re-run ingestion on repeated source pages and confirm zero duplicate runs and correct updates for existing run states.

### Tests for User Story 2

- [ ] T021 [P] [US2] Add ingestion replay idempotency tests in `tests/integration/test_ingestion_idempotency.py` | Goal: enforce no-duplicate guarantee for repeat ingestion | DoD: repeated ingest preserves unique run count by `(pipeline_id,external_run_id)` | Depends: T020 | Issue: `CHM T021: Add ingestion idempotency replay tests` | Verify: `pytest tests/integration/test_ingestion_idempotency.py`
- [ ] T022 [P] [US2] Add ingestion status progression and pagination tests in `tests/integration/test_ingestion_progression_and_pagination.py` | Goal: validate updates and cursor traversal behavior | DoD: running->success update path and multi-page ingestion are covered | Depends: T020 | Issue: `CHM T022: Add ingestion status progression and pagination tests` | Verify: `pytest tests/integration/test_ingestion_progression_and_pagination.py`

### Implementation for User Story 2

- [ ] T023 [US2] Implement partner HTTP ingestion client with timeout/retry/backoff in `app/ingestion/client.py` | Goal: reliable external fetch behavior for transient failures and 429 handling | DoD: retry policy and timeout behavior are deterministic in tests | Depends: T021,T022 | Issue: `CHM T023: Implement partner ingestion HTTP client resilience` | Verify: `pytest tests/unit/test_ingestion_client.py`
- [ ] T024 [US2] Implement source-to-run mapper and status normalization in `app/ingestion/mapper.py` | Goal: normalize partner payload into canonical run fields | DoD: mapping handles required and optional fields with UTC-safe parsing | Depends: T023 | Issue: `CHM T024: Implement ingestion mapper and status normalization` | Verify: `pytest tests/unit/test_ingestion_mapper.py`
- [ ] T025 [US2] Implement run upsert logic keyed on `(pipeline_id, external_run_id)` in `app/db/repository/runs.py` | Goal: satisfy idempotent ingestion hard gate | DoD: upsert updates mutable fields and preserves unique identity | Depends: T024 | Issue: `CHM T025: Implement idempotent run upsert repository` | Verify: `pytest tests/integration/test_ingestion_idempotency.py -k upsert`
- [ ] T026 [US2] Implement ingestion job orchestration for pipelines with `external_id` in `app/ingestion/job.py` | Goal: paginate through partner runs and persist normalized events | DoD: job loops by cursor, processes each configured pipeline, and records ingest timestamps | Depends: T025 | Issue: `CHM T026: Implement ingestion job orchestration by external_id` | Verify: `pytest tests/integration/test_ingestion_progression_and_pagination.py -k job`
- [ ] T027 [US2] Wire ingestion trigger and secret-safe logging in `app/api/ingestion.py` and `app/core/config.py` | Goal: operationally safe ingestion execution path | DoD: ingestion can be triggered without logging secrets or tokens | Depends: T026 | Issue: `CHM T027: Wire ingestion execution endpoint and secure logging` | Verify: `pytest tests/integration/test_ingestion_idempotency.py -k logging`

**Checkpoint**: Ingestion hard gate is complete; idempotency and status progression are validated.

---

## Phase 5: User Story 3 - Analyze Trends and Configure Alert Rules (Priority: P3)

**Goal**: Deliver alert-rule CRUD/validation and dashboard-ready analytical outputs.

**Independent Test**: Configure valid/invalid alert rules and validate dashboard queries against seeded run history.

### Milestone 4: Test Coverage Gate

- [ ] T028 [P] [US3] Add alert-rule contract tests for CRUD and rule-type validation in `tests/contract/test_alert_rules_api.py` | Goal: lock alert configuration behavior | DoD: create/list/get/patch/delete and rule_type validation paths covered | Depends: T020 | Issue: `CHM T028: Add alert rules contract and validation tests` | Verify: `pytest tests/contract/test_alert_rules_api.py`
- [ ] T029 [P] [US3] Add integration tests for scope precedence and enable/disable lifecycle in `tests/integration/test_alert_rules_scope.py` | Goal: validate client/pipeline scope semantics and rule lifecycle | DoD: pipeline-over-client precedence and toggling behavior are verified | Depends: T020 | Issue: `CHM T029: Add alert rule scope precedence integration tests` | Verify: `pytest tests/integration/test_alert_rules_scope.py`
- [ ] T030 [US3] Add full critical-path smoke suite runner in `tests/integration/test_critical_path_gate.py` | Goal: enforce milestone-level coverage gate before merge | DoD: suite executes schema, API, ingestion, and summary smoke assertions in one command | Depends: T021,T022,T028,T029 | Issue: `CHM T030: Add cross-milestone critical path test gate` | Verify: `pytest tests/integration/test_critical_path_gate.py`

### Milestone 5: Dashboard-Ready Query Shapes

- [ ] T031 [US3] Implement alert-rule schemas/service/router in `app/schemas/alert_rule.py`, `app/services/alert_rules.py`, and `app/api/alert_rules.py` | Goal: expose alert_rule endpoints from OpenAPI contract | DoD: alert-rule contract tests pass and validation rules enforce constraints | Depends: T028,T029 | Issue: `CHM T031: Implement alert rules API parity` | Verify: `pytest tests/contract/test_alert_rules_api.py -k api`
- [ ] T032 [US3] Implement dashboard query adapter for SQL shapes in `app/services/dashboard_queries.py` and `app/db/repository/dashboard.py` | Goal: make dashboard query shapes consumable and testable | DoD: query adapter executes all required analytical outputs with parameter binding | Depends: T031 | Issue: `CHM T032: Implement dashboard query adapter services` | Verify: `pytest tests/unit/test_dashboard_query_adapter.py`
- [ ] T033 [US3] Validate `specs/001-chm-api-ingestion/contracts/dashboard-queries.sql` against realistic seeded data in `tests/integration/test_dashboard_queries.py` and `tests/fixtures/dashboard_seed.sql` | Goal: guarantee Grafana/Metabase readiness | DoD: all six query shapes produce expected rows/metrics on seeded dataset | Depends: T032 | Issue: `CHM T033: Validate dashboard SQL against realistic seeded dataset` | Verify: `pytest tests/integration/test_dashboard_queries.py`
- [ ] T034 [US3] Document dashboard field mappings and usage notes in `specs/001-chm-api-ingestion/contracts/dashboard-readme.md` | Goal: operational handoff for Grafana and Metabase consumers | DoD: each query has documented parameters, output columns, and intended dashboard panel | Depends: T033 | Issue: `CHM T034: Document dashboard query contracts for BI and Grafana` | Verify: `test -f specs/001-chm-api-ingestion/contracts/dashboard-readme.md`

**Checkpoint**: US3 is independently functional; test and dashboard milestones are complete.

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Final workflow hardening, GitHub issue orchestration, and release readiness.

- [ ] T035 Create GitHub issues (one per task T001-T034) and track URLs in `docs/project-management/issues.md` | Goal: enforce issue-per-task execution workflow on `Fatih0234/CHM` | DoD: each task has a corresponding GitHub issue with milestone label and assignee/state | Depends: T001,T002,T003,T004,T005 | Issue: `CHM T035: Create and track GitHub issues for all implementation tasks` | Verify: `gh issue list --repo Fatih0234/CHM --limit 200`
- [ ] T036 Update contribution workflow docs for PR linking and base branch `main` in `docs/project-management/pr-workflow.md` and `.github/pull_request_template.md` | Goal: guarantee PRs link issues and target main | DoD: workflow doc and PR template require "Closes #<issue>" and base branch main checks | Depends: T035 | Issue: `CHM T036: Enforce issue-linked PR workflow targeting main` | Verify: `rg -n "Closes #|base branch.*main" docs/project-management/pr-workflow.md .github/pull_request_template.md`
- [ ] T037 Run end-to-end quickstart validation and capture evidence in `docs/validation/001-chm-api-ingestion.md` | Goal: prove readiness for merge and demo | DoD: validation report includes commands run, pass/fail evidence, and known limitations | Depends: T012,T020,T027,T030,T033,T036 | Issue: `CHM T037: Record end-to-end validation evidence for feature readiness` | Verify: `pytest && test -f docs/validation/001-chm-api-ingestion.md`

---

## Dependencies & Execution Order

### Milestone Dependencies

- **Schema First (Phase 2)**: Depends on setup completion; blocks all user stories.
- **API Baseline (US1 / Phase 3)**: Depends on schema hard gate completion.
- **Ingestion Job (US2 / Phase 4)**: Depends on API baseline and schema hard gate.
- **Test Coverage Gate (US3 / Phase 5 milestone 4)**: Depends on API + ingestion tests being available.
- **Dashboard Query Shapes (US3 / Phase 5 milestone 5)**: Depends on ingestion data model and test gate.
- **Polish (Final)**: Depends on all milestone checkpoints.

### User Story Dependencies

- **US1 (P1)**: Starts immediately after foundational schema phase; no dependency on other stories.
- **US2 (P2)**: Depends on foundational schema and core run model/API behavior from US1.
- **US3 (P3)**: Depends on foundational schema and run history generated by US1/US2.

### Task Dependency Graph (High Level)

- `T001-T005 -> T006-T012 -> T013-T020 -> T021-T027 -> T028-T034 -> T035-T037`

### Within Each User Story

- Tests first (fail initially), then implementation.
- Schema/repository tasks before service tasks.
- Service tasks before router/endpoint tasks.
- Parity/validation gates before phase checkpoint completion.

## Parallel Opportunities

- Setup parallel: `T003`, `T004`, `T005`
- Foundational parallel: `T009` after `T008`
- US1 test parallel: `T013`, `T014`
- US2 test parallel: `T021`, `T022`
- US3 test parallel: `T028`, `T029`

## Parallel Example: User Story 1

```bash
# Run in parallel after foundational phase:
Task: "T013 Contract tests for clients/pipelines/runs in tests/contract/test_clients_pipelines_runs_api.py"
Task: "T014 Integration tests for latest/filter behavior in tests/integration/test_runs_latest_and_filters.py"
```

## Parallel Example: User Story 2

```bash
# Run in parallel before ingestion implementation:
Task: "T021 Idempotency replay tests in tests/integration/test_ingestion_idempotency.py"
Task: "T022 Status progression and pagination tests in tests/integration/test_ingestion_progression_and_pagination.py"
```

## Parallel Example: User Story 3

```bash
# Run in parallel before alert-rule implementation:
Task: "T028 Alert rule contract tests in tests/contract/test_alert_rules_api.py"
Task: "T029 Alert scope precedence tests in tests/integration/test_alert_rules_scope.py"
```

## Implementation Strategy

### MVP First (Recommended)

1. Complete Setup (Phase 1).
2. Complete Schema First hard gate (Phase 2).
3. Complete API Baseline (US1 / Phase 3).
4. Complete Ingestion Job hard gate (US2 / Phase 4).
5. Stop and validate with `T030` critical-path gate.

### Incremental Delivery

1. Deliver Milestone 1 (Schema) in small PRs (`T006-T012`).
2. Deliver Milestone 2 (API baseline) in PR slices by endpoint group (`T015-T020`).
3. Deliver Milestone 3 (Ingestion) in PR slices by client/mapper/upsert/job (`T023-T027`).
4. Deliver Milestone 4 (Test gate) and Milestone 5 (Dashboards) (`T028-T034`).
5. Finalize GitHub workflow and validation evidence (`T035-T037`).

### Suggested MVP Scope

- Complete through `T027` (Schema + API + Ingestion hard gates) and run `T030` for readiness.

## Notes

- All PRs must reference exactly one primary task issue and target base branch `main`.
- Use `Closes #<issue-number>` in PR descriptions to maintain issue linkage.
- Keep each PR to 1-4 hours of implementation scope matching one task.

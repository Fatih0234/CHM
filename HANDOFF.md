# Handoff

CHM (Client Health Monitor) is an internal service for tracking client pipelines,
run history, and ingestion-driven health status over time.

## Source of Truth Artifacts

- Specification: `specs/001-chm-api-ingestion/spec.md`
- Implementation plan: `specs/001-chm-api-ingestion/plan.md`
- Task plan: `specs/001-chm-api-ingestion/tasks.md`
- Data model: `specs/001-chm-api-ingestion/data-model.md`
- Research decisions: `specs/001-chm-api-ingestion/research.md`
- Quickstart: `specs/001-chm-api-ingestion/quickstart.md`
- API contract: `specs/001-chm-api-ingestion/contracts/openapi.yaml`
- Dashboard query shapes: `specs/001-chm-api-ingestion/contracts/dashboard-queries.sql`

## Branch Context

- Base branch: `main`
- Current feature branch: `001-chm-api-ingestion`

## Next Steps

1. Create GitHub issues from tasks `T001` through `T037` in order (one issue per task).
2. Start implementation in milestone order from `tasks.md`.
3. Respect hard gates:
   - Schema-first gate: `T006` to `T012`
   - Idempotent ingestion gate: `T021` to `T027`
4. MVP target:
   - Complete through `T027`
   - Then run readiness gate `T030` before expanding scope.

# Phase 1 Data Model: CHM Core Inventory and Run Health

## Entity Relationship Overview

- A `client` has many `pipelines`.
- A `pipeline` belongs to one `client` and has many `runs`.
- An `alert_rule` may reference a `client`, a `pipeline`, or both.
- A `run` belongs to exactly one `pipeline`.

## clients

### Fields

- `id`: UUID/serial primary key
- `name`: text, required, globally unique
- `is_active`: boolean, required, default true
- `created_at`: timestamp with time zone, required
- `updated_at`: timestamp with time zone, required

### Validation Rules

- `name` must be non-empty and unique.
- `is_active` defaults to true.

### Constraints

- Primary key on `id`
- Unique constraint on `name`

## pipelines

### Fields

- `id`: UUID/serial primary key
- `client_id`: foreign key -> `clients.id`, required
- `name`: text, required
- `platform`: enum (`airflow`, `dbt`, `cron`, `vendor_api`, `custom`), required
- `external_id`: text, nullable
- `pipeline_type`: enum (`ingestion`, `transform`, `quality`, `export`, `healthcheck`), required
- `description`: text, nullable
- `environment`: enum (`dev`, `staging`, `prod`), default `prod`
- `is_active`: boolean, required, default true
- `created_at`: timestamp with time zone, required
- `updated_at`: timestamp with time zone, required

### Validation Rules

- `name` must be unique within a client.
- If `external_id` is provided, it maps to partner pipeline identity for ingestion.

### Constraints

- Primary key on `id`
- Foreign key `client_id` references `clients.id`
- Unique constraint `(client_id, name)`
- Recommended unique constraint `(client_id, platform, external_id)` with null-safe behavior

## runs

### Fields

- `id`: UUID/serial primary key
- `pipeline_id`: foreign key -> `pipelines.id`, required
- `external_run_id`: text, required for ingested runs; auto-generated for manual runs when omitted
- `status`: enum (`running`, `success`, `failed`, `canceled`, `skipped`), required
- `started_at`: timestamp with time zone, nullable
- `finished_at`: timestamp with time zone, nullable
- `duration_seconds`: integer, nullable
- `rows_processed`: bigint, nullable
- `error_message`: text (short), nullable
- `status_reason`: text (short), nullable
- `payload`: JSONB, nullable
- `ingested_at`: timestamp with time zone, required
- `created_at`: timestamp with time zone, required
- `updated_at`: timestamp with time zone, required

### Validation Rules

- `status` must be one of the allowed lifecycle values.
- `duration_seconds` and `rows_processed` must be non-negative when present.
- If `status` is terminal (`success`, `failed`, `canceled`, `skipped`), `finished_at` should
  be present when provided by source.

### Constraints

- Primary key on `id`
- Foreign key `pipeline_id` references `pipelines.id`
- Unique constraint `(pipeline_id, external_run_id)` for idempotency
- Optional check constraints for non-negative numeric metrics

### State Transitions

Allowed transitions for the same `(pipeline_id, external_run_id)` record:

- `running` -> `success`
- `running` -> `failed`
- `running` -> `canceled`
- `running` -> `skipped`
- terminal -> same terminal state (idempotent replay)

Disallowed transition handling:

- Regressions from terminal to `running` should be ignored or rejected based on source trust policy.

## alert_rules

### Fields

- `id`: UUID/serial primary key
- `client_id`: foreign key -> `clients.id`, nullable
- `pipeline_id`: foreign key -> `pipelines.id`, nullable
- `rule_type`: enum (`on_failure`, `failures_in_window`), required
- `threshold`: integer, nullable
- `window_minutes`: integer, nullable
- `channel`: enum (`slack`, `email`, `webhook`), required
- `destination`: text, required
- `is_enabled`: boolean, required, default true
- `created_at`: timestamp with time zone, required
- `updated_at`: timestamp with time zone, required

### Validation Rules

- At least one of `client_id` or `pipeline_id` must be present.
- For `on_failure`, `threshold` and `window_minutes` may be null.
- For `failures_in_window`, `threshold` and `window_minutes` are required and > 0.
- If both scopes are set, future evaluation precedence is pipeline first.

### Constraints

- Primary key on `id`
- Foreign key `client_id` references `clients.id`
- Foreign key `pipeline_id` references `pipelines.id`
- Check constraint: `client_id IS NOT NULL OR pipeline_id IS NOT NULL`
- Check constraints for rule-type parameter requirements
- Recommended unique active-rule constraint over `(scope, rule_type, channel, destination)`

## Derived/Query Shapes

The following outputs are first-class data shapes for dashboards:

- Failed runs over time by bucket and client/pipeline dimensions
- Latest run per pipeline with client and platform context
- Failure counts per client over rolling windows
- Top flaky pipelines over 30 days
- Failure rate per platform (failed/total)

## Migration Notes

- Create entity enums before dependent tables.
- Create tables in dependency order: `clients`, `pipelines`, `runs`, `alert_rules`.
- Add indexes for query-heavy filters: run status, run timestamps, pipeline/client joins.
- Backfill strategy is not required for initial MVP schema rollout.

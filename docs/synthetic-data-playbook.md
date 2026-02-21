# CHM Synthetic Data Playbook (ChatGPT/Gemini)

This playbook gives you repeatable prompts and a flow to generate interesting synthetic data across multiple chat sessions without breaking references.

## 1) Core Idea

Treat synthetic data as a versioned artifact.

- Keep one canonical `id_registry.csv` as source of truth for IDs.
- Reuse the same context block in every chat session.
- Generate data in batches (`clients`, `pipelines`, `runs`, `alert_rules`) and validate before loading.

## 2) CHM Data Contract (Use Exactly)

Tables and key columns:

- `clients`: `id`, `name`, `is_active`, `created_at`, `updated_at`
- `pipelines`: `id`, `client_id`, `name`, `platform`, `external_id`, `pipeline_type`, `description`, `environment`, `is_active`, `created_at`, `updated_at`
- `runs`: `id`, `pipeline_id`, `external_run_id`, `status`, `started_at`, `finished_at`, `duration_seconds`, `rows_processed`, `error_message`, `status_reason`, `payload`, `ingested_at`, `created_at`, `updated_at`
- `alert_rules`: `id`, `client_id`, `pipeline_id`, `rule_type`, `threshold`, `window_minutes`, `channel`, `destination`, `is_enabled`, `created_at`, `updated_at`

Enum values (must match):

- `platform`: `airflow`, `dbt`, `cron`, `vendor_api`, `custom`
- `pipeline_type`: `ingestion`, `transform`, `quality`, `export`, `healthcheck`
- `run_status`: `running`, `success`, `failed`, `canceled`, `skipped`
- `rule_type`: `on_failure`, `failures_in_window`
- `channel`: `slack`, `email`, `webhook`

## 3) Recommended Repo Layout

```text
data/synthetic/v1/context/
data/synthetic/v1/base/
data/synthetic/v1/batches/
data/synthetic/v1/final/
```

Suggested files:

- `data/synthetic/v1/context/id_registry.csv`
- `data/synthetic/v1/context/generation_manifest.yaml`
- `data/synthetic/v1/base/clients.csv`
- `data/synthetic/v1/base/pipelines.csv`
- `data/synthetic/v1/batches/runs_YYYYMMDD_batch01.csv`
- `data/synthetic/v1/base/alert_rules.csv`

## 4) Session Bootstrap Prompt (Paste At Start Of Every Chat)

Use this first in each ChatGPT/Gemini session:

```markdown
You are generating synthetic data for a data engineering project.

Rules:
1. Follow schema and enums exactly.
2. Never invent parent IDs. Only use IDs provided in id_registry.csv.
3. Output only CSV in fenced code blocks. No prose.
4. Keep timestamps in UTC ISO 8601 format (e.g., 2026-02-21T16:00:00Z).
5. Maintain realistic relationships and variability.
6. For failed runs, include error_message and status_reason. For successful runs, leave both empty.
7. Ensure finished_at >= started_at when status is success/failed/canceled/skipped.

Schema summary:
- clients(id,name,is_active,created_at,updated_at)
- pipelines(id,client_id,name,platform,external_id,pipeline_type,description,environment,is_active,created_at,updated_at)
- runs(id,pipeline_id,external_run_id,status,started_at,finished_at,duration_seconds,rows_processed,error_message,status_reason,payload,ingested_at,created_at,updated_at)
- alert_rules(id,client_id,pipeline_id,rule_type,threshold,window_minutes,channel,destination,is_enabled,created_at,updated_at)

Enums:
- platform: airflow, dbt, cron, vendor_api, custom
- pipeline_type: ingestion, transform, quality, export, healthcheck
- run status: running, success, failed, canceled, skipped
- rule_type: on_failure, failures_in_window
- channel: slack, email, webhook
```

## 5) Prompt A: Generate Base Clients + Pipelines

Use once per dataset version:

```markdown
Generate two CSV files:
1) clients.csv with 12 clients
2) pipelines.csv with 40 pipelines

Requirements:
- Use realistic company names for clients.
- Mix active/inactive clients (about 80/20).
- For each pipeline, choose a realistic platform and pipeline_type.
- Environments should be one of: prod, staging, dev.
- external_id should be unique and human-readable.
- Ensure each pipeline references a valid client_id from clients.csv.
- Spread created_at dates over last 180 days.

ID rules:
- Create stable UUIDs and include them directly in the CSV.
- Do not change IDs once generated.

Output format:
- Return exactly two fenced CSV blocks:
  - first block: clients.csv
  - second block: pipelines.csv
```

After this prompt:

- Save files to:
  - `data/synthetic/v1/base/clients.csv`
  - `data/synthetic/v1/base/pipelines.csv`
- Build `id_registry.csv` from these two files (client and pipeline IDs).

## 6) Prompt B: Generate Runs Batch (Reusable Across Sessions)

Use repeatedly (daily/weekly batches):

```markdown
Using the provided pipelines from id_registry.csv, generate one runs batch CSV.

Batch request:
- Time range: 2026-01-01 to 2026-02-21 UTC
- Total rows: 1500
- Output file name suggestion: runs_20260221_batch01.csv

Behavior goals:
- Overall success rate around 82-90%
- Include one clear incident window (90-120 minutes) with failure spike for vendor_api pipelines
- Include one long-tail latency pattern on dbt transform pipelines
- Keep rows_processed realistic by pipeline type:
  - ingestion: 50k-5M
  - transform: 20k-2M
  - quality: 5k-500k
  - export: 10k-1M
  - healthcheck: 100-10k

Rules:
- status must be one of: running, success, failed, canceled, skipped
- running runs may have null finished_at/duration_seconds
- non-running runs must have finished_at and duration_seconds
- failed runs must include non-empty error_message and status_reason
- payload must be valid JSON object text
- pipeline_id must come from id_registry.csv
- external_run_id must be unique in this batch

Output:
- Return one fenced CSV block only (runs file).
```

## 7) Prompt C: Generate Alert Rules

Use once, then update occasionally:

```markdown
Generate alert_rules.csv for existing clients/pipelines from id_registry.csv.

Requirements:
- Create 25 rows.
- Mix rule_type: on_failure and failures_in_window.
- channel mix: slack/email/webhook.
- destination examples:
  - slack: #data-alerts, #ops-oncall
  - email: alerts@company.com
  - webhook: https://example.internal/hooks/chm-alerts
- is_enabled mostly true (about 85%).
- threshold/window_minutes should be realistic for failures_in_window.
- client_id and pipeline_id should reference existing IDs when present.
- created_at and updated_at in UTC.

Output:
- One fenced CSV block only.
```

## 8) Validation Checklist (Before Loading)

Required checks:

- Foreign keys:
  - every `pipelines.client_id` exists in `clients.id`
  - every `runs.pipeline_id` exists in `pipelines.id`
  - every non-null `alert_rules.client_id` exists in `clients.id`
  - every non-null `alert_rules.pipeline_id` exists in `pipelines.id`
- Enum values are valid.
- Timestamps are valid UTC strings.
- `finished_at >= started_at` where both exist.
- `duration_seconds >= 0`.
- `external_run_id` uniqueness per batch.
- `payload` is valid JSON object text.

## 9) Practical Flow (End-To-End)

1. Create `v1` folder and context files.
2. Run Prompt A once to create base entities.
3. Freeze `id_registry.csv` (do not change existing IDs).
4. Run Prompt B in any number of chat sessions to create run batches.
5. Run Prompt C for alert rules.
6. Validate all files.
7. Place approved files in:
   - `data/synthetic/v1/base/`
   - `data/synthetic/v1/batches/`
8. Load into Postgres, then refresh Metabase/Grafana dashboards.

## 10) Minimal Load Order

Load in this order to satisfy relationships:

1. `clients`
2. `pipelines`
3. `runs`
4. `alert_rules`

---

If you generate the CSV files using these prompts, drop them in the project and I can validate + ingest them for you.

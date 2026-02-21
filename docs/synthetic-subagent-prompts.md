# CHM Multi-Session Subagent Prompt Pack

Use these prompts in separate fresh Codex/ChatGPT/Gemini sessions.

## Current Status (Verified)

- `data/synthetic/v1/base/clients.csv` exists.
- `data/synthetic/v1/base/pipelines.csv` exists.
- `data/synthetic/v1/context/id_registry.csv` does not exist yet.
- Existing base CSVs are not CHM-contract compatible yet:
  - `clients.csv` uses `client_id,company_name,...` instead of `id,name,...,updated_at`.
  - `pipelines.csv` uses platform/type values outside CHM enums (for example `Apache Airflow`, `orchestration`).

## Session Order

1. Subagent A: Normalize base files to CHM schema.
2. Subagent B: Build `id_registry.csv`.
3. Subagent C: Generate runs batches from registry.
4. Subagent D: Generate alert rules from registry.
5. Subagent E: Validate all generated CSVs.
6. Subagent F (optional): Produce summary/stats for YouTube narrative.

## Common System Block (Paste At Top Of Every Session)

```markdown
You are a focused synthetic-data subagent.

Rules:
1. Use only files and context provided in this session.
2. Never assume memory from other chats.
3. Follow CHM schema and enum constraints exactly.
4. If required input is missing, stop and list only missing inputs.
5. Output only the requested artifact(s), in CSV code blocks unless I ask for prose.
6. Timestamps must be UTC ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`).

CHM schema:
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

## Prompt A: Base Normalizer (Use Existing Files)

Paste after Common System Block:

```markdown
Task:
Normalize the provided base files to CHM schema.

Input files:
- /Volumes/T7/CHM/data/synthetic/v1/base/clients.csv
- /Volumes/T7/CHM/data/synthetic/v1/base/pipelines.csv

Transform requirements:
- clients:
  - rename `client_id -> id`
  - rename `company_name -> name`
  - keep `is_active`, `created_at`
  - add `updated_at` equal to `created_at` plus 1-14 random days
- pipelines:
  - keep `id`, `client_id`, `external_id`, `is_active`, `created_at`
  - add/normalize fields to CHM columns:
    - `name`: short readable pipeline name from external_id
    - `platform`: map source labels to enum values only
    - `pipeline_type`: map source labels to enum values only
    - `environment`: must be one of `prod`, `staging`, `dev`
    - `description`: one sentence
    - `updated_at`: created_at plus 1-30 random days

Mapping rules:
- Platform mapping examples:
  - Apache Airflow -> airflow
  - dbt Cloud -> dbt
  - cron/k8s cron -> cron
  - vendor API connectors -> vendor_api
  - everything else -> custom
- Pipeline type mapping examples:
  - orchestration/scheduling -> healthcheck
  - ingest/ingestion/landing -> ingestion
  - transform/modeling -> transform
  - data quality/tests -> quality
  - export/reverse etl/serving -> export

Data integrity:
- Preserve existing IDs.
- `pipelines.client_id` must match an existing client `id`.
- Deduplicate exact duplicate rows if any.

Output:
- Return exactly two CSV blocks:
  1) normalized clients.csv
  2) normalized pipelines.csv
```

Save outputs to:

- `/Volumes/T7/CHM/data/synthetic/v1/base/clients.csv`
- `/Volumes/T7/CHM/data/synthetic/v1/base/pipelines.csv`

## Prompt B: Registry Builder

Paste after Common System Block:

```markdown
Task:
Create id_registry.csv from normalized base files.

Input files:
- /Volumes/T7/CHM/data/synthetic/v1/base/clients.csv
- /Volumes/T7/CHM/data/synthetic/v1/base/pipelines.csv

Output file:
- /Volumes/T7/CHM/data/synthetic/v1/context/id_registry.csv

Registry format:
- entity_type,entity_id,entity_name,parent_entity_id,parent_entity_name,platform,pipeline_type,environment,is_active,created_at

Rules:
- Add one row for every client:
  - entity_type=client
  - entity_id=clients.id
  - entity_name=clients.name
- Add one row for every pipeline:
  - entity_type=pipeline
  - entity_id=pipelines.id
  - entity_name=pipelines.name
  - parent_entity_id=pipelines.client_id
  - parent_entity_name=matching clients.name
  - include platform, pipeline_type, environment
- Keep deterministic ordering:
  - clients by name asc, then pipelines by client_name asc and pipeline name asc.

Output:
- Return one CSV block only (id_registry.csv).
```

## Prompt C: Runs Batch Generator (Reusable)

Paste after Common System Block:

```markdown
Task:
Generate a realistic runs batch using id_registry pipeline IDs.

Input:
- /Volumes/T7/CHM/data/synthetic/v1/context/id_registry.csv

Batch config:
- target rows: 2500
- window: 2025-11-01T00:00:00Z to 2026-02-21T23:59:59Z
- output filename: runs_20260221_batch01.csv

Behavior goals:
- overall success rate 83-90%
- include 2 incident arcs:
  1) vendor_api ingestion failure burst (90-120 min) in prod
  2) dbt transform latency degradation over 10 days
- include weekend traffic dips
- include at least 3 running rows near window end

Rules:
- pipeline_id must exist in registry where entity_type=pipeline
- status in: running, success, failed, canceled, skipped
- non-running statuses must have finished_at and duration_seconds
- failed must have error_message and status_reason
- success/skipped/canceled should have empty error_message and status_reason
- payload must be valid JSON object string
- external_run_id unique in this file, format: <pipeline_slug>-<yyyymmdd>-<seq>
- rows_processed ranges by pipeline_type:
  - ingestion: 50000-5000000
  - transform: 20000-2000000
  - quality: 5000-500000
  - export: 10000-1000000
  - healthcheck: 100-10000

Output:
- Return one CSV block only (runs batch).
```

Save output to:

- `/Volumes/T7/CHM/data/synthetic/v1/batches/runs_20260221_batch01.csv`

## Prompt D: Alert Rules Generator

Paste after Common System Block:

```markdown
Task:
Generate alert_rules.csv from registry with realistic targeting.

Input:
- /Volumes/T7/CHM/data/synthetic/v1/context/id_registry.csv

Config:
- rows: 35
- output: alert_rules.csv

Rules:
- id must be UUID.
- rule_type in: on_failure, failures_in_window
- channel in: slack, email, webhook
- destination examples:
  - slack: #data-alerts, #ops-oncall, #etl-reliability
  - email: data-alerts@example.com, oncall@example.com
  - webhook: https://ops.example.internal/hooks/chm-<team>
- for failures_in_window: set threshold 2-8 and window_minutes 10-60
- for on_failure: threshold/window_minutes may be empty
- is_enabled mostly true (~85%)
- client_id and pipeline_id should be populated for most rows
- referenced IDs must exist in registry
- created_at/updated_at within last 120 days

Output:
- Return one CSV block only (alert_rules.csv).
```

Save output to:

- `/Volumes/T7/CHM/data/synthetic/v1/base/alert_rules.csv`

## Prompt E: Validator Subagent

Paste after Common System Block:

```markdown
Task:
Validate CHM synthetic CSV set and return only an issue report CSV.

Input files:
- /Volumes/T7/CHM/data/synthetic/v1/base/clients.csv
- /Volumes/T7/CHM/data/synthetic/v1/base/pipelines.csv
- /Volumes/T7/CHM/data/synthetic/v1/context/id_registry.csv
- /Volumes/T7/CHM/data/synthetic/v1/batches/runs_20260221_batch01.csv
- /Volumes/T7/CHM/data/synthetic/v1/base/alert_rules.csv

Checks:
- required columns by file
- enum validity
- FK validity
- unique IDs and unique runs.external_run_id
- timestamp format and ordering (`finished_at >= started_at`)
- status/field consistency for runs
- payload JSON parseability

Output:
- If no issues: one CSV with header `status,message` and row `ok,validation passed`
- If issues: one CSV with header:
  `severity,file,row,column,rule,details`
```

## Prompt F: Storyline Summary (Optional, YouTube Narrative)

Paste after Common System Block:

```markdown
Task:
Create a concise analytics narrative from generated CSVs for dashboard storytelling.

Input files:
- clients.csv
- pipelines.csv
- runs batch file(s)
- alert_rules.csv

Output:
- Markdown with sections:
  1) dataset profile
  2) reliability KPIs
  3) top failing pipelines
  4) incident windows
  5) business-style insights

Constraints:
- Use computed facts only from input files.
- Keep under 300 words.
```

## Quick Operator Checklist

1. Run Prompt A first and overwrite base files.
2. Run Prompt B and create registry.
3. Run Prompt C/D to generate volume.
4. Run Prompt E and fix any issues.
5. Send me the generated files; I will ingest into Postgres and refresh Metabase/Grafana visuals.

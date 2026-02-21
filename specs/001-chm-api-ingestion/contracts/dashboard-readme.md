# Dashboard Query Contract Guide

This document describes how to use the SQL contract in
`specs/001-chm-api-ingestion/contracts/dashboard-queries.sql` for Grafana and Metabase.

## Query 1: Failures Over Time

- Purpose: Time-series panel for failed runs in a selected window.
- Parameters:
  - `:bucket` (`minute`, `hour`, `day`, `week`)
  - `:since` (timestamp, inclusive)
  - `:until` (timestamp, exclusive)
- Output columns:
  - `ts_bucket` (timestamp bucket)
  - `failed_runs` (count)
- Panel mapping:
  - Grafana: time-series visualization
  - Metabase: trend line chart

## Query 2: Latest Status Per Pipeline

- Purpose: Current operational snapshot by client and pipeline.
- Parameters: none
- Output columns:
  - `client_name`
  - `pipeline_name`
  - `platform`
  - `latest_status`
  - `last_run_time`
- Panel mapping:
  - Grafana: table panel for on-call triage
  - Metabase: table/model for ad-hoc filtering

## Query 3: Failure Counts Per Client (24h and 7d)

- Purpose: Rolling client-level failure summary.
- Parameters: none (`now()` anchored)
- Output columns:
  - `client_id`
  - `client_name`
  - `failed_24h`
  - `failed_7d`
- Panel mapping:
  - Grafana: bar chart by `failed_24h`
  - Metabase: table with sorting by rolling failures

## Query 4: Top Flaky Pipelines (Last 30 Days)

- Purpose: Identify unstable pipelines by failure frequency and rate.
- Parameters: none (`now()` anchored)
- Output columns:
  - `client_name`
  - `pipeline_name`
  - `platform`
  - `failure_count`
  - `total_runs`
  - `failure_rate`
- Panel mapping:
  - Grafana: table with top-N flaky pipelines
  - Metabase: ranked model for reliability reviews

## Query 5: Failure Rate By Platform

- Purpose: Compare platform reliability in a chosen time window.
- Parameters:
  - `:since` (timestamp, inclusive)
  - `:until` (timestamp, exclusive)
- Output columns:
  - `platform`
  - `failures`
  - `total_runs`
  - `failure_rate`
- Panel mapping:
  - Grafana: bar chart or stacked bar by platform
  - Metabase: breakout by platform for BI analysis

## Query 6: Run Duration Distribution (Optional)

- Purpose: Histogram source for runtime distribution.
- Parameters:
  - `:since` (timestamp, inclusive)
  - `:until` (timestamp, exclusive)
  - `:max_duration_seconds` (upper bound for buckets)
  - `:bucket_count` (number of buckets)
- Output columns:
  - `duration_bucket`
  - `run_count`
- Panel mapping:
  - Grafana: histogram panel
  - Metabase: bar chart on `duration_bucket`

## Usage Notes

- Time boundaries are UTC timestamps and should be passed explicitly from dashboard controls.
- Query 3 and Query 4 use `now()` internally; keep dashboard timezone set to UTC for consistent reads.
- Query 2 intentionally limits to active clients and active pipelines for current-state views.
- Query 6 excludes rows with `NULL` duration values.

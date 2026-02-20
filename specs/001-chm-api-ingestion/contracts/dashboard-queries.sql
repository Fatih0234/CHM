-- Dashboard query shapes for Grafana and Metabase
-- Parameters use :since, :until, :client_id placeholders where applicable.

-- 1) Failures over time (time series)
SELECT
  date_trunc(:bucket, COALESCE(r.finished_at, r.started_at, r.created_at)) AS ts_bucket,
  COUNT(*) AS failed_runs
FROM runs r
WHERE r.status = 'failed'
  AND COALESCE(r.finished_at, r.started_at, r.created_at) >= :since
  AND COALESCE(r.finished_at, r.started_at, r.created_at) < :until
GROUP BY 1
ORDER BY 1;

-- 2) Latest status per pipeline (table)
WITH latest_run AS (
  SELECT
    r.*,
    ROW_NUMBER() OVER (
      PARTITION BY r.pipeline_id
      ORDER BY r.started_at DESC NULLS LAST, r.finished_at DESC NULLS LAST, r.id DESC
    ) AS rn
  FROM runs r
)
SELECT
  c.name AS client_name,
  p.name AS pipeline_name,
  p.platform,
  lr.status AS latest_status,
  COALESCE(lr.started_at, lr.finished_at, lr.created_at) AS last_run_time
FROM pipelines p
JOIN clients c ON c.id = p.client_id
LEFT JOIN latest_run lr ON lr.pipeline_id = p.id AND lr.rn = 1
WHERE p.is_active = TRUE
  AND c.is_active = TRUE
ORDER BY c.name, p.name;

-- 3) Failure counts per client (24h/7d)
SELECT
  c.id AS client_id,
  c.name AS client_name,
  SUM(CASE WHEN r.status = 'failed'
            AND COALESCE(r.finished_at, r.started_at, r.created_at) >= now() - interval '24 hours'
           THEN 1 ELSE 0 END) AS failed_24h,
  SUM(CASE WHEN r.status = 'failed'
            AND COALESCE(r.finished_at, r.started_at, r.created_at) >= now() - interval '7 days'
           THEN 1 ELSE 0 END) AS failed_7d
FROM clients c
LEFT JOIN pipelines p ON p.client_id = c.id
LEFT JOIN runs r ON r.pipeline_id = p.id
GROUP BY c.id, c.name
ORDER BY failed_24h DESC, failed_7d DESC;

-- 4) Top flaky pipelines (last 30 days)
SELECT
  c.name AS client_name,
  p.name AS pipeline_name,
  p.platform,
  COUNT(*) FILTER (WHERE r.status = 'failed') AS failure_count,
  COUNT(*) AS total_runs,
  CASE
    WHEN COUNT(*) = 0 THEN 0
    ELSE ROUND((COUNT(*) FILTER (WHERE r.status = 'failed'))::numeric / COUNT(*), 4)
  END AS failure_rate
FROM pipelines p
JOIN clients c ON c.id = p.client_id
LEFT JOIN runs r ON r.pipeline_id = p.id
  AND COALESCE(r.finished_at, r.started_at, r.created_at) >= now() - interval '30 days'
GROUP BY c.name, p.name, p.platform
ORDER BY failure_count DESC, failure_rate DESC, total_runs DESC
LIMIT 20;

-- 5) Failure rate by platform
SELECT
  p.platform,
  COUNT(*) FILTER (WHERE r.status = 'failed') AS failures,
  COUNT(*) AS total_runs,
  CASE
    WHEN COUNT(*) = 0 THEN 0
    ELSE ROUND((COUNT(*) FILTER (WHERE r.status = 'failed'))::numeric / COUNT(*), 4)
  END AS failure_rate
FROM pipelines p
LEFT JOIN runs r ON r.pipeline_id = p.id
WHERE COALESCE(r.finished_at, r.started_at, r.created_at) >= :since
  AND COALESCE(r.finished_at, r.started_at, r.created_at) < :until
GROUP BY p.platform
ORDER BY failure_rate DESC;

-- 6) Run duration distribution (optional)
SELECT
  width_bucket(r.duration_seconds, 0, :max_duration_seconds, :bucket_count) AS duration_bucket,
  COUNT(*) AS run_count
FROM runs r
WHERE r.duration_seconds IS NOT NULL
  AND COALESCE(r.finished_at, r.started_at, r.created_at) >= :since
  AND COALESCE(r.finished_at, r.started_at, r.created_at) < :until
GROUP BY duration_bucket
ORDER BY duration_bucket;

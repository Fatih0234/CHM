SELECT 'CREATE DATABASE metabase_app'
WHERE NOT EXISTS (
  SELECT
  FROM pg_database
  WHERE datname = 'metabase_app'
)\gexec

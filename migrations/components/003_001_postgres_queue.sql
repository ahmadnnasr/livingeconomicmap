CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_name TEXT NOT NULL,
    job_type TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'retry', 'running', 'completed', 'dead_letter', 'cancelled')
    ),
    priority INTEGER NOT NULL DEFAULT 100,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    leased_until TIMESTAMPTZ,
    worker_id TEXT,
    dedupe_key TEXT,
    parent_job_id UUID REFERENCES jobs(job_id),
    trace_id UUID NOT NULL DEFAULT gen_random_uuid(),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_queue_dedupe
ON jobs(queue_name, dedupe_key)
WHERE dedupe_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_jobs_claim
ON jobs(queue_name, status, available_at, priority, created_at)
WHERE status IN ('pending', 'retry');

CREATE INDEX IF NOT EXISTS idx_jobs_running_lease
ON jobs(status, leased_until)
WHERE status = 'running';

CREATE TABLE IF NOT EXISTS job_attempts (
    attempt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(job_id),
    worker_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    error_message TEXT,
    output_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_job_attempts_job
ON job_attempts(job_id, started_at DESC);

CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    worker_type TEXT NOT NULL,
    queue_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('online', 'stale', 'offline')),
    hostname TEXT,
    process_id INTEGER,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_workers_heartbeat
ON workers(status, heartbeat_at);

CREATE TABLE IF NOT EXISTS dead_letter_jobs (
    dead_letter_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_job_id UUID NOT NULL,
    queue_name TEXT NOT NULL,
    job_type TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    trace_id UUID NOT NULL,
    failure_count INTEGER NOT NULL,
    last_error TEXT NOT NULL,
    moved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    replayed_job_id UUID
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    workflow_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_name TEXT NOT NULL,
    trace_id UUID NOT NULL DEFAULT gen_random_uuid(),
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    input_json JSONB NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    workflow_step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID NOT NULL REFERENCES workflow_runs(workflow_run_id),
    step_name TEXT NOT NULL,
    job_id UUID REFERENCES jobs(job_id),
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'skipped')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    output_json JSONB,
    UNIQUE(workflow_run_id, step_name)
);

CREATE TABLE IF NOT EXISTS schedules (
    schedule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    queue_name TEXT NOT NULL,
    job_type TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    cron_expression TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'America/New_York',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    dedupe_template TEXT,
    last_enqueued_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_schedules_due
ON schedules(is_enabled, next_run_at)
WHERE is_enabled = TRUE;

CREATE TABLE IF NOT EXISTS queue_metrics_hourly (
    metric_hour TIMESTAMPTZ NOT NULL,
    queue_name TEXT NOT NULL,
    completed_jobs BIGINT NOT NULL DEFAULT 0,
    failed_jobs BIGINT NOT NULL DEFAULT 0,
    dead_letter_jobs BIGINT NOT NULL DEFAULT 0,
    average_runtime_ms DOUBLE PRECISION,
    p95_runtime_ms DOUBLE PRECISION,
    maximum_queue_age_seconds DOUBLE PRECISION,
    PRIMARY KEY(metric_hour, queue_name)
);

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS jobs_touch_updated_at ON jobs;
CREATE TRIGGER jobs_touch_updated_at
BEFORE UPDATE ON jobs
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS schedules_touch_updated_at ON schedules;
CREATE TRIGGER schedules_touch_updated_at
BEFORE UPDATE ON schedules
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

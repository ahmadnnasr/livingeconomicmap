PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    queue_name TEXT NOT NULL,
    job_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    available_at TEXT NOT NULL,
    leased_until TEXT,
    worker_id TEXT,
    dedupe_key TEXT,
    parent_job_id TEXT,
    trace_id TEXT NOT NULL,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(queue_name, dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_jobs_claim
ON jobs(queue_name, status, available_at, priority, created_at);

CREATE TABLE IF NOT EXISTS job_attempts (
    attempt_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    error_message TEXT,
    output_json TEXT,
    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    worker_type TEXT NOT NULL,
    queue_name TEXT NOT NULL,
    status TEXT NOT NULL,
    hostname TEXT,
    process_id INTEGER,
    started_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS dead_letter_jobs (
    dead_letter_id TEXT PRIMARY KEY,
    original_job_id TEXT NOT NULL,
    queue_name TEXT NOT NULL,
    job_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    failure_count INTEGER NOT NULL,
    last_error TEXT NOT NULL,
    moved_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    schedule_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    queue_name TEXT NOT NULL,
    job_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    timezone TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    dedupe_template TEXT,
    last_enqueued_at TEXT,
    next_run_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    workflow_run_id TEXT PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    status TEXT NOT NULL,
    input_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    workflow_step_id TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    job_id TEXT,
    status TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    output_json TEXT,
    FOREIGN KEY(workflow_run_id) REFERENCES workflow_runs(workflow_run_id),
    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);

ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS queue TEXT;

UPDATE jobs
SET queue = job_type
WHERE queue IS NULL;

ALTER TABLE jobs
ALTER COLUMN queue SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_jobs_queue_status_created
ON jobs(queue, status, created_at);

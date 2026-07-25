CLAIM_JOB_SQL = """
WITH candidate AS (
    SELECT job_id
    FROM jobs
    WHERE queue_name = %(queue_name)s
      AND status IN ('pending', 'retry')
      AND available_at <= NOW()
      AND (leased_until IS NULL OR leased_until <= NOW())
    ORDER BY priority ASC, created_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE jobs AS j
SET status = 'running',
    worker_id = %(worker_id)s,
    leased_until = NOW() + (%(lease_seconds)s || ' seconds')::interval,
    attempt_count = attempt_count + 1
FROM candidate
WHERE j.job_id = candidate.job_id
RETURNING j.*;
"""

INSERT_ATTEMPT_SQL = """
INSERT INTO job_attempts(job_id, worker_id, status)
VALUES (%(job_id)s, %(worker_id)s, 'running')
RETURNING attempt_id;
"""

COMPLETE_JOB_SQL = """
UPDATE jobs
SET status='completed',
    leased_until=NULL,
    worker_id=%(worker_id)s
WHERE job_id=%(job_id)s
  AND worker_id=%(worker_id)s
  AND status='running'
RETURNING job_id;
"""

COMPLETE_ATTEMPT_SQL = """
UPDATE job_attempts
SET status='completed',
    finished_at=NOW(),
    output_json=%(output_json)s::jsonb
WHERE job_id=%(job_id)s
  AND worker_id=%(worker_id)s
  AND status='running';
"""

RETRY_JOB_SQL = """
UPDATE jobs
SET status='retry',
    available_at=NOW() + (%(delay_seconds)s || ' seconds')::interval,
    leased_until=NULL,
    worker_id=NULL,
    last_error=%(error_message)s
WHERE job_id=%(job_id)s
RETURNING job_id;
"""

DEAD_LETTER_JOB_SQL = """
WITH moved AS (
    UPDATE jobs
    SET status='dead_letter',
        leased_until=NULL,
        last_error=%(error_message)s
    WHERE job_id=%(job_id)s
    RETURNING *
)
INSERT INTO dead_letter_jobs(
    original_job_id, queue_name, job_type, payload_json,
    trace_id, failure_count, last_error
)
SELECT job_id, queue_name, job_type, payload_json,
       trace_id, attempt_count, %(error_message)s
FROM moved
RETURNING dead_letter_id;
"""

RECOVER_EXPIRED_LEASES_SQL = """
UPDATE jobs
SET status='retry',
    worker_id=NULL,
    leased_until=NULL,
    available_at=NOW(),
    last_error='Worker lease expired'
WHERE status='running'
  AND leased_until < NOW()
RETURNING job_id;
"""

CLAIM_DUE_SCHEDULE_SQL = """
SELECT *
FROM schedules
WHERE is_enabled = TRUE
  AND next_run_at <= NOW()
ORDER BY next_run_at
FOR UPDATE SKIP LOCKED
LIMIT %(limit)s;
"""

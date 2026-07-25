QUEUE_DEPTH_SQL = """
SELECT queue_name, status, COUNT(*) AS jobs
FROM jobs
GROUP BY queue_name, status
ORDER BY queue_name, status;
"""

OLDEST_PENDING_SQL = """
SELECT queue_name,
       EXTRACT(EPOCH FROM (NOW() - MIN(created_at))) AS oldest_seconds
FROM jobs
WHERE status IN ('pending', 'retry')
GROUP BY queue_name
ORDER BY oldest_seconds DESC;
"""

WORKER_HEALTH_SQL = """
SELECT worker_id, worker_type, queue_name, status,
       EXTRACT(EPOCH FROM (NOW() - heartbeat_at)) AS heartbeat_age_seconds
FROM workers
ORDER BY heartbeat_age_seconds DESC;
"""

DEAD_LETTER_SUMMARY_SQL = """
SELECT queue_name, job_type, COUNT(*) AS failures,
       MAX(moved_at) AS latest_failure
FROM dead_letter_jobs
GROUP BY queue_name, job_type
ORDER BY failures DESC;
"""

ATTEMPT_LATENCY_SQL = """
SELECT j.queue_name,
       AVG(EXTRACT(EPOCH FROM (a.finished_at - a.started_at)) * 1000)
           AS average_runtime_ms,
       PERCENTILE_CONT(0.95) WITHIN GROUP (
           ORDER BY EXTRACT(EPOCH FROM (a.finished_at - a.started_at)) * 1000
       ) AS p95_runtime_ms
FROM job_attempts a
JOIN jobs j ON j.job_id = a.job_id
WHERE a.status='completed'
  AND a.finished_at >= NOW() - INTERVAL '24 hours'
GROUP BY j.queue_name;
"""

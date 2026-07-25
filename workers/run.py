from __future__ import annotations

import argparse
import os
import signal
import socket
import time
import traceback

from app.db import connection


running = True


def stop(*_args) -> None:
    global running
    running = False


def worker_name(queue_name: str) -> str:
    configured = os.getenv("WORKER_NAME")

    if configured:
        return configured

    return f"{queue_name}-{socket.gethostname()}"


def claim_next_job(queue_name: str, worker: str):
    """
    Atomically claim the oldest queued job for this worker queue.
    """
    with connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            WITH next_job AS (
                SELECT job_id
                FROM jobs
                WHERE queue = %s
                  AND status = 'queued'
                  AND run_after <= NOW()
                ORDER BY priority DESC, created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE jobs
            SET
                status = 'running',
                locked_by = %s,
                locked_at = NOW(),
                started_at = NOW(),
                attempts = attempts + 1,
                updated_at = NOW()
            WHERE job_id = (
                SELECT job_id
                FROM next_job
            )
            RETURNING
                job_id,
                job_type,
                payload
            """,
            (
                queue_name,
                worker,
            ),
        )

        row = cur.fetchone()
        conn.commit()

    return row


def mark_completed(job_id) -> None:
    with connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE jobs
            SET
                status = 'completed',
                finished_at = NOW(),
                updated_at = NOW(),
                last_error = NULL
            WHERE job_id = %s
            """,
            (job_id,),
        )

        conn.commit()


def mark_failed(job_id, error: str) -> None:
    with connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE jobs
            SET
                status = 'failed',
                finished_at = NOW(),
                updated_at = NOW(),
                last_error = %s
            WHERE job_id = %s
            """,
            (
                error[:5000],
                job_id,
            ),
        )

        conn.commit()


def process_job(job_type: str, payload) -> None:
    """
    Temporary lifecycle test.

    This confirms queued -> running -> completed before adding live FRED work.
    """
    if job_type != "fred_ingestion":
        raise NotImplementedError(
            f"No test handler registered for job_type='{job_type}'."
        )

    time.sleep(2)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "queue",
        choices=[
            "ingestion",
            "reasoning",
            "publication",
            "maintenance",
        ],
    )

    args = parser.parse_args()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    name = worker_name(args.queue)

    print(
        f"worker_started queue={args.queue} worker={name}",
        flush=True,
    )

    while running:
        try:
            row = claim_next_job(
                queue_name=args.queue,
                worker=name,
            )

            if row is None:
                time.sleep(5)
                continue

            job_id, job_type, payload = row

            print(
                f"job_claimed id={job_id} "
                f"queue={args.queue} "
                f"type={job_type}",
                flush=True,
            )

            try:
                process_job(
                    job_type=job_type,
                    payload=payload,
                )

                mark_completed(job_id)

                print(
                    f"job_completed id={job_id}",
                    flush=True,
                )

            except Exception:
                error = traceback.format_exc()

                mark_failed(
                    job_id=job_id,
                    error=error,
                )

                print(
                    f"job_failed id={job_id}",
                    flush=True,
                )

        except Exception:
            print(
                traceback.format_exc(),
                flush=True,
            )
            time.sleep(5)

    print(
        f"worker_stopped queue={args.queue} worker={name}",
        flush=True,
    )


if __name__ == "__main__":
    main()

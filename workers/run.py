from __future__ import annotations

import argparse
import os
import signal
import socket
import time
import traceback

from lemp_queue.repository import Job, JobRepository


running = True


def stop(*_args) -> None:
    global running
    running = False


def worker_name(queue_name: str) -> str:
    configured_name = os.getenv("WORKER_NAME")

    if configured_name:
        return configured_name

    return f"{queue_name}-{socket.gethostname()}"


def handle_job(queue_name: str, job: Job) -> None:
    """
    Temporary dispatcher.

    Real handlers, including fred_ingestion, will be added in the next commit.
    """
    raise NotImplementedError(
        f"No handler registered for "
        f"queue='{queue_name}', "
        f"job_type='{job.job_type}'."
    )


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

    repository = JobRepository()
    name = worker_name(args.queue)

    print(
        f"worker_started queue={args.queue} worker={name}",
        flush=True,
    )

    while running:
        job = repository.claim_next_job(
            queue=args.queue,
            worker=name,
        )

        if job is None:
            time.sleep(5)
            continue

        print(
            f"job_claimed id={job.id} "
            f"queue={args.queue} "
            f"type={job.job_type} "
            f"worker={name}",
            flush=True,
        )

        try:
            handle_job(args.queue, job)

            repository.mark_completed(job.id)

            print(
                f"job_completed id={job.id}",
                flush=True,
            )

        except Exception as exc:
            error_details = traceback.format_exc()

            repository.mark_failed(
                job.id,
                error_details,
            )

            print(
                f"job_failed id={job.id} error={exc}",
                flush=True,
            )

    print(
        f"worker_stopped queue={args.queue} worker={name}",
        flush=True,
    )


if __name__ == "__main__":
    main()

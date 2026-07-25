from __future__ import annotations

import argparse
import os
import signal
import socket
import time
import traceback

from lemp_queue.repository import JobRepository


running = True


def stop(*_):
    global running
    running = False


def worker_name(queue_name: str) -> str:
    configured = os.getenv("WORKER_NAME")

    if configured:
        return configured

    return f"{queue_name}-{socket.gethostname()}"


def handle_job(queue_name: str, job) -> None:
    """
    Temporary job dispatcher.

    FRED execution is added in the next commit.
    For now, claimed jobs fail clearly instead of being silently ignored.
    """
    raise RuntimeError(
        f"No handler configured yet for queue={queue_name}, "
        f"job_type={job.job_type}"
    )


def main():
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
            job_type=args.queue,
            worker=name,
        )

        if job is None:
            time.sleep(5)
            continue

        print(
            f"job_claimed id={job.id} "
            f"type={job.job_type} worker={name}",
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
            repository.mark_failed(
                job.id,
                traceback.format_exc(),
            )

            print(
                f"job_failed id={job.id} error={exc}",
                flush=True,
            )

    print("worker_stopped", flush=True)


if __name__ == "__main__":
    main()

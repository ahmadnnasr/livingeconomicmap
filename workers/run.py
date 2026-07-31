from __future__ import annotations

import argparse
import os
import signal
import socket
import time
import traceback
from typing import Any

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


def claim_next_job(
    queue_name: str,
    worker: str,
):
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
                attempts = attempts + 1,
                updated_at = NOW(),
                last_error = NULL
            WHERE job_id = (
                SELECT job_id
                FROM next_job
            )
            RETURNING
                job_id,
                job_type,
                payload,
                attempts,
                max_attempts
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
                locked_by = NULL,
                locked_at = NULL,
                updated_at = NOW(),
                last_error = NULL
            WHERE job_id = %s
            """,
            (job_id,),
        )

        conn.commit()


def mark_failed(
    job_id,
    error: str,
    attempts: int,
    max_attempts: int,
) -> None:
    with connection() as conn:
        cur = conn.cursor()

        if attempts < max_attempts:
            cur.execute(
                """
                UPDATE jobs
                SET
                    status = 'queued',
                    locked_by = NULL,
                    locked_at = NULL,
                    run_after = NOW() + INTERVAL '60 seconds',
                    updated_at = NOW(),
                    last_error = %s
                WHERE job_id = %s
                """,
                (
                    error[:5000],
                    job_id,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE jobs
                SET
                    status = 'failed',
                    locked_by = NULL,
                    locked_at = NULL,
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


def process_ingestion_job(
    job_type: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if job_type != "fred_ingestion":
        raise NotImplementedError(
            f"No ingestion handler registered for job_type='{job_type}'."
        )

    from lemp_macro.live_fred import ingest_priority_series

    payload = payload or {}

    lookback_days = int(
        payload.get(
            "lookback_days",
            2200,
        )
    )

    return ingest_priority_series(
        lookback_days=lookback_days,
    )


def process_reasoning_job(
    job_type: str,
    payload: dict[str, Any] | None,
    job_id: str,
) -> dict[str, Any]:
    if job_type != "rates_liquidity_reasoning":
        raise NotImplementedError(
            f"No reasoning handler registered for job_type='{job_type}'."
        )

    from datetime import date as _date

    from lemp_rates.adapters import SimpleJob, load_priors, load_signals, persist_snapshot
    from lemp_rates.queue_handlers import RatesLiquidityReasoningHandler

    payload = payload or {}
    as_of_date = payload.get("as_of_date") or _date.today().isoformat()

    handler = RatesLiquidityReasoningHandler(
        load_signals=load_signals,
        persist_snapshot=persist_snapshot,
        publish_event=lambda *_args, **_kwargs: None,
        load_priors=load_priors,
    )

    job = SimpleJob(
        payload={"as_of_date": as_of_date},
        trace_id=str(job_id),
    )

    return handler(job)


def process_publication_job(
    job_type: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = payload or {}

    from datetime import date as _date

    as_of_date = payload.get("as_of_date") or _date.today().isoformat()

    if job_type == "daily_brief":
        from lemp_daily.adapters import load_context, persist_publication
        from lemp_daily.briefing import DailyBriefGenerator

        context = load_context(as_of_date)
        generator = DailyBriefGenerator()
        brief = generator.generate(context)
        markdown = generator.render_markdown(brief)
        publication_id = persist_publication(brief, markdown)

        return {
            "publication_id": publication_id,
            "headline": brief.headline,
        }

    if job_type == "narrative_synthesis":
        from lemp_daily.adapters import load_snapshot, persist_narrative
        from lemp_daily.narrative import generate_narrative

        snapshot = load_snapshot()
        result = generate_narrative(
            snapshot["macro"],
            snapshot["beliefs"],
            snapshot["regimes"],
        )
        publication_id = persist_narrative(
            as_of_date,
            result["narrative"],
            result["glossary"],
        )

        return {
            "publication_id": publication_id,
        }

    raise NotImplementedError(
        f"No publication handler registered for job_type='{job_type}'."
    )


def process_job(
    queue_name: str,
    job_type: str,
    payload: dict[str, Any] | None,
    job_id: str,
) -> dict[str, Any]:
    if queue_name == "ingestion":
        return process_ingestion_job(
            job_type=job_type,
            payload=payload,
        )

    if queue_name == "reasoning":
        return process_reasoning_job(
            job_type=job_type,
            payload=payload,
            job_id=job_id,
        )

    if queue_name == "publication":
        return process_publication_job(
            job_type=job_type,
            payload=payload,
        )

    raise NotImplementedError(
        f"No handler registered for "
        f"queue='{queue_name}', "
        f"job_type='{job_type}'."
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

            (
                job_id,
                job_type,
                payload,
                attempts,
                max_attempts,
            ) = row

            print(
                f"job_claimed "
                f"id={job_id} "
                f"queue={args.queue} "
                f"type={job_type} "
                f"attempt={attempts}/{max_attempts}",
                flush=True,
            )

            try:
                result = process_job(
                    queue_name=args.queue,
                    job_type=job_type,
                    payload=payload,
                    job_id=job_id,
                )

                mark_completed(job_id)

                print(
                    f"job_completed "
                    f"id={job_id} "
                    f"type={job_type} "
                    f"result={result}",
                    flush=True,
                )

            except Exception:
                error = traceback.format_exc()

                mark_failed(
                    job_id=job_id,
                    error=error,
                    attempts=attempts,
                    max_attempts=max_attempts,
                )

                print(
                    f"job_processing_failed "
                    f"id={job_id} "
                    f"type={job_type} "
                    f"attempt={attempts}/{max_attempts}\n"
                    f"{error}",
                    flush=True,
                )

        except Exception:
            print(
                "worker_polling_error\n"
                + traceback.format_exc(),
                flush=True,
            )

            time.sleep(5)

    print(
        f"worker_stopped queue={args.queue} worker={name}",
        flush=True,
    )


if __name__ == "__main__":
    main()

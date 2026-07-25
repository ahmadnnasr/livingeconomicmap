from __future__ import annotations

import json

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import require_auth
from app.db import connection
from app.queries import dashboard_state
from app.settings import get_settings


app = FastAPI(
    title="Living Economic Map",
    version="3.51",
)

templates = Jinja2Templates(directory="templates")

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


@app.get("/health")
def health():
    try:
        with connection() as conn:
            conn.cursor().execute("SELECT 1")

        database_status = "ok"

    except Exception as exc:
        return JSONResponse(
            {
                "status": "degraded",
                "database": str(exc),
            },
            status_code=503,
        )

    return {
        "status": "ok",
        "database": database_status,
        "environment": get_settings().app_env,
    }


@app.get(
    "/",
    response_class=HTMLResponse,
)
def dashboard(
    request: Request,
    user=Depends(require_auth),
):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "state": dashboard_state(),
            "settings": get_settings(),
            "user": user,
        },
    )


@app.get("/api/state")
def api_state(
    user=Depends(require_auth),
):
    return dashboard_state()


@app.post("/admin/ingest/fred")
def run_fred_ingestion(
    user=Depends(require_auth),
):
    """
    Queue a FRED ingestion job and immediately return to the dashboard.
    """
    with connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT job_id
            FROM jobs
            WHERE queue = %s
              AND job_type = %s
              AND status IN ('queued', 'running')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (
                "ingestion",
                "fred_ingestion",
            ),
        )

        existing_job = cur.fetchone()

        if existing_job is None:
            cur.execute(
                """
                INSERT INTO jobs (
                    queue,
                    job_type,
                    payload,
                    status,
                    priority,
                    attempts,
                    max_attempts,
                    run_after
                )
                VALUES (
                    %s,
                    %s,
                    %s::jsonb,
                    'queued',
                    100,
                    0,
                    5,
                    NOW()
                )
                """,
                (
                    "ingestion",
                    "fred_ingestion",
                    json.dumps({}),
                ),
            )

            conn.commit()

    return RedirectResponse(
        url="/",
        status_code=303,
    )

from __future__ import annotations

import json

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import require_auth
from app.db import connection
from app.formatting import fmt_et, fmt_macro, fmt_pct
from app.queries import dashboard_state, macro_series_history, public_conditions
from app.settings import get_settings


app = FastAPI(
    title="Living Economic Map",
    version="3.51",
)

# Scoped to browser-side reads of /api/public-conditions only — every other
# route stays same-origin / HTTP-Basic protected as before.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["X-LEM-Key"],
)

templates = Jinja2Templates(directory="templates")
templates.env.filters["fmt_macro"] = fmt_macro
templates.env.filters["fmt_pct"] = fmt_pct
templates.env.filters["fmt_et"] = fmt_et

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


def require_public_key(x_lem_key: str | None = Header(default=None)):
    """
    Separate, low-privilege check for the public endpoint. Deliberately NOT
    the same credentials as require_auth (those also gate /admin/ingest/fred).
    If PUBLIC_CONDITIONS_KEY is unset, the endpoint is open — set it in
    Railway once you're ready to lock this down.
    """
    settings = get_settings()
    if settings.public_conditions_key and x_lem_key != settings.public_conditions_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-LEM-Key")
    return True


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


@app.get("/api/macro/{series_id}/history")
def macro_history(
    series_id: str,
    user=Depends(require_auth),
):
    """Full history for one series, for the click-to-chart feature on the
    dashboard. Same auth as the dashboard itself — not the CORS-enabled
    public-conditions route."""
    return macro_series_history(series_id)


@app.get("/api/state")
def api_state(
    user=Depends(require_auth),
):
    return dashboard_state()


@app.get("/api/public-conditions")
def api_public_conditions(
    _ok=Depends(require_public_key),
):
    """
    Read-only, CORS-enabled subset of dashboard_state() for external
    consumers (e.g. the Analog Archive artifact). No admin actions live
    behind this key.
    """
    return public_conditions()


@app.post("/admin/run/reasoning")
def run_reasoning(
    user=Depends(require_auth),
):
    """
    Queue a rates/liquidity belief+regime reasoning job and immediately
    return to the dashboard. Mirrors run_fred_ingestion's dedupe-by-existing-
    job pattern so repeated clicks don't stack up duplicate runs.
    """
    from datetime import date as _date

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
                "reasoning",
                "rates_liquidity_reasoning",
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
                    "reasoning",
                    "rates_liquidity_reasoning",
                    json.dumps({"as_of_date": _date.today().isoformat()}),
                ),
            )
            conn.commit()
    return RedirectResponse(
        url="/",
        status_code=303,
    )


@app.post("/admin/run/publication")
def run_publication(
    user=Depends(require_auth),
):
    """
    Queue a daily-brief publication job. Gmail delivery is deliberately
    NOT triggered here — gmail_delivery_enabled is false, and lemp_gmail's
    provider is an unimplemented stub, so this only ever writes a
    publications row, never attempts to send anything.
    """
    from datetime import date as _date

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
                "publication",
                "daily_brief",
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
                    "publication",
                    "daily_brief",
                    json.dumps({"as_of_date": _date.today().isoformat()}),
                ),
            )
            conn.commit()
    return RedirectResponse(
        url="/",
        status_code=303,
    )


@app.post("/admin/run/narrative")
def run_narrative(
    user=Depends(require_auth),
):
    """
    Queue a narrative-synthesis job — calls the real Anthropic API
    server-side using ANTHROPIC_API_KEY. Fails loudly (job marked
    'failed', error visible in Postgres) if that key isn't set.
    """
    from datetime import date as _date

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
                "publication",
                "narrative_synthesis",
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
                    "publication",
                    "narrative_synthesis",
                    json.dumps({"as_of_date": _date.today().isoformat()}),
                ),
            )
            conn.commit()
    return RedirectResponse(
        url="/",
        status_code=303,
    )


@app.post("/admin/run/asset-analysis")
def run_asset_analysis(
    user=Depends(require_auth),
):
    """
    Queue a historical-analog asset analysis job — calls the real
    Anthropic API server-side with web search enabled, using
    ANTHROPIC_API_KEY. Same key as narrative synthesis; fails loudly
    (job marked 'failed', error visible in Postgres) if unset.
    """
    from datetime import date as _date

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
                "publication",
                "asset_regime_analysis",
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
                    "publication",
                    "asset_regime_analysis",
                    json.dumps({"as_of_date": _date.today().isoformat()}),
                ),
            )
            conn.commit()
    return RedirectResponse(
        url="/",
        status_code=303,
    )


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

from __future__ import annotations
 
import json
 
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
 
from app.auth import require_auth
from app.db import connection
from app.formatting import fmt_macro, fmt_pct
from app.queries import dashboard_state, public_conditions
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
 

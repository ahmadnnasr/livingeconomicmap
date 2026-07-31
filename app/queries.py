import json as _json

from app.db import fetch_all


def safe(query, params=()):
    try:
        return fetch_all(query, params)
    except Exception:
        return []


def latest_narrative():
    """
    Returns the most recent narrative_synthesis publication as a plain
    dict with `narrative` (str) and `glossary` (dict) pulled out of the
    JSONB payload, or None if none exists yet. Normalizes payload whether
    psycopg hands it back as a dict (typical) or a raw string.
    """
    rows = safe(
        """
        SELECT payload, created_at FROM publications
        WHERE publication_type = 'narrative_synthesis'
        ORDER BY created_at DESC LIMIT 1
        """
    )
    if not rows:
        return None

    payload = rows[0]["payload"]
    if isinstance(payload, str):
        payload = _json.loads(payload)

    return {
        "narrative": payload.get("narrative", ""),
        "glossary": payload.get("glossary", {}),
        "created_at": rows[0]["created_at"],
    }


def latest_asset_analysis():
    """
    Returns the most recent asset_regime_analysis publication with its
    historical analogs, avoid/favored asset lists, and synthesis pulled
    out of the JSONB payload, or None if none exists yet.
    """
    rows = safe(
        """
        SELECT payload, created_at FROM publications
        WHERE publication_type = 'asset_regime_analysis'
        ORDER BY created_at DESC LIMIT 1
        """
    )
    if not rows:
        return None

    payload = rows[0]["payload"]
    if isinstance(payload, str):
        payload = _json.loads(payload)

    return {
        "historical_analogs": payload.get("historical_analogs", []),
        "assets_to_avoid": payload.get("assets_to_avoid", []),
        "assets_favored": payload.get("assets_favored", []),
        "synthesis": payload.get("synthesis", ""),
        "created_at": rows[0]["created_at"],
    }


def public_conditions():
    """
    Curated, read-only subset of dashboard_state() safe to expose outside
    the authenticated dashboard: latest macro observations, the current
    regime, and top beliefs. Deliberately excludes jobs, publications,
    gmail deliveries, and ingestion run internals.
    """
    return {
        "macro": safe(
            """
            SELECT DISTINCT ON (s.series_id)
                s.series_id, s.title, s.category, s.units, s.interpretation,
                o.observation_date, o.value
            FROM macro_series s
            JOIN macro_observations o ON o.series_id=s.series_id
            ORDER BY s.series_id, o.observation_date DESC, o.retrieved_at DESC
            """
        ),
        "regime": safe(
            """
            SELECT regime_key, probability, as_of FROM (
                SELECT DISTINCT ON (regime_key) regime_key, probability, as_of
                FROM regimes ORDER BY regime_key, as_of DESC
            ) t ORDER BY probability DESC LIMIT 1
            """
        ),
        "beliefs": safe(
            """
            SELECT belief_key, probability, confidence, updated_at FROM (
                SELECT DISTINCT ON (belief_key) belief_key, probability, confidence, updated_at
                FROM beliefs ORDER BY belief_key, updated_at DESC
            ) t ORDER BY updated_at DESC LIMIT 8
            """
        ),
    }


def last_run_times():
    """
    Most recent timestamp for each of the four triggerable actions,
    regardless of whether that run succeeded — this answers "when did I
    last click this button", not "when did it last succeed". Each is a
    single scalar query against the table that action actually writes to.
    """
    ingestion = safe(
        "SELECT started_at FROM macro_ingestion_runs ORDER BY started_at DESC LIMIT 1"
    )
    reasoning = safe("SELECT MAX(updated_at) AS ts FROM beliefs")
    publication = safe(
        "SELECT MAX(created_at) AS ts FROM publications WHERE publication_type = 'daily_brief'"
    )
    narrative = safe(
        "SELECT MAX(created_at) AS ts FROM publications WHERE publication_type = 'narrative_synthesis'"
    )
    asset_analysis = safe(
        "SELECT MAX(created_at) AS ts FROM publications WHERE publication_type = 'asset_regime_analysis'"
    )
    return {
        "ingestion": ingestion[0]["started_at"] if ingestion else None,
        "reasoning": reasoning[0]["ts"] if reasoning else None,
        "publication": publication[0]["ts"] if publication else None,
        "narrative": narrative[0]["ts"] if narrative else None,
        "asset_analysis": asset_analysis[0]["ts"] if asset_analysis else None,
    }


def macro_series_history(series_id: str):
    """Full observation history for one series, deduped the same way as
    every other macro query (latest retrieved_at per date), plus its
    title/category/units from macro_series for the chart's labels."""
    meta_rows = safe(
        "SELECT title, category, units, interpretation FROM macro_series WHERE series_id = %s",
        (series_id,),
    )
    obs_rows = safe(
        """
        SELECT DISTINCT ON (observation_date) observation_date, value
        FROM macro_observations
        WHERE series_id = %s
        ORDER BY observation_date, retrieved_at DESC
        """,
        (series_id,),
    )
    meta = meta_rows[0] if meta_rows else {}
    return {
        "series_id": series_id,
        "title": meta.get("title", series_id),
        "category": meta.get("category"),
        "units": meta.get("units"),
        "interpretation": meta.get("interpretation"),
        "observations": [
            {"date": row["observation_date"].isoformat(), "value": row["value"]}
            for row in obs_rows
        ],
    }


def jobs_summary_text(jobs):
    """Short 'N running · N queued' string for the toast, or None if
    nothing is active — completed/failed rows don't count as active."""
    active = {
        row["status"]: row["count"]
        for row in jobs
        if row["status"] in ("queued", "running")
    }
    if not active:
        return None
    parts = []
    if active.get("running"):
        parts.append(f"{active['running']} running")
    if active.get("queued"):
        parts.append(f"{active['queued']} queued")
    return " · ".join(parts)


def dashboard_state():
    jobs = safe("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status ORDER BY status")
    jobs_active = any(
        row["status"] in ("queued", "running") and row["count"] > 0
        for row in jobs
    )

    return {
        "narrative": latest_narrative(),
        "asset_analysis": latest_asset_analysis(),
        "last_runs": last_run_times(),
        "jobs_active": jobs_active,
        "jobs_summary": jobs_summary_text(jobs),
        "beliefs": safe(
            """
            SELECT belief_key, probability, confidence, updated_at FROM (
                SELECT DISTINCT ON (belief_key) belief_key, probability, confidence, updated_at
                FROM beliefs ORDER BY belief_key, updated_at DESC
            ) t ORDER BY updated_at DESC LIMIT 12
            """
        ),
        "regimes": safe(
            """
            SELECT regime_key, probability, as_of FROM (
                SELECT DISTINCT ON (regime_key) regime_key, probability, as_of
                FROM regimes ORDER BY regime_key, as_of DESC
            ) t ORDER BY probability DESC LIMIT 12
            """
        ),
        "publications": safe("SELECT publication_id, publication_type, subject, status, created_at FROM publications ORDER BY created_at DESC LIMIT 10"),
        "macro": safe(
            """
            SELECT DISTINCT ON (s.series_id)
                s.series_id, s.title, s.category, s.units, s.interpretation,
                o.observation_date, o.value, o.retrieved_at
            FROM macro_series s
            JOIN macro_observations o ON o.series_id=s.series_id
            ORDER BY s.series_id, o.observation_date DESC, o.retrieved_at DESC
            """
        ),
        "ingestion_runs": safe(
            """
            SELECT provider,status,series_requested,series_succeeded,
                   observations_written,started_at,completed_at
            FROM macro_ingestion_runs
            ORDER BY started_at DESC LIMIT 5
            """
        ),
    }

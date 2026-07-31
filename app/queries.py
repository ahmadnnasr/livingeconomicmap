from app.db import fetch_all
 
 
def safe(query, params=()):
    try:
        return fetch_all(query, params)
    except Exception:
        return []
 
 
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
 
 
def dashboard_state():
    return {
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
        "jobs": safe("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status ORDER BY status"),
        "publications": safe("SELECT publication_id, publication_type, subject, status, created_at FROM publications ORDER BY created_at DESC LIMIT 10"),
        "deliveries": safe("SELECT status, delivery_mode, message_id, draft_id, created_at FROM gmail_delivery_records ORDER BY created_at DESC LIMIT 10"),
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
 

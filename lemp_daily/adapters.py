from __future__ import annotations

import json

from app.db import connection, fetch_all

MODEL_VERSION = "daily_brief_v1"


def _latest_regimes() -> list[dict]:
    return fetch_all(
        """
        SELECT regime_key, probability, as_of FROM (
            SELECT DISTINCT ON (regime_key) regime_key, probability, as_of
            FROM regimes ORDER BY regime_key, as_of DESC
        ) t ORDER BY probability DESC
        """
    )


def _latest_beliefs() -> list[dict]:
    return fetch_all(
        """
        SELECT belief_key, probability, confidence, updated_at FROM (
            SELECT DISTINCT ON (belief_key) belief_key, probability, confidence, updated_at
            FROM beliefs ORDER BY belief_key, updated_at DESC
        ) t ORDER BY belief_key
        """
    )


def load_context(as_of_date: str) -> dict:
    """
    Builds the context dict DailyBriefGenerator.generate() expects, from
    whatever beliefs/regimes actually exist right now. market_transmission,
    ranking_changes, alerts, and model_governance are honestly empty —
    those subsystems (company ranking, calibration, governance) aren't
    wired up yet, so the brief says "No material changes" for them rather
    than fabricating content.
    """
    regimes = _latest_regimes()
    beliefs = _latest_beliefs()

    top_regime = regimes[0]["regime_key"] if regimes else "unknown"

    composite = next(
        (b["probability"] for b in beliefs if b["belief_key"] == "composite_liquidity"),
        None,
    )

    belief_change_text = [
        f"{b['belief_key'].replace('_', ' ')}: {b['probability'] * 100:.1f}% "
        f"(confidence {b['confidence'] * 100:.0f}%)"
        for b in beliefs
        if b["belief_key"] != "composite_liquidity"
    ]

    return {
        "as_of_date": as_of_date,
        "top_regime": top_regime,
        "composite_liquidity": composite,
        "belief_change_text": belief_change_text,
        "market_transmission_text": [],
        "ranking_change_text": [],
        "alert_text": [],
        "governance_text": [],
    }


def persist_publication(brief, markdown: str) -> str:
    with connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO publications (publication_type, subject, payload, status, model_version)
            VALUES (%s, %s, %s::jsonb, %s, %s)
            RETURNING publication_id
            """,
            (
                "daily_brief",
                brief.headline,
                json.dumps(
                    {
                        "as_of_date": brief.as_of_date,
                        "regime_summary": brief.regime_summary,
                        "belief_changes": brief.belief_changes,
                        "markdown": markdown,
                    }
                ),
                "rendered",
                MODEL_VERSION,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    return str(row[0]) if row else ""

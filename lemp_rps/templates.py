from __future__ import annotations
from .models import PublicationSection


PUBLICATION_TYPES = {
    "preopen_brief": {
        "default_subject": "Living Economic Map — Pre-Open Brief",
        "required_sections": [
            "overnight_macro",
            "scheduled_releases",
            "regime",
            "belief_changes",
            "market_sensitivities",
            "risk_watchlist",
        ],
    },
    "release_bulletin": {
        "default_subject": "Living Economic Map — Material Release Bulletin",
        "required_sections": [
            "release_summary",
            "evidence_update",
            "belief_update",
            "regime_update",
            "market_impact",
        ],
    },
    "closing_report": {
        "default_subject": "Living Economic Map — Closing Research Report",
        "required_sections": [
            "executive_summary",
            "evidence",
            "beliefs",
            "regimes",
            "market_transmission",
            "company_implications",
            "ranking_changes",
            "calibration",
            "platform_health",
            "tomorrow_watchlist",
        ],
    },
    "governance_package": {
        "default_subject": "Living Economic Map — Model Approval Package",
        "required_sections": [
            "candidate_summary",
            "performance_comparison",
            "coefficient_changes",
            "stability",
            "risks",
            "recommendation",
            "approval",
        ],
    },
    "critical_alert": {
        "default_subject": "Living Economic Map — Critical Alert",
        "required_sections": [
            "alert_summary",
            "impact",
            "required_action",
        ],
    },
}


def validate_sections(publication_type: str, sections: list[PublicationSection]) -> list[str]:
    spec = PUBLICATION_TYPES[publication_type]
    keys = {section.key for section in sections}
    return [key for key in spec["required_sections"] if key not in keys]

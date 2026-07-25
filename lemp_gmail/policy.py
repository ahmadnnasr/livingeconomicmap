from __future__ import annotations


class GmailDeliveryPolicy:
    """
    Gmail-first defaults for a small, human-governed research platform.
    """

    DEFAULT_MODES = {
        "preopen_brief": "send_now",
        "closing_report": "send_now",
        "release_bulletin": "send_now",
        "critical_alert": "send_now",
        "governance_package": "draft_first",
    }

    @classmethod
    def mode_for(cls, publication_type: str) -> str:
        try:
            return cls.DEFAULT_MODES[publication_type]
        except KeyError as exc:
            raise ValueError(
                f"No Gmail delivery policy for {publication_type}"
            ) from exc

    @staticmethod
    def requires_human_review(publication_type: str) -> bool:
        return GmailDeliveryPolicy.mode_for(publication_type) == "draft_first"

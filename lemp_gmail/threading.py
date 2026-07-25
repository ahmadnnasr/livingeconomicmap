from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class ThreadState:
    publication_series_key: str
    latest_message_id: Optional[str]
    latest_thread_id: Optional[str]


class ThreadingPolicy:
    """
    Threads recurring publications only when explicitly desired.

    Recommended:
      - closing reports may remain in one daily-report thread per month
      - governance packages should reply within the candidate's review thread
      - critical alerts should start new threads
    """

    @staticmethod
    def reply_message_id(
        publication_type: str,
        thread_state: ThreadState | None,
    ) -> str | None:
        if thread_state is None:
            return None
        if publication_type in {"closing_report", "governance_package"}:
            return thread_state.latest_message_id
        return None

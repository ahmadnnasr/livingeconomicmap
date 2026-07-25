from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, List
from .models import Observation


class Connector(Protocol):
    source_id: str
    connector_name: str

    def fetch(self, request: dict) -> dict:
        ...

    def normalize(self, payload: dict) -> List[Observation]:
        ...


@dataclass
class BenzingaConnectorContract:
    """
    First-class contract for future Benzinga integration.

    Intended use cases:
    - Earnings calendar and earnings results
    - Analyst ratings and estimate changes
    - Corporate news
    - Economic calendar
    - Delayed or real-time market data, depending on entitlement

    The API key should be injected through an environment reference such as:
        env:BENZINGA_API_KEY

    No secret value should be written to this repository or database.
    """

    source_id: str = "benzinga"
    connector_name: str = "benzinga_api"
    credential_reference: str = "env:BENZINGA_API_KEY"

    def fetch(self, request: dict) -> dict:
        raise NotImplementedError(
            "Network execution belongs in the live connector runtime."
        )

    def normalize(self, payload: dict) -> List[Observation]:
        raise NotImplementedError(
            "Normalization is endpoint-specific and will be added per feed."
        )

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from .models import CanonicalObservation, ConnectorRequest


class MacroConnector(ABC):
    source_id: str
    connector_name: str

    @abstractmethod
    def build_request(self, **kwargs) -> ConnectorRequest:
        ...

    @abstractmethod
    def normalize(
        self,
        payload: Any,
        *,
        vintage_date: str,
        **kwargs,
    ) -> list[CanonicalObservation]:
        ...


def numeric(value: Any) -> float | None:
    if value in (None, "", ".", "NA", "N/A", "null"):
        return None
    text = str(value).replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None

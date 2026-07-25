from __future__ import annotations
from typing import Any

from .base import MacroConnector, numeric
from .models import CanonicalObservation, ConnectorRequest


class EiaConnector(MacroConnector):
    source_id = "eia"
    connector_name = "eia_api_v2"
    base_endpoint = "https://api.eia.gov/v2"

    def build_request(
        self,
        route: str,
        data_fields: list[str],
        facets: dict[str, list[str]] | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str | None = None,
        length: int = 5000,
        offset: int = 0,
    ) -> ConnectorRequest:
        params: dict[str, Any] = {
            "data[]": data_fields,
            "length": length,
            "offset": offset,
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if frequency:
            params["frequency"] = frequency
        for facet, values in (facets or {}).items():
            params[f"facets[{facet}][]"] = values

        return ConnectorRequest(
            endpoint=f"{self.base_endpoint}/{route.strip('/')}/data/",
            parameters=params,
            credential_reference="env:EIA_API_KEY",
        )

    def normalize(
        self,
        payload: dict,
        *,
        vintage_date: str,
        route: str,
        data_fields: list[str],
        period_field: str = "period",
        series_dimensions: list[str] | None = None,
        units_by_field: dict[str, str] | None = None,
        frequency: str,
    ) -> list[CanonicalObservation]:
        series_dimensions = series_dimensions or []
        units_by_field = units_by_field or {}
        response = payload.get("response", {})
        output = []

        for row in response.get("data", []):
            period = row[period_field]
            observation_date = self._period_to_date(str(period), frequency)
            dimensions = ":".join(
                f"{field}={row.get(field)}" for field in series_dimensions
            )
            for field in data_fields:
                value = numeric(row.get(field))
                if value is None:
                    continue
                external_id = f"{route}:{field}"
                suffix = f":{dimensions}" if dimensions else ""
                output.append(
                    CanonicalObservation(
                        series_id=f"eia:{external_id}{suffix}",
                        source_id=self.source_id,
                        external_id=external_id,
                        observation_date=observation_date,
                        value=value,
                        vintage_date=vintage_date,
                        units=units_by_field.get(field, row.get(f"{field}-units", "unknown")),
                        frequency=frequency,
                        metadata={
                            "route": route,
                            "dimensions": {
                                field: row.get(field)
                                for field in series_dimensions
                            },
                        },
                    )
                )
        return output

    @staticmethod
    def _period_to_date(period: str, frequency: str) -> str:
        if frequency == "daily":
            return period[:10]
        if frequency == "monthly":
            return f"{period[:7]}-01"
        if frequency == "quarterly":
            year = period[:4]
            quarter = period[-1]
            month = {"1": "01", "2": "04", "3": "07", "4": "10"}[quarter]
            return f"{year}-{month}-01"
        return f"{period[:4]}-01-01"

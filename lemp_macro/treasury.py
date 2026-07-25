from __future__ import annotations
from typing import Any

from .base import MacroConnector, numeric
from .models import CanonicalObservation, ConnectorRequest


class TreasuryFiscalDataConnector(MacroConnector):
    source_id = "treasury"
    connector_name = "treasury_fiscal_data"
    base_endpoint = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"

    def build_request(
        self,
        endpoint_path: str,
        fields: list[str],
        filters: str | None = None,
        page_size: int = 1000,
        page_number: int = 1,
    ) -> ConnectorRequest:
        params = {
            "fields": ",".join(fields),
            "page[size]": page_size,
            "page[number]": page_number,
        }
        if filters:
            params["filter"] = filters
        return ConnectorRequest(
            endpoint=f"{self.base_endpoint}/{endpoint_path.strip('/')}",
            parameters=params,
        )

    def normalize(
        self,
        payload: dict,
        *,
        vintage_date: str,
        dataset_id: str,
        date_field: str,
        value_fields: list[str],
        units_by_field: dict[str, str],
        frequency: str,
        dimensions: list[str] | None = None,
    ) -> list[CanonicalObservation]:
        dimensions = dimensions or []
        output = []
        for row in payload.get("data", []):
            observation_date = row[date_field][:10]
            dimension_key = ":".join(
                f"{field}={row.get(field)}" for field in dimensions
            )
            for field in value_fields:
                value = numeric(row.get(field))
                if value is None:
                    continue
                suffix = f":{dimension_key}" if dimension_key else ""
                output.append(
                    CanonicalObservation(
                        series_id=f"treasury:{dataset_id}:{field}{suffix}",
                        source_id=self.source_id,
                        external_id=field,
                        observation_date=observation_date,
                        value=value,
                        vintage_date=vintage_date,
                        units=units_by_field[field],
                        frequency=frequency,
                        metadata={
                            "dataset_id": dataset_id,
                            "dimensions": {
                                name: row.get(name) for name in dimensions
                            },
                        },
                    )
                )
        return output

from __future__ import annotations
from typing import Any

from .base import MacroConnector, numeric
from .models import CanonicalObservation, ConnectorRequest


class CensusConnector(MacroConnector):
    source_id = "census"
    connector_name = "census_data_api"

    def build_request(
        self,
        dataset_url: str,
        variables: list[str],
        predicates: dict[str, str] | None = None,
    ) -> ConnectorRequest:
        params = {"get": ",".join(variables)}
        params.update(predicates or {})
        return ConnectorRequest(
            endpoint=dataset_url,
            parameters=params,
            credential_reference="env:CENSUS_API_KEY",
        )

    def normalize(
        self,
        payload: list,
        *,
        vintage_date: str,
        dataset_id: str,
        value_variables: list[str],
        period_variable: str,
        units_by_variable: dict[str, str],
        frequency: str,
        geography_fields: list[str] | None = None,
    ) -> list[CanonicalObservation]:
        if not payload:
            return []
        headers = payload[0]
        output = []
        geography_fields = geography_fields or []

        for values in payload[1:]:
            row = dict(zip(headers, values))
            observation_date = self._period_to_date(
                row[period_variable],
                frequency,
            )
            geography = ":".join(
                f"{field}={row.get(field)}" for field in geography_fields
            )
            for variable in value_variables:
                value = numeric(row.get(variable))
                if value is None:
                    continue
                suffix = f":{geography}" if geography else ""
                output.append(
                    CanonicalObservation(
                        series_id=f"census:{dataset_id}:{variable}{suffix}",
                        source_id=self.source_id,
                        external_id=variable,
                        observation_date=observation_date,
                        value=value,
                        vintage_date=vintage_date,
                        units=units_by_variable[variable],
                        frequency=frequency,
                        metadata={
                            "dataset_id": dataset_id,
                            "geography": {
                                field: row.get(field)
                                for field in geography_fields
                            },
                        },
                    )
                )
        return output

    @staticmethod
    def _period_to_date(value: str, frequency: str) -> str:
        text = str(value)
        if frequency == "monthly":
            digits = text.replace("-", "")
            return f"{digits[:4]}-{digits[4:6]}-01"
        if frequency == "quarterly":
            year = text[:4]
            quarter = text[-1]
            month = {"1": "01", "2": "04", "3": "07", "4": "10"}[quarter]
            return f"{year}-{month}-01"
        return f"{text[:4]}-01-01"

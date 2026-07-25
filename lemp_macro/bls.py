from __future__ import annotations
from datetime import date
from typing import Any

from .base import MacroConnector, numeric
from .models import CanonicalObservation, ConnectorRequest


class BlsConnector(MacroConnector):
    source_id = "bls"
    connector_name = "bls_public_data_v2"
    endpoint = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

    def build_request(
        self,
        series_ids: list[str],
        start_year: int,
        end_year: int,
    ) -> ConnectorRequest:
        if end_year - start_year > 19:
            raise ValueError("Split long BLS requests into bounded year windows.")
        return ConnectorRequest(
            endpoint=self.endpoint,
            parameters={},
            credential_reference="env:BLS_API_KEY",
        )

    def build_post_body(
        self,
        series_ids: list[str],
        start_year: int,
        end_year: int,
        registration_key: str | None = None,
    ) -> dict:
        body = {
            "seriesid": series_ids,
            "startyear": str(start_year),
            "endyear": str(end_year),
        }
        if registration_key:
            body["registrationkey"] = registration_key
        return body

    def normalize(
        self,
        payload: dict,
        *,
        vintage_date: str,
        units_by_series: dict[str, str],
        frequency_by_series: dict[str, str],
        seasonal_by_series: dict[str, str | None] | None = None,
    ) -> list[CanonicalObservation]:
        seasonal_by_series = seasonal_by_series or {}
        output = []
        if payload.get("status") not in (None, "REQUEST_SUCCEEDED"):
            raise ValueError(f"BLS request failed: {payload.get('message')}")

        for series in payload.get("Results", {}).get("series", []):
            external_id = series["seriesID"]
            for item in series.get("data", []):
                period = item.get("period")
                if not period or period == "M13":
                    continue
                value = numeric(item.get("value"))
                if value is None:
                    continue
                month = int(period[1:]) if period.startswith("M") else 1
                observation_date = f"{item['year']}-{month:02d}-01"
                output.append(
                    CanonicalObservation(
                        series_id=f"bls:{external_id}",
                        source_id=self.source_id,
                        external_id=external_id,
                        observation_date=observation_date,
                        value=value,
                        vintage_date=vintage_date,
                        units=units_by_series[external_id],
                        frequency=frequency_by_series[external_id],
                        seasonal_adjustment=seasonal_by_series.get(external_id),
                        metadata={
                            "period_name": item.get("periodName"),
                            "footnotes": item.get("footnotes", []),
                            "latest": item.get("latest"),
                        },
                    )
                )
        return output

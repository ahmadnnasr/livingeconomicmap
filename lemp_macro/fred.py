from __future__ import annotations
from typing import Any

from .base import MacroConnector, numeric
from .models import CanonicalObservation, ConnectorRequest


class FredConnector(MacroConnector):
    source_id = "fred"
    connector_name = "fred_series_observations"
    endpoint = "https://api.stlouisfed.org/fred/series/observations"

    def build_request(
        self,
        series_id: str,
        observation_start: str,
        observation_end: str,
        *,
        output_type: int = 1,
        realtime_start: str | None = None,
        realtime_end: str | None = None,
    ) -> ConnectorRequest:
        params = {
            "series_id": series_id,
            "observation_start": observation_start,
            "observation_end": observation_end,
            "file_type": "json",
            "output_type": output_type,
        }
        if realtime_start:
            params["realtime_start"] = realtime_start
        if realtime_end:
            params["realtime_end"] = realtime_end
        return ConnectorRequest(
            endpoint=self.endpoint,
            parameters=params,
            credential_reference="env:FRED_API_KEY",
        )

    def normalize(
        self,
        payload: dict,
        *,
        vintage_date: str,
        series_id: str,
        units: str,
        frequency: str,
        seasonal_adjustment: str | None = None,
        release_id: str | None = None,
    ) -> list[CanonicalObservation]:
        output = []
        for item in payload.get("observations", []):
            value = numeric(item.get("value"))
            if value is None:
                continue
            item_vintage = item.get("realtime_start") or vintage_date
            output.append(
                CanonicalObservation(
                    series_id=f"fred:{series_id}",
                    source_id=self.source_id,
                    external_id=series_id,
                    observation_date=item["date"],
                    value=value,
                    vintage_date=item_vintage,
                    units=units,
                    frequency=frequency,
                    seasonal_adjustment=seasonal_adjustment,
                    release_id=release_id,
                    metadata={
                        "realtime_end": item.get("realtime_end"),
                        "api_output_type": payload.get("output_type"),
                    },
                )
            )
        return output


class FredReleaseConnector(MacroConnector):
    source_id = "fred"
    connector_name = "fred_v2_release_observations"
    endpoint = "https://api.stlouisfed.org/fred/v2/release/observations"

    def build_request(
        self,
        release_id: str,
        next_cursor: str | None = None,
        limit: int = 1000,
    ) -> ConnectorRequest:
        params = {
            "release_id": release_id,
            "format": "json",
            "limit": limit,
        }
        if next_cursor:
            params["next_cursor"] = next_cursor
        return ConnectorRequest(
            endpoint=self.endpoint,
            parameters=params,
            credential_reference="env:FRED_API_KEY",
        )

    def normalize(
        self,
        payload: dict,
        *,
        vintage_date: str,
        release_id: str,
    ) -> list[CanonicalObservation]:
        output = []
        for series in payload.get("series", payload.get("seriess", [])):
            external_id = series.get("series_id") or series.get("id")
            for item in series.get("observations", []):
                value = numeric(item.get("value"))
                if value is None:
                    continue
                output.append(
                    CanonicalObservation(
                        series_id=f"fred:{external_id}",
                        source_id=self.source_id,
                        external_id=external_id,
                        observation_date=item["date"],
                        value=value,
                        vintage_date=vintage_date,
                        units=series.get("units", "unknown"),
                        frequency=series.get("frequency", "unknown"),
                        seasonal_adjustment=series.get("seasonal_adjustment"),
                        release_id=release_id,
                        metadata={
                            "title": series.get("title"),
                            "last_updated": series.get("last_updated"),
                            "copyright_id": series.get("copyright_id"),
                        },
                    )
                )
        return output

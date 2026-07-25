from __future__ import annotations
from typing import Any

from .base import MacroConnector, numeric
from .models import CanonicalObservation, ConnectorRequest


class BeaConnector(MacroConnector):
    source_id = "bea"
    connector_name = "bea_data_api"
    endpoint = "https://apps.bea.gov/api/data/"

    def build_request(
        self,
        dataset_name: str,
        table_name: str,
        frequency: str,
        year: str = "X",
        result_format: str = "JSON",
    ) -> ConnectorRequest:
        return ConnectorRequest(
            endpoint=self.endpoint,
            parameters={
                "method": "GetData",
                "datasetname": dataset_name,
                "TableName": table_name,
                "Frequency": frequency,
                "Year": year,
                "ResultFormat": result_format,
            },
            credential_reference="env:BEA_API_KEY",
        )

    def normalize(
        self,
        payload: dict,
        *,
        vintage_date: str,
        dataset_name: str,
        table_name: str,
        series_code_field: str = "SeriesCode",
    ) -> list[CanonicalObservation]:
        api = payload.get("BEAAPI", {})
        if api.get("Error"):
            raise ValueError(str(api["Error"]))

        results = api.get("Results", {})
        data = results.get("Data", [])
        output = []

        for item in data:
            value = numeric(item.get("DataValue"))
            if value is None:
                continue

            period = str(item.get("TimePeriod", ""))
            observation_date = self._period_to_date(period)
            external_id = (
                item.get(series_code_field)
                or item.get("LineNumber")
                or item.get("GeoFIPS")
            )
            unit = item.get("UNIT_MULT", "0")
            units = item.get("CL_UNIT") or item.get("Unit") or f"unit_mult:{unit}"

            output.append(
                CanonicalObservation(
                    series_id=f"bea:{dataset_name}:{table_name}:{external_id}",
                    source_id=self.source_id,
                    external_id=str(external_id),
                    observation_date=observation_date,
                    value=value,
                    vintage_date=vintage_date,
                    units=str(units),
                    frequency=self._frequency(period),
                    metadata={
                        "dataset_name": dataset_name,
                        "table_name": table_name,
                        "line_description": item.get("LineDescription"),
                        "unit_multiplier": item.get("UNIT_MULT"),
                        "note_ref": item.get("NoteRef"),
                    },
                )
            )
        return output

    @staticmethod
    def _period_to_date(period: str) -> str:
        if "Q" in period:
            year, quarter = period.split("Q")
            month = {"1": "01", "2": "04", "3": "07", "4": "10"}[quarter]
            return f"{year}-{month}-01"
        if "M" in period:
            year, month = period.split("M")
            return f"{year}-{int(month):02d}-01"
        return f"{period[:4]}-01-01"

    @staticmethod
    def _frequency(period: str) -> str:
        if "Q" in period:
            return "quarterly"
        if "M" in period:
            return "monthly"
        return "annual"

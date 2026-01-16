from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

BASE_URL = "https://api.airtable.com"


@dataclass(frozen=True)
class AirtableRecord:
    record_id: str
    fields: dict[str, Any]


class AirtableError(RuntimeError):
    pass


class AirtableClient:
    def __init__(self, api_key: str, base_id: str) -> None:
        self.base_id = base_id
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )

    def list_tables(self) -> list[dict[str, Any]]:
        data = self._request("GET", f"/v0/meta/bases/{self.base_id}/tables")
        return data.get("tables", [])

    def list_records(
        self,
        table_id: str,
        fields: list[str] | None = None,
        filter_formula: str | None = None,
    ) -> list[AirtableRecord]:
        params: dict[str, Any] = {}
        if fields:
            params["fields[]"] = fields
        if filter_formula:
            params["filterByFormula"] = filter_formula

        records: list[AirtableRecord] = []
        offset = None
        while True:
            if offset:
                params["offset"] = offset
            data = self._request("GET", f"/v0/{self.base_id}/{table_id}", params=params)
            for record in data.get("records", []):
                records.append(AirtableRecord(record_id=record["id"], fields=record.get("fields", {})))
            offset = data.get("offset")
            if not offset:
                break
        return records

    def create_record(self, table_id: str, fields: dict[str, Any]) -> AirtableRecord:
        data = self._request("POST", f"/v0/{self.base_id}/{table_id}", json={"fields": fields})
        return AirtableRecord(record_id=data["id"], fields=data.get("fields", {}))

    def update_record(self, table_id: str, record_id: str, fields: dict[str, Any]) -> AirtableRecord:
        data = self._request(
            "PATCH",
            f"/v0/{self.base_id}/{table_id}/{record_id}",
            json={"fields": fields},
        )
        return AirtableRecord(record_id=data["id"], fields=data.get("fields", {}))

    def find_record_by_external_id(self, table_id: str, external_id: str) -> AirtableRecord | None:
        formula = f"{{ExternalId}}='{external_id.replace("'", "\\'")}'"
        records = self.list_records(table_id, filter_formula=formula)
        if not records:
            return None
        if len(records) > 1:
            raise AirtableError("Multiple Airtable records found for ExternalId.")
        return records[0]

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None, json: Any | None = None):
        url = f"{BASE_URL}{path}"
        response = self.session.request(method, url, params=params, json=json, timeout=30)
        if response.status_code >= 400:
            raise AirtableError(f"Airtable error {response.status_code}: {response.text}")
        return response.json()

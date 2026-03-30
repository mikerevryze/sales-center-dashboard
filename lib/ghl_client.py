"""GoHighLevel API client."""

import httpx

BASE_URL = "https://rest.gohighlevel.com/v1"


class GHLClient:
    def __init__(self, api_token: str):
        self.headers = {"Authorization": f"Bearer {api_token}"}

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = httpx.get(f"{BASE_URL}{path}", headers=self.headers, params=params or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_contacts(self, limit: int = 100, offset: int = 0) -> dict:
        return self._get("/contacts", {"limit": limit, "startAfter": offset})

    def get_contact(self, contact_id: str) -> dict:
        return self._get(f"/contacts/{contact_id}")

    def get_opportunities(self, pipeline_id: str) -> dict:
        return self._get("/pipelines/opportunities", {"pipelineId": pipeline_id})

    def get_pipelines(self) -> dict:
        return self._get("/pipelines")

    def get_calendars(self) -> dict:
        return self._get("/calendars")

    def get_appointments(self, calendar_id: str, start: str, end: str) -> dict:
        return self._get(f"/calendars/{calendar_id}/appointments", {
            "startDate": start, "endDate": end
        })

"""Clients API — client and location management."""

from fastapi import APIRouter, Body
from pydantic import BaseModel
from lib.snowflake_client import fetch_all, execute
import uuid

router = APIRouter()


class LocationInput(BaseModel):
    location_name: str
    ghl_location_id: str
    ghl_api_token: str
    meta_account_id: str = ""
    meta_access_token: str = ""
    sales_start_date: str = ""
    opening_date: str = ""


class ClientInput(BaseModel):
    client_name: str
    multi_location: bool = False
    industry: str = ""
    survival_threshold: int = 150
    target_mrr: float = 30000
    locations: list[LocationInput] = []


@router.get("/clients")
async def list_clients():
    """Return all clients with their locations.

    Response shape:
    {
      "clients": [
        {
          "client_id": str,
          "client_name": str,
          "multi_location": bool,
          "industry": str,
          "locations": [
            {"location_id": str, "location_name": str, "ghl_location_id": str}
          ]
        }
      ]
    }
    """
    rows = fetch_all("""
        SELECT
            c.client_id, c.client_name, c.multi_location, c.industry,
            l.location_id, l.location_name, l.ghl_location_id
        FROM clients c
        LEFT JOIN locations l ON l.client_id = c.client_id
        ORDER BY c.client_name, l.location_name
    """)

    clients_map = {}
    for r in rows:
        cid = r["client_id"]
        if cid not in clients_map:
            clients_map[cid] = {
                "client_id": cid,
                "client_name": r["client_name"],
                "multi_location": bool(r["multi_location"]),
                "industry": r["industry"] or "",
                "locations": [],
            }
        if r["location_id"]:
            clients_map[cid]["locations"].append({
                "location_id": r["location_id"],
                "location_name": r["location_name"],
                "ghl_location_id": r["ghl_location_id"],
            })

    return {"clients": list(clients_map.values())}


@router.post("/clients")
async def create_client(client: ClientInput):
    """Create a new client with locations.

    Request body: ClientInput
    Response: {"client_id": str, "status": "created"}
    """
    client_id = str(uuid.uuid4())
    execute("""
        INSERT INTO clients (client_id, client_name, multi_location, industry, survival_threshold, target_mrr, created_at)
        VALUES (%(client_id)s, %(client_name)s, %(multi_location)s, %(industry)s, %(survival_threshold)s, %(target_mrr)s, CURRENT_TIMESTAMP)
    """, {
        "client_id": client_id,
        "client_name": client.client_name,
        "multi_location": client.multi_location,
        "industry": client.industry,
        "survival_threshold": client.survival_threshold,
        "target_mrr": client.target_mrr,
    })

    for loc in client.locations:
        location_id = str(uuid.uuid4())
        execute("""
            INSERT INTO locations (location_id, client_id, location_name, ghl_location_id, ghl_api_token,
                meta_account_id, meta_access_token, sales_start_date, opening_date, created_at)
            VALUES (%(location_id)s, %(client_id)s, %(location_name)s, %(ghl_location_id)s, %(ghl_api_token)s,
                %(meta_account_id)s, %(meta_access_token)s, %(sales_start_date)s, %(opening_date)s, CURRENT_TIMESTAMP)
        """, {
            "location_id": location_id,
            "client_id": client_id,
            "location_name": loc.location_name,
            "ghl_location_id": loc.ghl_location_id,
            "ghl_api_token": loc.ghl_api_token,
            "meta_account_id": loc.meta_account_id,
            "meta_access_token": loc.meta_access_token,
            "sales_start_date": loc.sales_start_date or None,
            "opening_date": loc.opening_date or None,
        })

    return {"client_id": client_id, "status": "created"}

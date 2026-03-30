"""Scorecard API — EOS health metrics per location."""

from fastapi import APIRouter, Query
from lib.snowflake_client import fetch_all

router = APIRouter()


@router.get("/scorecard")
async def get_scorecard(
    client_id: str = Query(...),
    location_id: str = Query(None),
):
    """Return EOS scorecard metrics for a client/location.

    Response shape:
    {
      "locations": [
        {
          "location_id": str,
          "location_name": str,
          "metrics": {
            "members": {"value": int, "threshold": int},
            "mrr": {"value": float, "threshold": float},
            "cpl": {"value": float},
            "close_rate": {"value": float},
            "days_to_opening": {"value": int | null},
            "ad_spend": {"value": float}
          }
        }
      ]
    }
    """
    location_filter = "AND l.location_id = %(location_id)s" if location_id else ""
    rows = fetch_all(f"""
        SELECT
            l.location_id,
            l.location_name,
            COALESCE(m.active_members, 0) AS members,
            c.survival_threshold AS member_threshold,
            COALESCE(m.mrr, 0) AS mrr,
            c.target_mrr AS mrr_threshold,
            COALESCE(mk.cpl, 0) AS cpl,
            COALESCE(mk.close_rate, 0) AS close_rate,
            DATEDIFF('day', CURRENT_DATE, l.opening_date) AS days_to_opening,
            COALESCE(mk.ad_spend_mtd, 0) AS ad_spend
        FROM clients c
        JOIN locations l ON l.client_id = c.client_id
        LEFT JOIN member_metrics m ON m.location_id = l.location_id
            AND m.metric_date = CURRENT_DATE
        LEFT JOIN marketing_metrics mk ON mk.location_id = l.location_id
            AND mk.metric_date = CURRENT_DATE
        WHERE c.client_id = %(client_id)s
        {location_filter}
        ORDER BY l.location_name
    """, {"client_id": client_id, "location_id": location_id})

    locations = []
    for r in rows:
        locations.append({
            "location_id": r["location_id"],
            "location_name": r["location_name"],
            "metrics": {
                "members": {"value": r["members"], "threshold": r["member_threshold"]},
                "mrr": {"value": float(r["mrr"]), "threshold": float(r["mrr_threshold"])},
                "cpl": {"value": float(r["cpl"])},
                "close_rate": {"value": float(r["close_rate"])},
                "days_to_opening": {"value": r["days_to_opening"]},
                "ad_spend": {"value": float(r["ad_spend"])},
            },
        })
    return {"locations": locations}

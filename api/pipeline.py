"""Pipeline API — opportunity funnel and stage breakdown."""

from fastapi import APIRouter, Query
from lib.snowflake_client import fetch_all

router = APIRouter()


@router.get("/pipeline")
async def get_pipeline(
    client_id: str = Query(...),
    location_id: str = Query(...),
):
    """Return pipeline funnel summary.

    Response shape:
    {
      "stages": [
        {
          "stage": str,
          "count": int,
          "total_value": float,
          "avg_days_in_stage": float
        }
      ],
      "total_opportunities": int,
      "total_value": float
    }
    """
    rows = fetch_all("""
        SELECT
            o.stage,
            COUNT(*) AS count,
            COALESCE(SUM(o.value), 0) AS total_value,
            COALESCE(AVG(DATEDIFF('day', o.stage_entered_at, CURRENT_TIMESTAMP)), 0) AS avg_days_in_stage
        FROM opportunities o
        WHERE o.location_id = %(location_id)s
        GROUP BY o.stage
        ORDER BY MIN(o.stage_order)
    """, {"location_id": location_id})

    stages = [
        {
            "stage": r["stage"],
            "count": int(r["count"]),
            "total_value": float(r["total_value"]),
            "avg_days_in_stage": round(float(r["avg_days_in_stage"]), 1),
        }
        for r in rows
    ]

    return {
        "stages": stages,
        "total_opportunities": sum(s["count"] for s in stages),
        "total_value": sum(s["total_value"] for s in stages),
    }


@router.get("/pipeline/opportunities")
async def list_opportunities(
    client_id: str = Query(...),
    location_id: str = Query(...),
    stage: str = Query(None),
    status: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """Return paginated opportunity list.

    Response shape:
    {
      "opportunities": [
        {
          "opportunity_id": str,
          "contact_name": str,
          "stage": str,
          "status": str,
          "value": float,
          "created_at": str,
          "days_in_stage": int
        }
      ],
      "total": int,
      "page": int,
      "page_size": int
    }
    """
    filters = ["o.location_id = %(location_id)s"]
    params = {"location_id": location_id, "offset": (page - 1) * page_size, "limit": page_size}

    if stage:
        filters.append("o.stage = %(stage)s")
        params["stage"] = stage
    if status:
        filters.append("o.status = %(status)s")
        params["status"] = status
    if start_date:
        filters.append("o.created_at >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        filters.append("o.created_at <= %(end_date)s")
        params["end_date"] = end_date

    where = " AND ".join(filters)

    total_row = fetch_all(f"SELECT COUNT(*) AS cnt FROM opportunities o WHERE {where}", params)
    total = total_row[0]["cnt"] if total_row else 0

    rows = fetch_all(f"""
        SELECT
            o.opportunity_id, o.contact_name, o.stage, o.status,
            o.value, o.created_at,
            DATEDIFF('day', o.stage_entered_at, CURRENT_TIMESTAMP) AS days_in_stage
        FROM opportunities o
        WHERE {where}
        ORDER BY o.created_at DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, params)

    return {
        "opportunities": [
            {
                "opportunity_id": r["opportunity_id"],
                "contact_name": r["contact_name"],
                "stage": r["stage"],
                "status": r["status"],
                "value": float(r["value"]) if r["value"] else 0,
                "created_at": str(r["created_at"]),
                "days_in_stage": int(r["days_in_stage"]) if r["days_in_stage"] else 0,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

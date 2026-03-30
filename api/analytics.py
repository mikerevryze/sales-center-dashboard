"""Analytics API — marketing & sales performance data."""

from fastapi import APIRouter, Query
from lib.snowflake_client import fetch_all

router = APIRouter()


@router.get("/analytics/summary")
async def analytics_summary(
    client_id: str = Query(...),
    location_id: str = Query(...),
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    campaigns: str = Query(None, description="Comma-separated campaign names"),
):
    """Return aggregate KPI summary for the analytics dashboard.

    Response shape:
    {
      "kpis": {
        "total_spend": float,
        "total_leads": int,
        "cpl": float,
        "total_appointments": int,
        "total_enrollments": int,
        "close_rate": float,
        "cost_per_enrollment": float
      },
      "ltv": {
        "base_ltv": float,
        "adjusted_ltv": float,
        "avg_monthly_value": float,
        "avg_lifespan_months": float,
        "attrition_rate": float
      },
      "sales_velocity": {
        "avg_days_to_close": float,
        "enrollments_per_week": float,
        "pipeline_value": float
      },
      "campaigns": [
        {"name": str, "spend": float, "leads": int, "enrollments": int}
      ]
    }
    """
    campaign_filter = ""
    params = {
        "client_id": client_id,
        "location_id": location_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    if campaigns:
        campaign_list = [c.strip() for c in campaigns.split(",")]
        campaign_filter = "AND d.campaign_name IN ({})".format(
            ",".join(f"'{c}'" for c in campaign_list)
        )

    kpi_row = fetch_all(f"""
        SELECT
            COALESCE(SUM(d.spend), 0) AS total_spend,
            COALESCE(SUM(d.leads), 0) AS total_leads,
            CASE WHEN SUM(d.leads) > 0 THEN SUM(d.spend) / SUM(d.leads) ELSE 0 END AS cpl,
            COALESCE(SUM(d.appointments), 0) AS total_appointments,
            COALESCE(SUM(d.enrollments), 0) AS total_enrollments,
            CASE WHEN SUM(d.appointments) > 0
                THEN SUM(d.enrollments)::FLOAT / SUM(d.appointments) ELSE 0 END AS close_rate,
            CASE WHEN SUM(d.enrollments) > 0
                THEN SUM(d.spend) / SUM(d.enrollments) ELSE 0 END AS cost_per_enrollment
        FROM daily_metrics d
        WHERE d.location_id = %(location_id)s
          AND d.metric_date BETWEEN %(start_date)s AND %(end_date)s
          {campaign_filter}
    """, params)

    ltv_row = fetch_all("""
        SELECT
            COALESCE(AVG(monthly_value), 0) AS avg_monthly_value,
            COALESCE(AVG(lifespan_months), 0) AS avg_lifespan_months,
            COALESCE(AVG(attrition_rate), 0) AS attrition_rate
        FROM member_ltv
        WHERE location_id = %(location_id)s
    """, params)

    velocity_row = fetch_all(f"""
        SELECT
            COALESCE(AVG(days_to_close), 0) AS avg_days_to_close,
            COALESCE(SUM(d.enrollments)::FLOAT / GREATEST(DATEDIFF('week', %(start_date)s, %(end_date)s), 1), 0) AS enrollments_per_week,
            COALESCE(SUM(d.pipeline_value), 0) AS pipeline_value
        FROM daily_metrics d
        LEFT JOIN sales_velocity sv ON sv.location_id = d.location_id
        WHERE d.location_id = %(location_id)s
          AND d.metric_date BETWEEN %(start_date)s AND %(end_date)s
          {campaign_filter}
    """, params)

    campaigns_rows = fetch_all(f"""
        SELECT
            d.campaign_name AS name,
            SUM(d.spend) AS spend,
            SUM(d.leads) AS leads,
            SUM(d.enrollments) AS enrollments
        FROM daily_metrics d
        WHERE d.location_id = %(location_id)s
          AND d.metric_date BETWEEN %(start_date)s AND %(end_date)s
          {campaign_filter}
        GROUP BY d.campaign_name
        ORDER BY SUM(d.spend) DESC
    """, params)

    kpi = kpi_row[0] if kpi_row else {}
    ltv = ltv_row[0] if ltv_row else {}
    vel = velocity_row[0] if velocity_row else {}

    avg_monthly = float(ltv.get("avg_monthly_value", 0))
    avg_lifespan = float(ltv.get("avg_lifespan_months", 0))

    return {
        "kpis": {
            "total_spend": float(kpi.get("total_spend", 0)),
            "total_leads": int(kpi.get("total_leads", 0)),
            "cpl": float(kpi.get("cpl", 0)),
            "total_appointments": int(kpi.get("total_appointments", 0)),
            "total_enrollments": int(kpi.get("total_enrollments", 0)),
            "close_rate": float(kpi.get("close_rate", 0)),
            "cost_per_enrollment": float(kpi.get("cost_per_enrollment", 0)),
        },
        "ltv": {
            "base_ltv": avg_monthly * avg_lifespan,
            "adjusted_ltv": avg_monthly * avg_lifespan * (1 - float(ltv.get("attrition_rate", 0))),
            "avg_monthly_value": avg_monthly,
            "avg_lifespan_months": avg_lifespan,
            "attrition_rate": float(ltv.get("attrition_rate", 0)),
        },
        "sales_velocity": {
            "avg_days_to_close": float(vel.get("avg_days_to_close", 0)),
            "enrollments_per_week": float(vel.get("enrollments_per_week", 0)),
            "pipeline_value": float(vel.get("pipeline_value", 0)),
        },
        "campaigns": [
            {"name": r["name"], "spend": float(r["spend"]), "leads": int(r["leads"]), "enrollments": int(r["enrollments"])}
            for r in campaigns_rows
        ],
    }


@router.get("/analytics/daily")
async def analytics_daily(
    client_id: str = Query(...),
    location_id: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    campaigns: str = Query(None),
):
    """Return daily time-series data for charts.

    Response shape:
    {
      "daily": [
        {
          "date": "YYYY-MM-DD",
          "spend": float,
          "leads": int,
          "appointments": int,
          "enrollments": int,
          "cumulative_enrollments": int,
          "projected_enrollments": int | null
        }
      ]
    }
    """
    campaign_filter = ""
    params = {
        "location_id": location_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    if campaigns:
        campaign_list = [c.strip() for c in campaigns.split(",")]
        campaign_filter = "AND campaign_name IN ({})".format(
            ",".join(f"'{c}'" for c in campaign_list)
        )

    rows = fetch_all(f"""
        SELECT
            metric_date AS date,
            SUM(spend) AS spend,
            SUM(leads) AS leads,
            SUM(appointments) AS appointments,
            SUM(enrollments) AS enrollments
        FROM daily_metrics
        WHERE location_id = %(location_id)s
          AND metric_date BETWEEN %(start_date)s AND %(end_date)s
          {campaign_filter}
        GROUP BY metric_date
        ORDER BY metric_date
    """, params)

    cumulative = 0
    daily = []
    for r in rows:
        cumulative += int(r["enrollments"])
        daily.append({
            "date": str(r["date"]),
            "spend": float(r["spend"]),
            "leads": int(r["leads"]),
            "appointments": int(r["appointments"]),
            "enrollments": int(r["enrollments"]),
            "cumulative_enrollments": cumulative,
            "projected_enrollments": None,
        })

    # Simple linear projection for future dates
    if len(daily) >= 7:
        recent = daily[-7:]
        avg_per_day = sum(d["enrollments"] for d in recent) / 7
        last_cumulative = daily[-1]["cumulative_enrollments"]
        for i in range(1, 31):
            from datetime import datetime, timedelta
            last_date = datetime.strptime(daily[-1]["date"], "%Y-%m-%d")
            proj_date = last_date + timedelta(days=i)
            daily.append({
                "date": proj_date.strftime("%Y-%m-%d"),
                "spend": 0,
                "leads": 0,
                "appointments": 0,
                "enrollments": 0,
                "cumulative_enrollments": last_cumulative,
                "projected_enrollments": int(last_cumulative + avg_per_day * i),
            })

    return {"daily": daily}

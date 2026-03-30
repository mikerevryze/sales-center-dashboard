"""Call Center API — call recordings, scores, and leaderboard."""

from fastapi import APIRouter, Query, Path, Body
from lib.snowflake_client import fetch_all, fetch_one, execute
from lib.s3_client import generate_presigned_url

router = APIRouter()


@router.get("/calls")
async def list_calls(
    client_id: str = Query(...),
    location_id: str = Query(...),
    start_date: str = Query(None),
    end_date: str = Query(None),
    closer: str = Query(None),
    outcome: str = Query(None),
    search: str = Query(None, description="Search by contact name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """Return paginated call list with scores.

    Response shape:
    {
      "calls": [
        {
          "call_id": str,
          "contact_name": str,
          "closer": str,
          "call_date": str,
          "duration_seconds": int,
          "overall_score": int | null,
          "outcome": str,
          "recording_key": str | null
        }
      ],
      "total": int,
      "page": int,
      "page_size": int
    }
    """
    filters = ["c.location_id = %(location_id)s"]
    params = {"location_id": location_id, "offset": (page - 1) * page_size, "limit": page_size}

    if start_date:
        filters.append("c.call_date >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        filters.append("c.call_date <= %(end_date)s")
        params["end_date"] = end_date
    if closer:
        filters.append("c.closer = %(closer)s")
        params["closer"] = closer
    if outcome:
        filters.append("c.outcome = %(outcome)s")
        params["outcome"] = outcome
    if search:
        filters.append("c.contact_name ILIKE %(search)s")
        params["search"] = f"%{search}%"

    where = " AND ".join(filters)

    total_row = fetch_one(f"SELECT COUNT(*) AS cnt FROM calls c WHERE {where}", params)
    total = total_row["cnt"] if total_row else 0

    rows = fetch_all(f"""
        SELECT
            c.call_id, c.contact_name, c.closer, c.call_date,
            c.duration_seconds, cs.overall_score, c.outcome, c.recording_key
        FROM calls c
        LEFT JOIN call_scores cs ON cs.call_id = c.call_id
        WHERE {where}
        ORDER BY c.call_date DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, params)

    return {
        "calls": [
            {
                "call_id": r["call_id"],
                "contact_name": r["contact_name"],
                "closer": r["closer"],
                "call_date": str(r["call_date"]),
                "duration_seconds": int(r["duration_seconds"]),
                "overall_score": int(r["overall_score"]) if r["overall_score"] is not None else None,
                "outcome": r["outcome"],
                "recording_key": r["recording_key"],
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/calls/{call_id}")
async def get_call_detail(call_id: str = Path(...)):
    """Return full call detail including scores and transcript.

    Response shape:
    {
      "call_id": str,
      "contact_name": str,
      "closer": str,
      "call_date": str,
      "duration_seconds": int,
      "outcome": str,
      "scores": {
        "overall_score": int,
        "talk_ratio": int,
        "energy": int,
        "objection_handling": int,
        "next_steps": bool,
        "coach_notes": str
      } | null,
      "transcript": str | null,
      "manager_override": {
        "score": int | null,
        "notes": str | null
      } | null
    }
    """
    row = fetch_one("""
        SELECT
            c.call_id, c.contact_name, c.closer, c.call_date,
            c.duration_seconds, c.outcome, c.recording_key, c.transcript,
            cs.overall_score, cs.talk_ratio, cs.energy,
            cs.objection_handling, cs.next_steps, cs.coach_notes,
            mo.override_score, mo.override_notes
        FROM calls c
        LEFT JOIN call_scores cs ON cs.call_id = c.call_id
        LEFT JOIN manager_overrides mo ON mo.call_id = c.call_id
        WHERE c.call_id = %(call_id)s
    """, {"call_id": call_id})

    if not row:
        return {"error": "Call not found"}, 404

    scores = None
    if row["overall_score"] is not None:
        scores = {
            "overall_score": int(row["overall_score"]),
            "talk_ratio": int(row["talk_ratio"]),
            "energy": int(row["energy"]),
            "objection_handling": int(row["objection_handling"]),
            "next_steps": bool(row["next_steps"]),
            "coach_notes": row["coach_notes"],
        }

    manager_override = None
    if row["override_score"] is not None or row["override_notes"] is not None:
        manager_override = {
            "score": int(row["override_score"]) if row["override_score"] else None,
            "notes": row["override_notes"],
        }

    return {
        "call_id": row["call_id"],
        "contact_name": row["contact_name"],
        "closer": row["closer"],
        "call_date": str(row["call_date"]),
        "duration_seconds": int(row["duration_seconds"]),
        "outcome": row["outcome"],
        "scores": scores,
        "transcript": row["transcript"],
        "manager_override": manager_override,
    }


@router.get("/calls/{call_id}/audio")
async def get_call_audio(call_id: str = Path(...)):
    """Return a presigned S3 URL for the call recording."""
    row = fetch_one("SELECT recording_key FROM calls WHERE call_id = %(call_id)s", {"call_id": call_id})
    if not row or not row["recording_key"]:
        return {"error": "Recording not found"}, 404
    url = generate_presigned_url(row["recording_key"])
    return {"url": url}


@router.post("/calls/{call_id}/override")
async def save_manager_override(
    call_id: str = Path(...),
    score: int = Body(None),
    notes: str = Body(None),
):
    """Save or update a manager override for a call."""
    execute("""
        MERGE INTO manager_overrides mo
        USING (SELECT %(call_id)s AS call_id) src ON mo.call_id = src.call_id
        WHEN MATCHED THEN UPDATE SET
            override_score = %(score)s,
            override_notes = %(notes)s,
            updated_at = CURRENT_TIMESTAMP
        WHEN NOT MATCHED THEN INSERT (call_id, override_score, override_notes, created_at, updated_at)
            VALUES (%(call_id)s, %(score)s, %(notes)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, {"call_id": call_id, "score": score, "notes": notes})
    return {"status": "saved"}


@router.get("/calls/leaderboard")
async def get_leaderboard(
    client_id: str = Query(...),
    location_id: str = Query(...),
    start_date: str = Query(None),
    end_date: str = Query(None),
):
    """Return rep leaderboard stats.

    Response shape:
    {
      "reps": [
        {
          "closer": str,
          "avg_score": float,
          "close_rate": float,
          "enrolled_count": int,
          "avg_talk_ratio": float,
          "total_calls": int
        }
      ]
    }
    """
    date_filter = ""
    params = {"location_id": location_id}
    if start_date:
        date_filter += " AND c.call_date >= %(start_date)s"
        params["start_date"] = start_date
    if end_date:
        date_filter += " AND c.call_date <= %(end_date)s"
        params["end_date"] = end_date

    rows = fetch_all(f"""
        SELECT
            c.closer,
            AVG(cs.overall_score) AS avg_score,
            SUM(CASE WHEN c.outcome = 'enrolled' THEN 1 ELSE 0 END)::FLOAT
                / NULLIF(COUNT(*), 0) AS close_rate,
            SUM(CASE WHEN c.outcome = 'enrolled' THEN 1 ELSE 0 END) AS enrolled_count,
            AVG(cs.talk_ratio) AS avg_talk_ratio,
            COUNT(*) AS total_calls
        FROM calls c
        LEFT JOIN call_scores cs ON cs.call_id = c.call_id
        WHERE c.location_id = %(location_id)s {date_filter}
        GROUP BY c.closer
        ORDER BY AVG(cs.overall_score) DESC NULLS LAST
    """, params)

    return {
        "reps": [
            {
                "closer": r["closer"],
                "avg_score": round(float(r["avg_score"] or 0), 1),
                "close_rate": round(float(r["close_rate"] or 0), 3),
                "enrolled_count": int(r["enrolled_count"]),
                "avg_talk_ratio": round(float(r["avg_talk_ratio"] or 0), 1),
                "total_calls": int(r["total_calls"]),
            }
            for r in rows
        ],
    }

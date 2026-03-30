"""Background job: Score unscored calls using Claude AI."""

from lib.snowflake_client import fetch_all, execute
from lib.claude_client import score_call


def run():
    """Find calls with transcripts but no scores, and score them."""
    unscored = fetch_all("""
        SELECT c.call_id, c.transcript
        FROM calls c
        LEFT JOIN call_scores cs ON cs.call_id = c.call_id
        WHERE c.transcript IS NOT NULL
          AND cs.call_id IS NULL
        ORDER BY c.call_date DESC
        LIMIT 50
    """)

    scored_count = 0
    for call in unscored:
        try:
            result = score_call(call["transcript"])
            execute("""
                INSERT INTO call_scores (call_id, overall_score, talk_ratio, energy,
                    objection_handling, next_steps, coach_notes, scored_at)
                VALUES (%(call_id)s, %(overall_score)s, %(talk_ratio)s, %(energy)s,
                    %(objection_handling)s, %(next_steps)s, %(coach_notes)s, CURRENT_TIMESTAMP)
            """, {
                "call_id": call["call_id"],
                "overall_score": result["overall_score"],
                "talk_ratio": result["talk_ratio"],
                "energy": result["energy"],
                "objection_handling": result["objection_handling"],
                "next_steps": result["next_steps"],
                "coach_notes": result["coach_notes"],
            })
            scored_count += 1
            print(f"Scored call {call['call_id']}: {result['overall_score']}/100")
        except Exception as e:
            print(f"Failed to score call {call['call_id']}: {e}")

    print(f"Scored {scored_count}/{len(unscored)} calls")


if __name__ == "__main__":
    run()

"""Background job: Sync contacts and opportunities from GoHighLevel."""

from lib.snowflake_client import fetch_all, execute
from lib.ghl_client import GHLClient


def run():
    """Sync GHL data for all active locations."""
    locations = fetch_all("""
        SELECT location_id, ghl_location_id, ghl_api_token
        FROM locations
        WHERE ghl_api_token IS NOT NULL AND ghl_api_token != ''
    """)

    for loc in locations:
        try:
            client = GHLClient(loc["ghl_api_token"])
            sync_contacts(client, loc["location_id"])
            sync_opportunities(client, loc["location_id"])
            print(f"Synced location {loc['location_id']}")
        except Exception as e:
            print(f"Failed to sync location {loc['location_id']}: {e}")


def sync_contacts(client: GHLClient, location_id: str):
    data = client.get_contacts(limit=100)
    contacts = data.get("contacts", [])
    for contact in contacts:
        execute("""
            MERGE INTO contacts c
            USING (SELECT %(ghl_contact_id)s AS ghl_contact_id) src
            ON c.ghl_contact_id = src.ghl_contact_id
            WHEN MATCHED THEN UPDATE SET
                contact_name = %(name)s, email = %(email)s, phone = %(phone)s,
                updated_at = CURRENT_TIMESTAMP
            WHEN NOT MATCHED THEN INSERT
                (contact_id, location_id, ghl_contact_id, contact_name, email, phone, created_at, updated_at)
                VALUES (%(contact_id)s, %(location_id)s, %(ghl_contact_id)s, %(name)s, %(email)s, %(phone)s,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, {
            "contact_id": contact.get("id"),
            "location_id": location_id,
            "ghl_contact_id": contact.get("id"),
            "name": f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip(),
            "email": contact.get("email", ""),
            "phone": contact.get("phone", ""),
        })


def sync_opportunities(client: GHLClient, location_id: str):
    pipelines = client.get_pipelines()
    for pipeline in pipelines.get("pipelines", []):
        opps = client.get_opportunities(pipeline["id"])
        for opp in opps.get("opportunities", []):
            stage_name = ""
            for stage in pipeline.get("stages", []):
                if stage["id"] == opp.get("pipelineStageId"):
                    stage_name = stage["name"]
                    break

            execute("""
                MERGE INTO opportunities o
                USING (SELECT %(opp_id)s AS opportunity_id) src
                ON o.opportunity_id = src.opportunity_id
                WHEN MATCHED THEN UPDATE SET
                    stage = %(stage)s, status = %(status)s, value = %(value)s,
                    contact_name = %(contact_name)s, updated_at = CURRENT_TIMESTAMP
                WHEN NOT MATCHED THEN INSERT
                    (opportunity_id, location_id, contact_name, stage, stage_order, status, value,
                     stage_entered_at, created_at, updated_at)
                    VALUES (%(opp_id)s, %(location_id)s, %(contact_name)s, %(stage)s, 0, %(status)s, %(value)s,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, {
                "opp_id": opp["id"],
                "location_id": location_id,
                "contact_name": opp.get("contact", {}).get("name", opp.get("name", "")),
                "stage": stage_name,
                "status": opp.get("status", "open"),
                "value": float(opp.get("monetaryValue", 0) or 0),
            })


if __name__ == "__main__":
    run()

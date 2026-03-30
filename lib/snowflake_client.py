"""Snowflake database client for Revryze OS."""

import os
import snowflake.connector
from contextlib import contextmanager


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "REVRYZE"),
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
    )


@contextmanager
def cursor():
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
    finally:
        cur.close()
        conn.close()


def fetch_all(query: str, params: dict | None = None) -> list[dict]:
    with cursor() as cur:
        cur.execute(query, params or {})
        columns = [col[0].lower() for col in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def fetch_one(query: str, params: dict | None = None) -> dict | None:
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def execute(query: str, params: dict | None = None):
    with cursor() as cur:
        cur.execute(query, params or {})

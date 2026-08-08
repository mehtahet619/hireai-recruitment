"""Supabase Postgres connection helper.

Returns a psycopg2 connection if SUPABASE_DB_URL is set, else None.
Callers check for None and fall back to Valkey/memory (local dev).

ponytail: simple thread-local connection pool — upgrade to psycopg2.pool or
asyncpg if connection count becomes a bottleneck at scale.
"""
from __future__ import annotations

import threading
from typing import Optional

import psycopg2
import psycopg2.extras  # for RealDictCursor

from .config import get_settings

_local = threading.local()


def get_conn():
    """Return a live psycopg2 connection, or None if SUPABASE_DB_URL not set."""
    settings = get_settings()
    if not settings.supabase_db_url:
        return None
    conn = getattr(_local, "conn", None)
    if conn is None or conn.closed:
        conn = psycopg2.connect(settings.supabase_db_url)
        conn.autocommit = True
        _local.conn = conn
    return conn


def execute(sql: str, params: tuple = (), fetch: str = "none"):
    """Run sql against Supabase. fetch='one'|'all'|'none'. Returns rows or None."""
    conn = get_conn()
    if conn is None:
        raise RuntimeError("SUPABASE_DB_URL not configured")
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
        return None

"""Postgres connection helper for the webhook worker."""

import os

import psycopg2


def get_connection():
    """Open a psycopg2 connection using POSTGRES_* env vars."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", ""),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        dbname=os.getenv("POSTGRES_DB", "safepay"),
    )

"""Periodic job: refresh Redis balance:* cache from the account_balances view.

Safety net for drift caused by a worker crash between the Postgres commit and
the Redis SET in ledger.py, or a Redis restart/eviction wiping cached balances.
"""

import os
import time

import redis

from db import get_connection
from logging_config import setup_logging

logger = setup_logging()

RECONCILE_INTERVAL_SECONDS = int(os.getenv("RECONCILE_INTERVAL_SECONDS", "60"))

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    decode_responses=True
)


def reconcile_once() -> int:
    """Recompute every account's balance from Postgres and refresh its Redis cache. Returns count updated."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT account_id, currency, balance_cents FROM account_balances")
            rows = cur.fetchall()
    finally:
        conn.close()

    for account_id, currency, balance_cents in rows:
        redis_client.set(f"balance:{account_id}:{currency}", int(balance_cents), ex=3600)

    return len(rows)


def main():
    """Loop forever, reconciling balances on a fixed interval."""
    logger.info("Balance reconciler started (interval=%ss)", RECONCILE_INTERVAL_SECONDS)
    while True:
        try:
            count = reconcile_once()
            logger.info("Reconciled %d account balances", count)
        except Exception as e:
            logger.error("Reconciliation pass failed: %s", e)
        time.sleep(RECONCILE_INTERVAL_SECONDS)


if __name__ == '__main__':
    main()

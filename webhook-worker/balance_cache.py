"""Redis balance cache: informational only, never authoritative.

Postgres (ledger.py) remains the sole source of truth for balances. This
module only reads/writes the balance:{account_id}:{currency} cache used for
(a) an early, non-authoritative insufficient-funds hint before settlement
completes, and (b) the gateway's /balance endpoint fast path.
"""

import os

import redis

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    decode_responses=True
)

CACHE_TTL_SECONDS = 3600


def get_cached_balance(account_id: str, currency: str) -> int | None:
    """Return the cached balance in cents, or None on a cache miss."""
    value = redis_client.get(f"balance:{account_id}:{currency}")
    return int(value) if value is not None else None


def is_cached_insufficient(account_id: str, currency: str, amount_cents: int) -> str | None:
    """Return a reason string if the cache clearly shows insufficient funds, else None.

    A cache miss or an apparently-sufficient balance both return None \u2014 callers
    must never treat None as an approval, only as "no reason to reject yet".
    """
    cached_balance = get_cached_balance(account_id, currency)
    if cached_balance is not None and cached_balance < amount_cents:
        return f"insufficient funds (cached): balance={cached_balance} need={amount_cents}"
    return None


def debit(account_id: str, currency: str, balance_before_cents: int, amount_cents: int) -> None:
    """Set the source account's cache to its new post-debit balance.

    Safe as a plain SET (not an atomic decrement) because the caller already
    holds Postgres's FOR UPDATE lock on this account while it reads
    balance_before_cents, so no concurrent debit can be in flight.
    """
    redis_client.set(
        f"balance:{account_id}:{currency}",
        balance_before_cents - amount_cents,
        ex=CACHE_TTL_SECONDS,
    )


def credit(account_id: str, currency: str, amount_cents: int) -> None:
    """Atomically increment the destination account's cache after an approved credit.

    Uses INCRBY (not read-then-SET) because credits aren't serialized by any
    Postgres lock \u2014 a read-then-write here could lose an update if two
    credits land on the same account concurrently. INCRBY is correct even on
    a cold/missing key, since a pure-recipient account's true starting
    balance is 0.
    """
    key = f"balance:{account_id}:{currency}"
    redis_client.incrby(key, amount_cents)
    redis_client.expire(key, CACHE_TTL_SECONDS)

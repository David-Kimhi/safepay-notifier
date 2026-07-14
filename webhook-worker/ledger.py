"""Postgres ledger logic: accounts, balances, double-entry settlement."""

import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from db import get_connection

OPENING_BALANCE_CENTS = int(os.getenv("OPENING_BALANCE_CENTS", "100000"))


def float_amount_to_cents(amount) -> int:
    """Convert gateway float amount to integer cents (half-up rounding)."""
    return int(Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)


def _account_type(account_id: str) -> str:
    """Infer account_type from account_id prefix."""
    if account_id.startswith("merchant_"):
        return "merchant"
    if account_id.startswith("system:"):
        return "system"
    return "customer"


def _equity_account(currency: str) -> str:
    """Return system equity account id for a currency."""
    return f"system:equity:{currency}"


def _parse_timestamp(value) -> datetime | None:
    """Parse ISO string or unix timestamp from Kafka payload."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _ensure_account(cur, account_id: str, currency: str) -> None:
    """Create account row if missing (no-op on conflict)."""
    cur.execute(
        """
        INSERT INTO accounts (account_id, currency, account_type)
        VALUES (%s, %s, %s)
        ON CONFLICT (account_id) DO NOTHING
        """,
        (account_id, currency, _account_type(account_id)),
    )


def _seed_opening_balance(cur, account_id: str, currency: str) -> None:
    """Credit new customer/merchant accounts from system equity (demo bootstrap)."""
    if _account_type(account_id) == "system":
        return

    cur.execute(
        "SELECT 1 FROM ledger_entries WHERE account_id = %s LIMIT 1",
        (account_id,),
    )
    if cur.fetchone():
        return

    equity = _equity_account(currency)
    _ensure_account(cur, equity, currency)
    idempotency_key = f"opening:{account_id}"

    cur.execute(
        """
        INSERT INTO transactions (
            gateway_transaction_id,
            idempotency_key,
            source_account_id,
            destination_account_id,
            amount_cents,
            currency,
            payment_type,
            status,
            processed_at
        )
        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, 'opening_balance', 'approved', now())
        RETURNING id
        """,
        (idempotency_key, equity, account_id, OPENING_BALANCE_CENTS, currency),
    )
    txn_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO ledger_entries (transaction_id, account_id, entry_type, amount_cents)
        VALUES (%s, %s, 'debit', %s), (%s, %s, 'credit', %s)
        """,
        (txn_id, equity, OPENING_BALANCE_CENTS, txn_id, account_id, OPENING_BALANCE_CENTS),
    )


def _get_balance_cents(cur, account_id: str, currency: str) -> int:
    """Read current balance from account_balances view."""
    cur.execute(
        """
        SELECT balance_cents
        FROM account_balances
        WHERE account_id = %s AND currency = %s
        """,
        (account_id, currency),
    )
    row = cur.fetchone()
    return int(row[0]) if row else 0


def settle_payment(payment_data: dict) -> tuple[str, str | None]:
    """Settle one payment in Postgres: pending → approved or rejected with ledger entries."""
    required = (
        "idempotency_key",
        "gateway_transaction_id",
        "source_account_id",
        "destination_account_id",
        "amount",
        "currency",
        "payment_type",
    )
    missing = [field for field in required if not payment_data.get(field)]
    if missing:
        raise ValueError(f"missing fields: {', '.join(missing)}")

    idempotency_key = payment_data["idempotency_key"]
    gateway_txn_id = payment_data["gateway_transaction_id"]
    source_id = payment_data["source_account_id"]
    dest_id = payment_data["destination_account_id"]
    currency = payment_data["currency"]
    amount_cents = float_amount_to_cents(payment_data["amount"])
    payment_type = payment_data["payment_type"]
    source_ts = _parse_timestamp(payment_data.get("source_account_timestamp"))
    gateway_ts = _parse_timestamp(payment_data.get("gateway_received_timestamp"))

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, reject_reason FROM transactions WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
                existing = cur.fetchone()
                if existing:
                    return "duplicate", existing[1]

                _ensure_account(cur, source_id, currency)
                _ensure_account(cur, dest_id, currency)
                _seed_opening_balance(cur, source_id, currency)

                cur.execute(
                    """
                    INSERT INTO transactions (
                        gateway_transaction_id,
                        idempotency_key,
                        source_account_id,
                        destination_account_id,
                        amount_cents,
                        currency,
                        payment_type,
                        status,
                        source_account_timestamp,
                        gateway_received_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
                    RETURNING id
                    """,
                    (
                        gateway_txn_id,
                        idempotency_key,
                        source_id,
                        dest_id,
                        amount_cents,
                        currency,
                        payment_type,
                        source_ts,
                        gateway_ts,
                    ),
                )
                txn_id = cur.fetchone()[0]

                balance = _get_balance_cents(cur, source_id, currency)
                if balance < amount_cents:
                    reason = f"insufficient funds: balance={balance} need={amount_cents}"
                    cur.execute(
                        """
                        UPDATE transactions
                        SET status = 'rejected', reject_reason = %s, processed_at = now()
                        WHERE id = %s
                        """,
                        (reason, txn_id),
                    )
                    return "rejected", reason

                cur.execute(
                    """
                    INSERT INTO ledger_entries (transaction_id, account_id, entry_type, amount_cents)
                    VALUES (%s, %s, 'debit', %s), (%s, %s, 'credit', %s)
                    """,
                    (txn_id, source_id, amount_cents, txn_id, dest_id, amount_cents),
                )
                cur.execute(
                    """
                    UPDATE transactions
                    SET status = 'approved', processed_at = now()
                    WHERE id = %s
                    """,
                    (txn_id,),
                )
                return "approved", None
    finally:
        conn.close()

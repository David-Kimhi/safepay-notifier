-- SafePay Notifier — ledger schema
-- Amounts: BIGINT cents only. No floats in DB.

BEGIN;

-- ---------------------------------------------------------------------------
-- accounts — identity + currency; balance derived from ledger_entries
-- ---------------------------------------------------------------------------
CREATE TABLE accounts (
    account_id   TEXT        PRIMARY KEY,
    currency     CHAR(3)     NOT NULL,
    account_type TEXT        NOT NULL DEFAULT 'customer'
                             CHECK (account_type IN ('customer', 'merchant', 'system')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- transactions — one row per gateway payment / client transaction
-- ---------------------------------------------------------------------------
CREATE TABLE transactions (
    id                       BIGSERIAL   PRIMARY KEY,
    gateway_transaction_id   UUID        NOT NULL UNIQUE,
    idempotency_key          TEXT        NOT NULL UNIQUE,
    source_account_id        TEXT        NOT NULL REFERENCES accounts (account_id),
    destination_account_id   TEXT        NOT NULL REFERENCES accounts (account_id),
    amount_cents             BIGINT      NOT NULL CHECK (amount_cents > 0),
    currency                 CHAR(3)     NOT NULL,
    payment_type             TEXT        NOT NULL,
    status                   TEXT        NOT NULL DEFAULT 'pending'
                                         CHECK (status IN ('pending', 'approved', 'rejected', 'failed')),
    reject_reason            TEXT,
    source_account_timestamp TIMESTAMPTZ,
    gateway_received_at      TIMESTAMPTZ,
    processed_at             TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT transactions_distinct_accounts
        CHECK (source_account_id <> destination_account_id),
    CONSTRAINT transactions_currency_match
        CHECK (currency ~ '^[A-Z]{3}$')
);

CREATE INDEX idx_transactions_status ON transactions (status);
CREATE INDEX idx_transactions_source ON transactions (source_account_id);
CREATE INDEX idx_transactions_created_at ON transactions (created_at);

-- ---------------------------------------------------------------------------
-- ledger_entries — append-only double-entry log
-- Each approved transaction: debit source, credit destination (same amount_cents)
-- ---------------------------------------------------------------------------
CREATE TABLE ledger_entries (
    id             BIGSERIAL   PRIMARY KEY,
    transaction_id BIGINT      NOT NULL REFERENCES transactions (id),
    account_id     TEXT        NOT NULL REFERENCES accounts (account_id),
    entry_type     TEXT        NOT NULL CHECK (entry_type IN ('debit', 'credit')),
    amount_cents   BIGINT      NOT NULL CHECK (amount_cents > 0),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ledger_entries_account_id ON ledger_entries (account_id);
CREATE INDEX idx_ledger_entries_transaction_id ON ledger_entries (transaction_id);
CREATE INDEX idx_ledger_entries_created_at ON ledger_entries (created_at);

-- Append-only: block UPDATE and DELETE
CREATE OR REPLACE FUNCTION prevent_ledger_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'ledger_entries is append-only';
END;
$$;

CREATE TRIGGER ledger_entries_no_update
    BEFORE UPDATE OR DELETE ON ledger_entries
    FOR EACH ROW
    EXECUTE FUNCTION prevent_ledger_mutation();

-- Double-entry: debits must equal credits per transaction
CREATE OR REPLACE FUNCTION enforce_balanced_ledger_entries()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    debit_total  BIGINT;
    credit_total BIGINT;
BEGIN
    SELECT
        COALESCE(SUM(amount_cents) FILTER (WHERE entry_type = 'debit'), 0),
        COALESCE(SUM(amount_cents) FILTER (WHERE entry_type = 'credit'), 0)
    INTO debit_total, credit_total
    FROM ledger_entries
    WHERE transaction_id = NEW.transaction_id;

    IF debit_total <> credit_total THEN
        RAISE EXCEPTION
            'unbalanced ledger for transaction %: debit=% credit=%',
            NEW.transaction_id, debit_total, credit_total;
    END IF;

    RETURN NEW;
END;
$$;

CREATE CONSTRAINT TRIGGER ledger_entries_balanced
    AFTER INSERT ON ledger_entries
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    EXECUTE FUNCTION enforce_balanced_ledger_entries();

-- ---------------------------------------------------------------------------
-- account_balances — derived view for worker startup / reconciliation
-- credit increases balance, debit decreases
-- ---------------------------------------------------------------------------
CREATE VIEW account_balances AS
SELECT
    a.account_id,
    a.currency,
    COALESCE(
        SUM(
            CASE
                WHEN le.entry_type = 'credit' THEN le.amount_cents
                WHEN le.entry_type = 'debit'  THEN -le.amount_cents
            END
        ),
        0
    )::BIGINT AS balance_cents
FROM accounts a
LEFT JOIN ledger_entries le ON le.account_id = a.account_id
GROUP BY a.account_id, a.currency;

-- System equity accounts — opening-balance credits pair with debit here (one per currency)
INSERT INTO accounts (account_id, currency, account_type) VALUES
    ('system:equity:USD', 'USD', 'system'),
    ('system:equity:ILS', 'ILS', 'system');

COMMIT;

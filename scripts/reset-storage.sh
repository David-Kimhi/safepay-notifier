#!/usr/bin/env bash
# reset-storage — wipe Kafka topic data + Postgres ledger tables (demo reset).
#
# Usage (from repo root):
#   ./scripts/reset-storage.sh
#
# Optional:
#   TOPIC=payments ./scripts/reset-storage.sh
#   SKIP_REDIS=1 ./scripts/reset-storage.sh   # leave Redis alone
#
# Stops producers/consumers briefly so topic delete is clean, then starts them again.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TOPIC="${TOPIC:-payments}"
GROUP="${GROUP:-payment_workers}"

echo "==> Stopping gateway, worker, simulator..."
docker compose stop payment-gateway webhook-worker bank-simulator 2>/dev/null || true

echo "==> Waiting for consumer group '${GROUP}' to have no members..."
# Kafka refuses --delete while any member is still in the group (session may linger ~10–45s).
empty=0
for i in $(seq 1 30); do
  desc="$(docker compose exec -T kafka kafka-consumer-groups \
    --bootstrap-server localhost:9092 \
    --describe --group "${GROUP}" 2>&1 || true)"
  if echo "$desc" | grep -qiE 'does not exist|Consumer group .* does not exist|no active members'; then
    empty=1
    break
  fi
  # "describe" with members shows CONSUMER-ID / MEMBER-ID lines; no members → Stable with empty or error
  if ! echo "$desc" | grep -qE 'CONSUMER-ID|MEMBER-ID|consumer-'; then
    # Group exists but no member rows (only header / STATE)
    if echo "$desc" | grep -q 'GROUP'; then
      empty=1
      break
    fi
  fi
  sleep 2
done
if [[ "$empty" -ne 1 ]]; then
  echo "    (group still has members after wait — will skip group delete; topic wipe is enough)"
fi

echo "==> Clearing Postgres tables..."
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
BEGIN;
TRUNCATE ledger_entries, transactions, accounts RESTART IDENTITY CASCADE;
INSERT INTO accounts (account_id, currency, account_type) VALUES
    ('system:equity:USD', 'USD', 'system'),
    ('system:equity:ILS', 'ILS', 'system');
COMMIT;
SELECT
    (SELECT count(*) FROM accounts) AS accounts,
    (SELECT count(*) FROM transactions) AS transactions,
    (SELECT count(*) FROM ledger_entries) AS ledger_entries;
SQL

echo "==> Deleting Kafka topic '${TOPIC}'..."
docker compose exec -T kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --delete --topic "${TOPIC}" 2>/dev/null || echo "(topic missing or already gone)"

if [[ "$empty" -eq 1 ]]; then
  echo "==> Deleting consumer group '${GROUP}'..."
  docker compose exec -T kafka kafka-consumer-groups \
    --bootstrap-server localhost:9092 \
    --delete --group "${GROUP}" >/dev/null 2>&1 \
    || echo "(group already gone)"
else
  echo "==> Skipping consumer group delete (not empty). Safe: new empty topic has no lag to worry about."
fi

# Wait for delete to finish, then recreate empty topic
sleep 2
docker compose exec -T kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --create --topic "${TOPIC}" \
  --partitions 1 --replication-factor 1 \
  2>/dev/null || echo "(topic already recreated / auto-create will handle it)"

if [[ "${SKIP_REDIS:-0}" != "1" ]]; then
  echo "==> Flushing Redis (idempotency keys)..."
  docker compose exec -T redis redis-cli FLUSHALL >/dev/null
fi

echo "==> Starting gateway + worker..."
docker compose start payment-gateway webhook-worker

echo "==> Done. Postgres empty (equity seeds only); Kafka topic '${TOPIC}' empty."
echo "    Start simulator when ready: MAX_SIM_DAYS=7 docker compose up -d bank-simulator"

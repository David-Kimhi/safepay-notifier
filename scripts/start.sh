#!/usr/bin/env bash
# start.sh — bring up the full stack, optionally wiping all data first.
#
# Usage (from repo root):
#   ./scripts/start.sh              # normal start (keep existing Postgres/Redis data)
#   ./scripts/start.sh --fresh      # truncate Postgres tables + flush Redis, THEN start everything
#   FRESH_START=1 ./scripts/start.sh   # same as --fresh, via env var
#
# Fresh start only touches Postgres tables and Redis keys (accounts, transactions,
# ledger_entries, all cache/idempotency keys). Kafka is left alone.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FRESH="${FRESH_START:-0}"
for arg in "$@"; do
  case "$arg" in
    --fresh|-f) FRESH=1 ;;
  esac
done

open_url() {
  local url="$1"
  if command -v open >/dev/null 2>&1; then
    open "$url"        # macOS
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url"    # Linux
  else
    echo "    Open manually: $url"
  fi
}

echo "==> Starting infra (postgres, redis, zookeeper, kafka) + monitoring (grafana, prometheus, loki)..."
docker compose up -d postgres redis zookeeper kafka cadvisor prometheus loki promtail grafana

echo "==> Waiting for Postgres to accept connections..."
until docker compose exec -T postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; do
  sleep 1
done

echo "==> Waiting for Redis to accept connections..."
until docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; do
  sleep 1
done

if [[ "$FRESH" == "1" ]]; then
  echo "==> --fresh: truncating Postgres tables..."
  docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
BEGIN;
TRUNCATE ledger_entries, transactions, accounts RESTART IDENTITY CASCADE;
INSERT INTO accounts (account_id, currency, account_type) VALUES
    ('system:equity:USD', 'USD', 'system'),
    ('system:equity:ILS', 'ILS', 'system');
COMMIT;
SQL

  echo "==> --fresh: flushing Redis..."
  docker compose exec -T redis redis-cli FLUSHALL >/dev/null

  echo "    Postgres + Redis wiped (equity accounts reseeded)."
else
  echo "==> Keeping existing Postgres/Redis data (pass --fresh to wipe first)."
fi

echo "==> Starting gateway, worker, balance-reconciler, simulator..."
docker compose up -d --build payment-gateway webhook-worker balance-reconciler bank-simulator

echo "==> Waiting for Grafana to be ready..."
until curl -sf http://localhost:3000/api/health >/dev/null 2>&1; do
  sleep 1
done

echo "==> Opening Grafana dashboards..."
open_url "http://localhost:3000/dashboards"

echo "==> Done."

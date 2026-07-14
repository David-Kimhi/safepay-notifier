# SafePay Notifier

**Mock payment-notification system** demonstrating Kafka as a buffer, Redis idempotency, a Postgres double-entry ledger, observability, and simulated day/night bank traffic.

## System sketch

```
 bank-simulator          payment-gateway              Kafka
                  ──►   (FastAPI, Redis         ──►  (payments
                           idempotency)                  topic)
                                                         │
                                                         ▼
                                                   webhook-worker
                                              (settle + ledger in Postgres)
                                                         │
                                                         ▼
                                              Prometheus / Grafana / Loki
```

- **bank-simulator**: fake customers with day/night activity; optional `MAX_SIM_DAYS` stop.
- **payment-gateway**: accepts payments (`202`), Redis idempotency, produces to Kafka.
- **webhook-worker**: consumes Kafka; writes `transactions` + append-only double-entry `ledger_entries` in Postgres.
- **monitoring**: Grafana + Prometheus + Loki (see [monitoring/README.md](monitoring/README.md)).

## Structure

| Path | Role |
|------|------|
| `payment-gateway/` | FastAPI API, `/pay`, `/metrics` |
| `webhook-worker/` | Kafka consumer, Postgres ledger settlement |
| `bank-simulator/` | Day/night population simulator |
| `postgres/` | Schema init + `psql.sh` helper |
| `scripts/` | Demo helpers (e.g. `reset-storage.sh`) |
| `load-test/` | Fixed-RPS load tool (`simulate.py`) |
| `monitoring/` | Prometheus, Grafana, Loki configs |
| `docker-compose.yml` | Full local stack |

## Run the demo

```bash
# Full stack (apps + monitoring + simulator)
docker compose up -d --build

# Finite sim run (e.g. 10 simulated days; ~12 min at 3s/sim-hour)
MAX_SIM_DAYS=10 docker compose up -d --build bank-simulator

# Watch traffic
docker compose logs -f bank-simulator
docker compose logs -f webhook-worker

# Query Postgres
./postgres/psql.sh
./postgres/psql.sh -c "SELECT count(*) FROM transactions;"

# Wipe Kafka topic + Postgres tables + Redis keys (clean demo)
./scripts/reset-storage.sh

# Fixed load test (optional; gateway must be up)
python3 load-test/simulate.py --rps 20 --duration 10
```

### Useful env knobs (simulator)

| Variable | Default | Meaning |
|----------|---------|---------|
| `INITIAL_POPULATION` | `10000` | Users in the pool |
| `REAL_SECONDS_PER_SIM_HOUR` | `3` | Wall-clock seconds per simulated hour |
| `MAX_SIM_DAYS` | `0` | Stop after N sim days (`0` = unlimited) |
| `NORMAL_P_DAY` / `NORMAL_P_NIGHT` | `0.015` / `0.001` | Per-user act probability per hour |

Details: [bank-simulator/README.md](bank-simulator/README.md).

### URLs

| Service | URL |
|---------|-----|
| Grafana | http://localhost:3000 (`admin` / `admin`) |
| Payment API (Swagger) | http://localhost:8000/docs |
| AKHQ (Kafka UI) | http://localhost:8080 |
| Prometheus | http://localhost:9090 |

### What to look for

1. **Day vs night**: simulator logs `Day N, hour HH (day|night)`; more `sent=` during daytime (09–20).
2. **Kafka as buffer** — Grafana → Explore → **Loki** (metric queries):
   - Produce: `sum(rate({container=~".*payment-gateway.*"} |= "Payment request sent to Kafka" [1m]))`
   - Consume: `sum(rate({container=~".*webhook-worker.*"} |= "Approved:" [1m]))`
   - Highs ≈ simulated days, lows ≈ nights. When the worker is slower than produce, lag builds in Kafka and the API still returns `202`.
3. **Prometheus**: `rate(http_requests_total{handler="/pay"}[1m])` — higher during simulated day.
4. **Postgres**: `./postgres/psql.sh -c "SELECT status, count(*) FROM transactions GROUP BY status;"`

## Roadmap

- [x] Payment gateway + Kafka + Redis idempotency
- [x] Observability stack (Grafana / Prometheus / Loki)
- [x] Load test script
- [x] Bank population simulator (normal persona, `MAX_SIM_DAYS`)
- [x] Postgres schema + worker ledger settle (approve / reject)
- [ ] Redis atomic balance check + holds (hot path)
- [ ] Dead letter queue for failed payments
- [ ] Heavy user + attacker personas
- [ ] CI (GitHub Actions)
- [ ] Kubernetes manifests

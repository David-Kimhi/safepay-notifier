# SafePay Notifier

**Mock payment-notification system** demonstrating Kafka, Redis, idempotency, observability, and simulated bank traffic.

## System sketch

```
 bank-simulator          payment-gateway              Kafka
                  ──►   (FastAPI, Redis         ──►  (payments
                           idempotency)                  topic)
                               │                         │
                               │                         ▼
                               │                   webhook-worker
                               │              (balance check in Redis,
                               │               ledger in Postgres)
                               ▼
                          Prometheus / Grafana / Loki
```

- **bank-simulator**: long-running fake customers (normal users today; heavy/attacker later).
- **payment-gateway**: accepts payments (202), idempotency via Redis, produces to Kafka.
- **webhook-worker**: consumes Kafka; Redis for fast balance check/holds; Postgres for ledger.
- **monitoring**: Grafana + Prometheus + Loki (see [monitoring/README.md](monitoring/README.md)).

## Structure

| Path | Role |
|------|------|
| `payment-gateway/` | FastAPI API, `/pay`, `/metrics` |
| `webhook-worker/` | Kafka consumer, balance + ledger |
| `bank-simulator/` | Day/night population simulator |
| `load-test/` | Fixed-RPS load tool (`simulate.py`) |
| `monitoring/` | Prometheus, Grafana, Loki configs |
| `docker-compose.yml` | Full local stack |

## Run the demo

```bash
# Start core stack + monitoring + simulator
docker compose up -d

# Watch simulated bank traffic
docker compose logs -f bank-simulator

# Fixed load test (optional)
python3 load-test/simulate.py --rps 20 --duration 10
```

### URLs

| Service | URL |
|---------|-----|
| Grafana | http://localhost:3000 |
| Payment API (Swagger) | http://localhost:8000/docs |
| AKHQ (Kafka UI) | http://localhost:8080 |
| Prometheus | http://localhost:9090 |

### What to look for

1. **bank-simulator logs**: `Day N, hour HH (day|night)` every 3 seconds; more `sent=` during daytime hours.
2. **Grafana → Explore → Prometheus**: `rate(http_requests_total{handler="/pay"}[1m])` — higher during simulated day.
3. **Grafana → Explore → Loki**: `{container=~".*payment-gateway.*"}`

## Roadmap

- [x] Payment gateway + Kafka + Redis idempotency
- [x] Observability stack (Grafana / Prometheus / Loki)
- [x] Load test script
- [x] Bank population simulator (normal persona)
- [ ] Redis balance check + Postgres ledger 
- [ ] Dead letter queue for failed payments
- [ ] Heavy user + attacker personas
- [ ] CI (GitHub Actions)
- [ ] Kubernetes manifests

# SafePay Notifier

**Mock payment-notification system** (in development) to demonstrate Kafka, Redis, Docker, port routing, and idempotency.

## System sketch

```
    Client
       │ Idempotency-Key
       ▼
┌─────────────────┐     transactions      ┌──────────────┐
│ payment-gateway │ ───────────────────► │    Kafka     │
│   (FastAPI)     │        produce        │   (topic)    │
└────────┬────────┘                       └──────┬───────┘
         │                                       │ consume
         │ exists?                               ▼
         ▼                                 ┌──────────────┐
    ┌────────┐                             │webhook-worker│
    │ Redis  │ ◄──────────────────────────│  (consumer)  │
    └────────┘   txn_id / idempotency     └──────────────┘
```

Gateway checks Redis (idempotency key + racing cond), produces to Kafka; worker consumes, checks Redis (transaction_id), commits on success. Postgres and AKHQ are in the stack; Zookeeper backs Kafka.

## Structure

- **payment-gateway**: FastAPI, Kafka producer, Redis for request idempotency.
- **webhook-worker**: Kafka consumer, Redis for processing idempotency (skip if already processed).
- **Docker**: All services in `docker-compose`; internal routing via `kafka`/`redis` hostnames; external ports (e.g. 9092, 6379, 5432, 8080) in `.env`.

## Roadmap

- [ ] Connect Redis to worker so idempotency is global (gateway + worker share same keys/state).
- [ ] Store and log data in Postgres.
- [ ] Script demo to test the system end-to-end.
- [ ] Demo UI (Streamlit or similar).
- [ ] Demonstrate k8s

# Bank simulator

Long-running container that simulates a population of bank customers making purchases through the payment gateway.

## Components

| File | What it does |
|------|----------------|
| `simulator/main.py` | Starts the sim: reads env/CLI, builds the pool, runs the engine loop. |
| `simulator/clock.py` | Simulated time. Tracks day/hour (09–20 = day, 21–08 = night). One sim hour = 3 real seconds. |
| `simulator/population.py` | User pool. `add_normal_users(10_000)` creates stable `user_id_*` records and picks who acts each hour. |
| `simulator/personas/base.py` | `Persona` interface — how a user type behaves (activity rate, payment shape). |
| `simulator/personas/normal.py` | Normal customer: buys more by day, rarely at night; amounts $10–500. |
| `simulator/engine.py` | Main loop each hour: sample actors → send payments → log stats → advance clock. |
| `simulator/gateway_client.py` | HTTP client: `POST /pay` with idempotency key, spreads requests across the hour window. |

```text
main → engine → clock (what hour is it?)
              → population (who acts?)
              → persona (how do they pay?)
              → gateway_client (send to payment-gateway)
```

## What it does

- Seeds a pool of **normal** users (`add_normal_users`, 10,000 by default).
- Runs a **day/night clock**: 1 simulated hour = 3 real seconds (full day ≈ 72 seconds).
- **Daytime** (09:00–20:59): users are more likely to purchase.
- **Night** (21:00–08:59): much lower activity.
- Sends `POST /pay` with realistic payloads and unique idempotency keys.

## Run with Docker

```bash
docker compose up -d bank-simulator
docker compose logs -f bank-simulator
```

## Run locally

```bash
pip install -r requirements.txt
python -m simulator.main --url http://localhost:8000 --population 1000
```

Use a smaller `--population` for quick local tests.

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `GATEWAY_URL` | `http://localhost:8000` | Payment gateway base URL |
| `INITIAL_POPULATION` | `10000` | Normal users added at startup |
| `REAL_SECONDS_PER_SIM_HOUR` | `3` | Real seconds per simulated hour |
| `NORMAL_P_DAY` | `0.015` | Per-user purchase probability per daytime hour |
| `NORMAL_P_NIGHT` | `0.001` | Per-user purchase probability per night hour |

## Extending

- New personas: implement `Persona` in `simulator/personas/` and register in `PopulationPool`.
- Add more users at runtime: call `pool.add_normal_users(10_000)` (CLI/API wiring later).

Future: **heavy** users (high volume), **attackers** (duplicate keys, bursts).

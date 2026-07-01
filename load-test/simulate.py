"""
Load simulator for the SafePay payment-gateway /pay endpoint.

Generates realistic-looking payment requests at a target rate (requests
per second) and reports basic throughput/latency stats.

Usage:
    python simulate.py --rps 20 --duration 10
    python simulate.py --rps 50 --duration 30 --url http://localhost:8000
"""

import argparse
import asyncio
import random
import time
import uuid
from datetime import datetime, timezone

import httpx

MERCHANTS = [f"merchant_{i:03d}" for i in range(20)]
CURRENCIES = ["ILS", "USD"]


def build_payment() -> dict:
    """Create a single random payment payload."""
    return {
        "source_account_id": f"user_id_{random.randint(0, 10_000)}",
        "destination_account_id": random.choice(MERCHANTS),
        "amount": round(random.uniform(0, 6_000), 2),
        "currency": random.choice(CURRENCIES),
        "payment_type": "purchase",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def send_one(client: httpx.AsyncClient, url: str) -> dict:
    """Send a single payment request and return its result."""
    payload = build_payment()
    headers = {"Idempotency-Key": str(uuid.uuid4())}
    start = time.perf_counter()
    try:
        resp = await client.post(f"{url}/pay", json=payload, headers=headers)
        latency = time.perf_counter() - start
        return {"ok": resp.status_code < 400, "status": resp.status_code, "latency": latency}
    except Exception as exc:
        latency = time.perf_counter() - start
        return {"ok": False, "status": None, "latency": latency, "error": repr(exc)}


async def run_load(rps: int, duration: int, url: str) -> None:
    """Fire `rps` requests per second for `duration` seconds."""
    total = rps * duration
    interval = 1.0 / rps
    print(f"Sending {total} requests at {rps} req/s for {duration}s to {url}/pay")

    tasks = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        loop_start = time.perf_counter()
        for i in range(total):
            tasks.append(asyncio.create_task(send_one(client, url)))
            # Pace launches evenly across each second.
            target = loop_start + (i + 1) * interval
            sleep_for = target - time.perf_counter()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

        results = await asyncio.gather(*tasks)
        wall = time.perf_counter() - loop_start

    report(results, wall)


def report(results: list[dict], wall: float) -> None:
    """Print a summary of the run."""
    n = len(results)
    ok = sum(1 for r in results if r["ok"])
    failed = n - ok
    latencies = sorted(r["latency"] for r in results)

    def pct(p: float) -> float:
        if not latencies:
            return 0.0
        idx = min(len(latencies) - 1, int(p / 100 * len(latencies)))
        return latencies[idx]

    status_counts: dict = {}
    for r in results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    print("\n--- Results ---")
    print(f"Total requests : {n}")
    print(f"Succeeded      : {ok}")
    print(f"Failed         : {failed}")
    print(f"Wall time      : {wall:.2f}s")
    print(f"Actual rate    : {n / wall:.1f} req/s")
    print(f"Status codes   : {status_counts}")
    if latencies:
        print(f"Latency avg    : {sum(latencies) / n * 1000:.1f} ms")
        print(f"Latency p50    : {pct(50) * 1000:.1f} ms")
        print(f"Latency p95    : {pct(95) * 1000:.1f} ms")
        print(f"Latency p99    : {pct(99) * 1000:.1f} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load simulator for payment-gateway /pay")
    parser.add_argument("--rps", type=int, default=10, help="Requests per second")
    parser.add_argument("--duration", type=int, default=10, help="Duration in seconds")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="Base URL")
    args = parser.parse_args()

    asyncio.run(run_load(args.rps, args.duration, args.url))


if __name__ == "__main__":
    main()

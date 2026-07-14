import asyncio
import logging
import time
import uuid

import httpx

logger = logging.getLogger(__name__)


async def send_payment(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
) -> dict:
    headers = {"Idempotency-Key": str(uuid.uuid4())}
    start = time.perf_counter()
    try:
        resp = await client.post(f"{url}/pay", json=payload, headers=headers)
        latency = time.perf_counter() - start
        
        # Build the return value
        return_value = {
            "ok": resp.status_code < 400,
            "status": resp.status_code,
            "latency": latency,
        }
        
        # Add error message if there is an error
        if resp.status_code >= 400:
            logger.warning("pay failed %s: %s", resp.status_code, resp.text)
            return_value["error"] = resp.text
            
        return return_value
    except Exception as exc:
        latency = time.perf_counter() - start
        return {
            "ok": False,
            "status": None,
            "latency": latency,
            "error": repr(exc),
        }


async def send_batch(
    client: httpx.AsyncClient,
    url: str,
    actors: list[tuple],
    window_seconds: float,
) -> list[dict]:
    """Send payments spread evenly across window_seconds."""
    if not actors:
        return []

    interval = window_seconds / len(actors)
    results: list[dict] = []
    batch_start = time.perf_counter()

    for i, (user, persona) in enumerate(actors):
        payload = persona.build_payment(user)
        result = await send_payment(client, url, payload)
        results.append(result)

        target = batch_start + (i + 1) * interval
        sleep_for = target - time.perf_counter()
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)

    return results

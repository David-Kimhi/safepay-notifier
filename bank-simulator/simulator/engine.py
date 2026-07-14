import asyncio
import logging
import signal

import httpx

from simulator.clock import SimClock
from simulator.gateway_client import send_batch
from simulator.population import PopulationPool

logger = logging.getLogger(__name__)


class SimulationEngine:
    def __init__(
        self,
        pool: PopulationPool,
        clock: SimClock,
        gateway_url: str,
        max_sim_days: int | None = None,
    ) -> None:
        self.pool = pool
        self.clock = clock
        self.gateway_url = gateway_url.rstrip("/")
        self.max_sim_days = max_sim_days
        self._stop = asyncio.Event()
        self._day_stats = {"sent": 0, "ok": 0, "failed": 0}

    def request_stop(self) -> None:
        self._stop.set()

    def _log_hour_stats(self, tick, results: list[dict]) -> None:
        sent = len(results)
        ok = sum(1 for r in results if r["ok"])
        failed = sent - ok
        self._day_stats["sent"] += sent
        self._day_stats["ok"] += ok
        self._day_stats["failed"] += failed

        period = "day" if tick.is_day else "night"
        logger.info(
            "Hour %02d (%s): sent=%s ok=%s failed=%s pool=%s",
            tick.hour,
            period,
            sent,
            ok,
            failed,
            self.pool.size,
        )

    def _log_day_summary(self, sim_day: int) -> None:
        s = self._day_stats
        logger.info(
            "Day %s summary: sent=%s ok=%s failed=%s",
            sim_day,
            s["sent"],
            s["ok"],
            s["failed"],
        )
        self._day_stats = {"sent": 0, "ok": 0, "failed": 0}

    async def run(self) -> None:
        logger.info(
            "Simulation started: pool=%s gateway=%s sec_per_hour=%s max_sim_days=%s",
            self.pool.size,
            self.gateway_url,
            self.clock.real_seconds_per_hour,
            self.max_sim_days or "unlimited",
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            while not self._stop.is_set():
                tick = self.clock.current()
                actors = self.pool.sample_actors(tick.hour)
                results = await send_batch(
                    client,
                    self.gateway_url,
                    actors,
                    self.clock.real_seconds_per_hour,
                )
                self._log_hour_stats(tick, results)

                day_ended = self.clock.advance()
                if day_ended:
                    self._log_day_summary(tick.sim_day)
                    if self.max_sim_days is not None and tick.sim_day >= self.max_sim_days:
                        logger.info(
                            "Reached MAX_SIM_DAYS=%s; stopping",
                            self.max_sim_days,
                        )
                        self.request_stop()

        logger.info("Simulation stopped.")

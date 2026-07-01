import argparse
import asyncio
import logging
import os
import signal

from simulator.clock import SimClock
from simulator.engine import SimulationEngine
from simulator.personas.normal import NormalPersona
from simulator.population import PopulationPool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def build_pool(initial_population: int) -> PopulationPool:
    pool = PopulationPool()
    normal = NormalPersona()
    pool.register_persona(normal)
    size = pool.add_normal_users(initial_population, persona=normal)
    logger.info("Population seeded: %s normal users", size)
    return pool


async def run_simulation(
    gateway_url: str,
    initial_population: int,
    seconds_per_hour: float,
) -> None:
    pool = build_pool(initial_population)
    clock = SimClock(real_seconds_per_hour=seconds_per_hour)
    engine = SimulationEngine(pool=pool, clock=clock, gateway_url=gateway_url)

    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, engine.request_stop)
    except NotImplementedError:
        # add_signal_handler not available on all platforms
        pass

    await engine.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bank population purchase simulator")
    parser.add_argument(
        "--url",
        default=os.getenv("GATEWAY_URL", "http://localhost:8000"),
        help="Payment gateway base URL",
    )
    parser.add_argument(
        "--population",
        type=int,
        default=int(os.getenv("INITIAL_POPULATION", "10000")),
        help="Initial normal users to add to the pool",
    )
    parser.add_argument(
        "--seconds-per-hour",
        type=float,
        default=float(os.getenv("REAL_SECONDS_PER_SIM_HOUR", "3")),
        help="Real seconds per simulated hour",
    )
    args = parser.parse_args()

    asyncio.run(
        run_simulation(
            gateway_url=args.url,
            initial_population=args.population,
            seconds_per_hour=args.seconds_per_hour,
        )
    )


if __name__ == "__main__":
    main()

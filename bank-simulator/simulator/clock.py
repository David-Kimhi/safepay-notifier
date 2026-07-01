import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DAY_START_HOUR = 9
DAY_END_HOUR = 20


def is_daytime(hour: int) -> bool:
    return DAY_START_HOUR <= hour <= DAY_END_HOUR


@dataclass
class Tick:
    sim_day: int
    hour: int
    is_day: bool


class SimClock:
    """Simulated clock: one hour of activity fits in real_seconds_per_hour."""

    def __init__(self, real_seconds_per_hour: float = 3.0) -> None:
        self.real_seconds_per_hour = real_seconds_per_hour
        self.sim_day = 1
        self.hour = DAY_START_HOUR

    def current(self) -> Tick:
        return Tick(sim_day=self.sim_day, hour=self.hour, is_day=is_daytime(self.hour))

    def advance(self) -> bool:
        """Advance to next hour. Returns True if a simulated day just ended."""
        period = "day" if is_daytime(self.hour) else "night"
        logger.info("Day %s, hour %02d (%s)", self.sim_day, self.hour, period)

        day_ended = self.hour == 23
        if day_ended:
            logger.info("--- End of simulated day %s ---", self.sim_day)
            self.hour = 0
            self.sim_day += 1
        else:
            self.hour += 1
        return day_ended

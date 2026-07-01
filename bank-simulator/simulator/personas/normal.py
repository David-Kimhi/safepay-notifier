import os
import random
from datetime import datetime, timezone

from simulator.clock import is_daytime
from simulator.population import User

# Currencies a typical user might pay in.
CURRENCIES = ["ILS", "USD"]


class NormalPersona:
    """Default persona: pays occasionally, more often during daytime hours."""
    kind = "normal"

    def __init__(
        self,
        p_day: float | None = None,
        p_night: float | None = None,
    ) -> None:
        # Chance per simulated hour to pay: ~1.5% by day, ~0.1% at night (ctor args override env).
        self.p_day = float(p_day if p_day is not None else os.getenv("NORMAL_P_DAY", "0.015"))
        self.p_night = float(p_night if p_night is not None else os.getenv("NORMAL_P_NIGHT", "0.001"))

    # Engine asks each hour: should this user attempt a payment right now?
    def activity_probability(self, hour: int) -> float:
        return self.p_day if is_daytime(hour) else self.p_night

    # Random realistic /pay payload: user account → their usual merchant (purchase).
    def build_payment(self, user: User) -> dict:
        return {
            "source_account_id": user.user_id,
            "destination_account_id": user.merchant_affinity,
            "amount": round(random.uniform(10, 500), 2),
            "currency": random.choice(CURRENCIES),
            "payment_type": "purchase",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

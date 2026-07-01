from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from simulator.population import User


class Persona(Protocol):
    kind: str

    def activity_probability(self, hour: int) -> float:
        """Chance this persona acts in a given simulated hour (0.0–1.0)."""
        ...

    def build_payment(self, user: "User") -> dict:
        """Build a /pay JSON body for this user."""
        ...

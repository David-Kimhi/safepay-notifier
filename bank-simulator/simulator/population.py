import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.personas.base import Persona


MERCHANTS = [f"merchant_{i:03d}" for i in range(20)]


@dataclass
class User:
    user_id: str
    persona_kind: str
    merchant_affinity: str = field(default_factory=lambda: random.choice(MERCHANTS))


class PopulationPool:
    """In-memory pool of simulated users, grouped by persona."""

    def __init__(self) -> None:
        self._users: list[User] = []
        self._personas: dict[str, "Persona"] = {}
        self._next_id = 0

    def register_persona(self, persona: "Persona") -> None:
        self._personas[persona.kind] = persona

    def add_normal_users(self, count: int = 10_000, persona: "Persona | None" = None) -> int:
        """Add count users with the normal persona. Returns new pool size."""
        kind = persona.kind if persona else "normal"
        if persona:
            self._personas[kind] = persona

        for _ in range(count):
            uid = f"user_id_{self._next_id}"
            self._next_id += 1
            self._users.append(User(user_id=uid, persona_kind=kind))

        return len(self._users)

    @property
    def size(self) -> int:
        return len(self._users)

    def sample_actors(self, hour: int) -> list[tuple[User, "Persona"]]:
        """Return users who act this hour, with their persona."""
        actors: list[tuple[User, "Persona"]] = []
        for user in self._users:
            persona = self._personas.get(user.persona_kind)
            if persona is None:
                continue
            if random.random() < persona.activity_probability(hour):
                actors.append((user, persona))
        return actors

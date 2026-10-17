# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""How a learner message arrived: its times and the device it was typed on.

The device is a hint the client sends (``DOCS-contract.md`` §4): on a phone
the tutor reads past typos, takes a few words as an answer and asks one short
question (prompt rule 13). Absent means desktop, so older clients and the
scripted runs keep today's prompt byte for byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from tutor.clock import reply_time

DESKTOP: Final = "desktop"
PHONE: Final = "phone"
DEVICES: Final = frozenset({DESKTOP, PHONE})
# The one engine-note line a phone turn gets (the rule itself is in the prompt).
PHONE_NOTE: Final = (
    "device: phone - the learner is typing on a phone this turn: rule 13 applies"
)


def device(value: object) -> str:
    """``value`` as a device name; ``None`` is desktop, anything else unknown raises."""
    if value is None:
        return DESKTOP
    if isinstance(value, str) and value in DEVICES:
        return value
    msg = f"device must be one of {sorted(DEVICES)}"
    raise ValueError(msg)


@dataclass(frozen=True)
class Delivery:
    """When the learner pressed Send / the relay received it, and on what device.

    ``sent_at`` is the first Send press (a retried send is timed from it);
    ``received`` (relay: RTDB server time) replaces the engine's own clock.
    """

    sent_at: float | None = None
    received: float | None = None
    device: str = DESKTOP

    def learner_at(self, now: float) -> float:
        """When the learner acted: ``received`` (else ``now``), or the Send press."""
        return reply_time(now if self.received is None else self.received, self.sent_at)


def note_lines(name: str) -> list[str]:
    """The engine-note lines for a turn typed on ``name`` (none on a desktop)."""
    return [PHONE_NOTE] if name == PHONE else []


def learner_message(text: str, name: object) -> dict[str, Any]:
    """The page message for a learner reply; only a phone one is marked."""
    message: dict[str, Any] = {"role": "learner", "text": text}
    if name == PHONE:
        message["device"] = PHONE
    return message

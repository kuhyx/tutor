# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Turn phases (thinking -> images -> checking_images) without engine hooks.

The engine makes its model sessions through an injectable factory; the relay
hands it one whose sessions report each ``ask`` to a :class:`PhaseSink`. A
text prompt is the tutor thinking; a content-block prompt is the image check;
between the two, a turn that asked for pictures or a diagram is fetching them.
Web-page turns run with no claim attached and report nowhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.session import TutorSession, isolated_options
from tutor.trace import traced

if TYPE_CHECKING:
    from collections.abc import Callable

    from claude_agent_sdk import ClaudeAgentOptions

    from tutor.models import TutorTurn
    from tutor.relay.claims import Claim
    from tutor.session import Prompt, Reply
    from tutor.trace import Observer, Trace


class PhaseSink:
    """Where phases go: the claim of the request being served, if any."""

    def __init__(self) -> None:
        """No request yet."""
        self.claim: Claim | None = None

    def __call__(self, phase: str) -> None:
        """Report ``phase`` to the current claim (no claim: dropped)."""
        if self.claim is not None:
            self.claim.set_phase(phase)

    def trace(self, trace: Trace) -> None:
        """The tutor turn's thinking / tool calls grew (no claim: dropped)."""
        if self.claim is not None:
            self.claim.set_trace(trace)


class PhasedSession(TutorSession):
    """A :class:`TutorSession` that reports its asks to a sink."""

    def __init__(self, options: ClaudeAgentOptions, sink: PhaseSink) -> None:
        """Wrap the options like a plain session; nothing spawns yet."""
        super().__init__(options)
        self._sink = sink

    async def ask(
        self, prompt: Prompt, on_trace: Observer | None = None
    ) -> tuple[TutorTurn, Reply]:
        """Report the phase, then ask as usual; the tutor turn's trace goes live.

        The image check's own thinking is not the turn's: it is not shown.
        """
        check = isinstance(prompt, list)
        self._sink("checking_images" if check else "thinking")
        if on_trace is None and not check:
            on_trace = self._sink.trace
        turn, reply = await super().ask(prompt, on_trace)
        if not check and (turn.images or turn.diagram is not None):
            self._sink("images")
        return turn, reply


def session_factory(sink: PhaseSink) -> Callable[[str], TutorSession]:
    """The engine's ``session_factory`` for a relay-enabled process."""
    return lambda prompt: PhasedSession(traced(isolated_options(prompt)), sink)

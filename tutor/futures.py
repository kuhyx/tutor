# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Settling a caller's future once (``session.TutorSession``'s waiting asks)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncio


def settle(fut: asyncio.Future[Any], err: BaseException | None) -> None:
    """Fail ``fut`` with ``err`` (cancel it when None), unless already done."""
    if fut.done():
        return
    if err is None:
        fut.cancel()
    else:
        fut.set_exception(err)

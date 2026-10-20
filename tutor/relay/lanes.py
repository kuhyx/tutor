# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Serving one request end to end (``DOCS-contract.md`` §4 steps 1-5).

done-map -> claim -> validate -> handler (lease kept, phases mirrored) ->
local commit (the engine's jsonl, then the done-map) -> projection ->
``result``. Two lanes, ``chat`` and ``build``, each serve one request at a
time, so a later rid never overtakes an earlier one in the same lane.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

from tutor.relay import hooks, live_trace
from tutor.relay.chat import CHAT_HANDLERS
from tutor.relay.claims import MAX_ATTEMPTS, Claim
from tutor.relay.context import RequestContext
from tutor.relay.errors import RequestError, classify, result_of
from tutor.relay.protocol import CHAT, validate
from tutor.relay.rtdb import SERVER_TIME, RtdbError

if TYPE_CHECKING:
    from tutor.relay.context import Wiring
    from tutor.relay.curriculum_sync import CurriculumSync
    from tutor.relay.protocol import Request

_logger = logging.getLogger(__name__)
_LOUD_CODES = frozenset({"worker_error", "model_error"})
Outcome = tuple[dict[str, Any], set[str]]  # result, sessions to re-publish


class Server:
    """Serves requests; ``current`` names the rid each lane is busy with."""

    def __init__(self, wiring: Wiring, curriculum: CurriculumSync) -> None:
        """Bind the worker's collaborators."""
        self.w, self.curriculum = wiring, curriculum
        self.current: dict[str, str | None] = {"chat": None, "build": None}
        # Sessions whose ``meta/busy`` may still show: a clear that failed, or
        # (seeded at startup) one a previous process left behind.
        self.stale_busy: set[str] = set()

    async def serve(self, rid: str, req: object, lane: str) -> dict[str, Any] | None:
        """Serve ``rid``; returns the result written (``None``: not ours to serve)."""
        row = self.w.done.get(rid)
        if row is not None:  # done before: answer again, never run again
            await self._put_result(rid, row["result"])
            return dict(row["result"])
        claim = Claim(self.w.rtdb, rid, self.w.worker, self.w.now)
        if not await claim.take():
            return None
        self.current[lane] = rid
        try:
            result = await self._run(claim, req)
        finally:  # a bug or a cancel must not leave Send disabled
            self.current[lane] = None
            if await claim.clear_busy():
                self.stale_busy.discard(claim.busy_session)
            else:
                self.stale_busy.add(claim.busy_session)
        await self._put_result(rid, result)
        return result

    async def sweep_busy(self) -> None:
        """Clear :attr:`stale_busy` while no request is in flight (failures wait)."""
        if any(self.current.values()):
            return
        for sid in sorted(self.stale_busy):
            try:
                await self.w.rtdb.patch(f"sessions/{sid}/meta", {"busy": None})
                await self.w.rtdb.delete(live_trace.path(sid))
            except RtdbError as err:
                _logger.warning("busy sweep on %s failed: %s", sid, err)
                return
            self.stale_busy.discard(sid)

    def _commit(self, rid: str, raw: object, result: dict[str, Any]) -> None:
        """The done-map row: after it, ``rid`` is never run again."""
        fields = raw if isinstance(raw, dict) else {}
        dev, kind = str(fields.get("dev") or ""), str(fields.get("kind") or "")
        self.w.done.add(rid, self.w.now(), dev, kind, result)

    async def _run(self, claim: Claim, raw: object) -> dict[str, Any]:
        try:
            request = self._valid(claim, raw)
        except RequestError as err:
            _logger.warning("request %s refused: %s", claim.rid, err.message)
            self._commit(claim.rid, raw, result_of(err))
            return result_of(err)
        session = request.body.get("session")
        if isinstance(session, str):
            text = request.body.get("text")
            claim.busy_session = session
            claim.busy_text = text if isinstance(text, str) else None
            every = live_trace.every_for(request.body)
            claim.progress = live_trace.TracePublisher(
                self.w.rtdb, session, claim.rid, every
            )
        keeper = asyncio.create_task(claim.keep())
        try:
            result, touched = await self._handle(claim, request)
            self._commit(claim.rid, raw, result)
            try:
                await self.w.publisher.after(touched)
            except RtdbError as err:  # the local commit stands; startup re-publishes
                _logger.warning("publish after %s failed: %s", claim.rid, err)
            await self.sync()  # a plan op or a taught card moved the curriculum
            return result
        finally:
            keeper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await keeper

    @staticmethod
    def _valid(claim: Claim, raw: object) -> Request:
        if claim.attempt > MAX_ATTEMPTS:
            msg = f"gave up after {MAX_ATTEMPTS} attempts"
            raise RequestError(msg, code="gave_up")
        return validate(claim.rid, raw)

    async def _handle(self, claim: Claim, request: Request) -> Outcome:
        w = self.w
        ctx = RequestContext(
            request, w.engine, w.rtdb, w.publisher, claim.set_phase, w.now
        )
        before = w.engine.session_id
        if request.lane == CHAT:
            w.sink.claim = claim
        try:
            # gather, not try/except: the curriculum's own error class joins
            # the expected ones at run time, and anything else still raises.
            outcomes = await asyncio.gather(self._call(ctx), return_exceptions=True)
        finally:
            w.sink.claim = None
        outcome = outcomes[0]
        if isinstance(outcome, BaseException):
            if not hooks.expected(outcome):
                raise outcome
            failed = classify(outcome)
            _logger.warning(
                "request %s (%s) failed: %s: %s",
                request.rid,
                request.kind,
                failed.code,
                failed.message,
                exc_info=outcome if failed.code in _LOUD_CODES else None,
            )
            result = result_of(failed)
        else:
            result = {"ok": True, "data": outcome}
        claim.set_phase("publishing")
        touched = {before, w.engine.session_id, *ctx.touched}
        if isinstance(sid := request.body.get("session"), str):
            touched.add(sid)
        return result, touched

    async def _call(self, ctx: RequestContext) -> dict[str, Any]:
        """Sync the curriculum, then run the handler (build: under its lock)."""
        await self.sync()
        handler = CHAT_HANDLERS.get(ctx.request.kind)
        if handler is not None:
            return await handler(ctx)
        async with self.curriculum.lock:
            return await hooks.build(ctx)

    async def sync(self) -> None:
        """The curriculum sync (it logs its own failures; the request goes on)."""
        await self.curriculum.sync()

    async def _put_result(self, rid: str, result: dict[str, Any]) -> None:
        await self.w.rtdb.put(f"requests/{rid}/result", {**result, "at": SERVER_TIME})

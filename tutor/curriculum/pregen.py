# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``module_pregenerate``: draft a locked module's cards before it unlocks.

Opt-in only (a request names the modules, or ``"all"`` for every locked one
not drafted yet): each gets ``status:"generating"`` + ``pregenerated:true``,
so :func:`tutor.curriculum.advance.pending` hands it to the worker's build
lane like any other module (one at a time; a crash leaves it ``generating``
and it is listed again). ``cardgen.generate`` then puts it back to
``locked`` with its cards, editable with ``card_edit`` but never taught,
until its ``requires`` are mastered: ``rules.advance_statuses`` opens it
straight to ``ready``, without drafting again. Refusals write nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tutor.curriculum.errors import PLAN_CONFLICT, RequestError
from tutor.curriculum.ids import valid_id
from tutor.curriculum.records import bad, id_list
from tutor.curriculum.subject_store import LOCK, Change

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.records import Module, Plan


def _chosen(plan: Plan, wanted: object) -> list[Module]:
    """The modules to draft ahead; anything not eligible refuses the lot."""
    if wanted == "all":
        return [m for m in plan.modules if m.status == "locked" and not m.pregenerated]
    ids = id_list(wanted, "modules")
    if not ids:
        msg = 'modules must name at least one module, or be "all"'
        raise bad(msg)
    unknown = [i for i in ids if plan.module(i) is None]
    if unknown:
        msg = f"unknown modules: {unknown}"
        raise bad(msg)
    chosen = [m for m in plan.modules if m.id in ids]
    done = [m.id for m in chosen if m.pregenerated and m.status == "locked"]
    if done:
        msg = f"already pre-generated (edit their cards instead): {done}"
        raise bad(msg)
    open_ = [f"{m.id} is {m.status}" for m in chosen if m.status != "locked"]
    if open_:
        msg = f"only locked modules can be pre-generated: {'; '.join(open_)}"
        raise bad(msg)
    return chosen


def module_pregenerate(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Queue the named locked modules (or ``"all"``); ``{"queued": [ids]}``."""
    subject = body.get("subject")
    if not valid_id(subject):
        msg = "subject must be a subject id"
        raise bad(msg)
    with LOCK:  # read-modify-write against the fold and the chat lane
        meta = ctx.subjects.need_meta(str(subject))
        plan = ctx.subjects.plan(str(subject))
        if plan is None or plan.status != "approved":
            msg = f"{subject}'s plan is not approved; approve it first"
            raise RequestError(PLAN_CONFLICT, msg)
        chosen = _chosen(plan, body.get("modules"))
        for module in chosen:
            module.status, module.pregenerated, module.error = "generating", True, None
        if chosen:
            ctx.subjects.commit(str(subject), meta, Change(plan=plan))
    return {"queued": [m.id for m in chosen]}

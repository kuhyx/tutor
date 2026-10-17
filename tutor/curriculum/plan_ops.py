# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The plan requests (build lane): new subject, revise, edit, approve, finish.

Each handler takes the request ``body`` and a :class:`Context`, writes the
subject files and returns the result ``data`` (``DOCS-contract.md`` §4).
Every plan op carries ``plan_rev``; a stale one is ``plan_conflict``. A plan
changes only while it is a ``draft``, and modules that have cards never
change. Card generation is not run here: approving marks modules
``generating`` and :func:`tutor.curriculum.advance.pending` hands them out.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Final
import unicodedata

from tutor.curriculum import planner, profiles, rules
from tutor.curriculum.errors import BAD_REQUEST, PLAN_CONFLICT, RequestError
from tutor.curriculum.ids import slug, valid_id
from tutor.curriculum.records import (
    MAX_GOAL,
    MAX_NOTES,
    Meta,
    Module,
    Plan,
    bad,
    check_modules,
    text,
)
from tutor.curriculum.subject_store import Change

if TYPE_CHECKING:
    from tutor.curriculum.context import Context

_FILLER: Final = re.compile(
    r"^\s*(?:i(?:\s+want|\s+would\s+like|['\u2019]d\s+like)\s+to\s+"
    r"(?:learn|know|understand)"
    r"|teach\s+me|learn)(?:\s+about)?\s+",
    re.IGNORECASE,
)
# Polish opener: chcę (się) + nauczyć / wiedzieć / zrozumieć / rozumieć /
# poznać (+ o), or chciałbym / chciałabym; diacritics optional.
_VERB_PL: Final = r"(?:nauczy[cć]|wiedzie[cć]|zrozumie[cć]|rozumie[cć]|pozna[cć])"
_FILLER_PL: Final = re.compile(
    rf"^\s*(?:chc[eę]|chcia[lł]a?bym)\s+(?:si[eę]\s+)?{_VERB_PL}"
    r"(?:\s+si[eę])?(?:\s+o)?\s+",
    re.IGNORECASE,
)
_DEEPER: Final = (
    "Go deeper: the learner has mastered every module above. Plan the next, "
    "more advanced round on the same goal."
)


def subject_id(goal: str, taken: set[str]) -> str:
    """A subject id from the learner's words ("how-a-car-works")."""
    words = unicodedata.normalize("NFC", goal)  # so "e" + U+0328 matches "ę"
    words = _FILLER_PL.sub("", _FILLER.sub("", words))
    return slug(words, taken, fallback="subject")


def subject_new(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Create a subject and draft its plan (``meta`` first, ``drafting``)."""
    goal = text(body, "text", MAX_GOAL)
    store = ctx.subjects
    live = {s for s in store.subjects() if store.need_meta(s).status != "failed"}
    subject = subject_id(goal, live)
    meta = Meta(title=goal[:60], goal=goal, status="drafting", created=ctx.clock())
    old = store.meta(subject)
    meta.rev = old.rev if old else 0
    store.commit(subject, meta)
    try:
        draft = planner.draft(ctx, goal, fixed=[])
    except RequestError as err:
        meta.status, meta.error = "failed", err.message
        store.commit(subject, meta)
        raise
    meta.title, meta.status, meta.error = draft.title or meta.title, "draft", None
    plan = Plan(rev=1, status="draft", notes=draft.notes, modules=draft.modules)
    profile = profiles.generated(subject, draft.profile).to_json()
    change = Change(plan=plan, cards={}, concepts=[], profile=profile)
    store.commit(subject, meta, change)
    return {"subject": subject}


def _load(body: dict[str, Any], ctx: Context) -> tuple[str, Meta, Plan]:
    subject = body.get("subject")
    if not valid_id(subject):
        msg = "subject must be a subject id"
        raise bad(msg)
    meta = ctx.subjects.need_meta(str(subject))
    plan = ctx.subjects.plan(str(subject))
    if plan is None:
        msg = f"{subject} has no plan yet"
        raise RequestError(PLAN_CONFLICT, msg)
    return str(subject), meta, plan


def _draft_plan(body: dict[str, Any], ctx: Context) -> tuple[str, Meta, Plan]:
    """The subject's plan, which must be the ``draft`` at ``plan_rev``."""
    subject, meta, plan = _load(body, ctx)
    if body.get("plan_rev") != plan.rev:
        msg = f"the plan changed (now rev {plan.rev}); reload it"
        raise RequestError(PLAN_CONFLICT, msg)
    if plan.status != "draft" or meta.status != "draft":
        msg = "the plan is approved; only a draft can change"
        raise RequestError(PLAN_CONFLICT, msg)
    return subject, meta, plan


def _fixed(plan: Plan) -> list[Module]:
    """Modules that never change: they have cards or left ``locked``."""
    return [m for m in plan.modules if m.cards or m.status != "locked"]


def _next(plan: Plan, modules: list[Module], comment: str, at: int) -> Plan:
    history = [*plan.history, {"rev": plan.rev, "comment": comment, "at": at}]
    return Plan(plan.rev + 1, "draft", plan.notes, modules, history)


def plan_revise(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Redraft the plan per kuhy's comment (modules with cards stay)."""
    subject, meta, plan = _draft_plan(body, ctx)
    comment = text(body, "comment", MAX_NOTES)
    draft = planner.draft(ctx, meta.goal, fixed=_fixed(plan), comment=comment)
    new = _next(plan, draft.modules, comment, ctx.clock())
    new.notes = draft.notes or plan.notes
    ctx.subjects.commit(subject, meta, Change(plan=new))
    return {"plan_rev": new.rev}


def plan_edit(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Replace the module list by hand (validated; fixed modules restored)."""
    subject, meta, plan = _draft_plan(body, ctx)
    raw = body.get("modules")
    if not isinstance(raw, list):
        msg = "modules must be a list"
        raise bad(msg)
    fixed = {m.id: m for m in _fixed(plan)}
    edited = [Module.from_json(m, client=True) for m in raw]
    missing = [i for i in fixed if i not in {m.id for m in edited}]
    if missing:
        msg = f"modules with cards cannot be removed: {missing}"
        raise RequestError(BAD_REQUEST, msg)
    depth = max((m.depth for m in fixed.values()), default=0) + 1
    for module in edited:
        module.depth = depth
    modules = [fixed.get(m.id, m) for m in edited]
    check_modules(modules)
    new = _next(plan, modules, "edited by hand", ctx.clock())
    ctx.subjects.commit(subject, meta, Change(plan=new))
    return {"plan_rev": new.rev}


def plan_approve(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Approve the draft (or retry failed modules of an approved plan)."""
    subject, meta, plan = _load(body, ctx)
    if body.get("plan_rev") != plan.rev:
        msg = f"the plan changed (now rev {plan.rev}); reload it"
        raise RequestError(PLAN_CONFLICT, msg)
    if plan.status == "draft":
        plan.status, meta.status = "approved", "active"
    for module in plan.modules:
        if module.status == "failed":
            module.status, module.error = "generating", None
    view = rules.View(subject, plan, ctx.subjects.cards(subject))
    rules.advance_statuses(view, ctx.fold())
    ctx.subjects.commit(subject, meta, Change(plan=plan))
    return {}


def subject_finish(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """After ``completed``: ``go_deeper`` (a new draft) or ``review_only``."""
    subject, meta, plan = _load(body, ctx)
    choice = body.get("choice")
    if choice not in {"go_deeper", "review_only"}:
        msg = "choice must be go_deeper or review_only"
        raise bad(msg)
    if meta.status != "completed":
        msg = f"{subject} is not completed yet"
        raise bad(msg)
    if choice == "review_only":
        meta.status = "review_only"
        ctx.subjects.commit(subject, meta)
        return {}
    draft = planner.draft(ctx, meta.goal, fixed=plan.modules, comment=_DEEPER)
    new = _next(plan, draft.modules, "go deeper", ctx.clock())
    new.notes = draft.notes or plan.notes
    meta.status = "draft"
    ctx.subjects.commit(subject, meta, Change(plan=new))
    return {"plan_rev": new.rev}

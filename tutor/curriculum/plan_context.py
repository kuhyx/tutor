# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The plan around one module, for every model call that must stay inside it.

A card generated for module 1 of a "how a car works" plan was about pistons
and the crankshaft, which module 2 teaches: the drafting model only saw the
other modules' titles, and the gate only this module's summary. Now the
titles call, the source pick, the drafting and the per-card gate all see
every other module's title and summary, split by plan order into earlier
modules (already taught: a card on them is a duplicate) and later ones (they
teach their own topic in depth: leave it to them). The gate names the module
each card fits best and code keeps a card only when that is this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from tutor.curriculum.records import Meta, Module, Plan

SCOPE_RULE: Final = """\
Every card belongs to the ONE module of the plan whose description fits it \
best. A module may name a part or system that another module covers only \
at the level of what it is and what it does for the whole; how it works \
inside (its parts, mechanisms, steps, types, numbers) belongs to the module \
that covers it. Content of an earlier module is a duplicate here."""


@dataclass(frozen=True)
class Scope:
    """What a relevance call is about: the subject, the module, its plan."""

    meta: Meta
    module: Module
    plan: Plan | None

    def about(self) -> str:
        """The learner's goal, the module and the plan around it, as text."""
        meta, module = self.meta, self.module
        return (
            f"Learner's goal: {meta.goal}\nSubject: {meta.title}\n"
            f"Module ({module.id}): {module.title}\n"
            f"What it covers: {module.summary}\n{around(self.plan, module)}"
        )


def neighbours(plan: Plan | None, module: Module) -> tuple[list[Module], list[Module]]:
    """The plan's other modules: (earlier, later) in teaching order."""
    others = plan.modules if plan else []
    ids = [m.id for m in others]
    at = ids.index(module.id) if module.id in ids else len(ids)
    return others[:at], others[at + 1 :]


def _listed(modules: list[Module]) -> str:
    return "\n".join(f'- {m.id} "{m.title}": {m.summary}' for m in modules)


def around(plan: Plan | None, module: Module) -> str:
    """The other modules as prompt text; ``(none)`` lines for an empty side."""
    earlier, later = neighbours(plan, module)
    return (
        "Earlier modules (already taught; a card on their content is a "
        f"duplicate):\n{_listed(earlier) or '(none)'}\n"
        "Later modules (each teaches its own topic in depth; leave it to "
        f"them):\n{_listed(later) or '(none)'}"
    )


def module_ids(plan: Plan | None, module: Module) -> list[str]:
    """Every module id a card can belong to, this module's first."""
    earlier, later = neighbours(plan, module)
    return [module.id, *(m.id for m in earlier + later)]


def misplaced(plan: Plan | None, module: Module, best: str) -> str:
    """Why a card whose best module is ``best`` is refused; "" unless another."""
    earlier, later = neighbours(plan, module)
    if best in {m.id for m in earlier}:
        return f"duplicates earlier module {best}"
    if best in {m.id for m in later}:
        return f"belongs to later module {best}"
    return ""

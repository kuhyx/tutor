# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The checks on a plan's module list as a whole (ids, order, count)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.curriculum.records import MAX_MODULES, MIN_MODULES, bad

if TYPE_CHECKING:
    from tutor.curriculum.records import Module


def check_modules(modules: list[Module]) -> None:
    """Unique ids, ``requires`` only on earlier modules, 3-12 per draft.

    The count is of the newest draft (the deepest ``depth``): go-deeper
    rounds append modules to a plan that already has some. Modules that
    hold cards never count toward the upper bound: a redraft cuts a big
    module into several (``redraft.swap``), which may pass twelve.
    """
    newest = max((m.depth for m in modules), default=1)
    count = sum(m.depth == newest for m in modules)
    empty = sum(m.depth == newest and not m.cards for m in modules)
    if count < MIN_MODULES or empty > MAX_MODULES:
        msg = f"a plan draft has {MIN_MODULES}-{MAX_MODULES} modules, not {count}"
        raise bad(msg)
    seen: set[str] = set()
    for module in modules:
        if module.id in seen:
            msg = f"duplicate module id {module.id!r}"
            raise bad(msg)
        late = [r for r in module.requires if r not in seen]
        if late:
            msg = f"{module.id} requires {late}, which are not earlier modules"
            raise bad(msg)
        seen.add(module.id)

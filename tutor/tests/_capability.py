# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Skip a test module whose host capability is absent, unless CI demands it.

The sandbox tests (pasta, bwrap) skip on a host without them. On CI that skip
hid a real failure for weeks: Ubuntu's AppArmor profile for pasta refuses to
exec a script outside ``/usr/bin``, the probe failed, and every sandbox test
"skipped" as "no usable bwrap". CI sets ``TUTOR_TESTS_NEED_SANDBOX`` (its
workflow sets the host up), so an absent capability there is a collection
error naming the probe, never a skip.
"""

from __future__ import annotations

import os

import pytest

NEED = "TUTOR_TESTS_NEED_SANDBOX"


def skip_unless(*, works: bool, reason: str) -> pytest.MarkDecorator:
    """``skipif(not works)``, or raise when the host is required to have it."""
    if not works and os.environ.get(NEED):
        msg = f"{reason}, and {NEED} says this host must have it"
        raise RuntimeError(msg)
    return pytest.mark.skipif(not works, reason=reason)

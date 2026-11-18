# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The fence line through the SDK's own subprocess, not a fake client."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from claude_agent_sdk import ClaudeAgentOptions, ProcessError
import pytest

from tutor import model_fault
from tutor.session import TutorSession
from tutor.tests.test_model_fault import FENCE, entries

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.tests.conftest import FaultRig


def test_a_real_cli_process_that_prints_the_fence_line(
    fault: FaultRig, tmp_path: Path
) -> None:
    """End to end through the SDK's own subprocess: stderr line, exit 1."""
    cli = tmp_path / "fake_cli.sh"
    cli.write_text(f"#!/bin/sh\necho '{FENCE}' >&2\nexit 1\n")
    cli.chmod(0o755)

    async def go() -> None:
        opts = ClaudeAgentOptions(cli_path=cli, cwd=tmp_path)
        sess = TutorSession(opts)
        with pytest.raises(ProcessError):
            await asyncio.wait_for(sess.ask_raw("hi"), 20)
        await sess.close()

    asyncio.run(go())
    kinds = [e["kind"] for e in entries(fault)]
    assert model_fault.SANDBOX_KIND in kinds
    assert len(fault.notices) == 1

# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor conversation's tools: every Claude Code tool, inside bubblewrap.

The tutor may research beyond its card (web search and fetch, running code,
subagents). Its CLI runs through ``scripts/tutor_model_sandbox.sh`` (the SDK's
``cli_path``), which sees a scratch HOME and network, never the data dir, the
ledger key, the repo or ``~/.claude``; so permissions are bypassed (nobody is
there to approve). Settings, hooks, skills and MCP stay off as in
:func:`session.isolated_options`, which every other model call keeps.

Two SDK hook callbacks (they run in this process, not the sandbox, and emit
no hook events, so ``tutor.isolation`` still counts 0):

- UserPromptSubmit (each turn): refresh the login copy (``model_login``) and
  start the turn's research clock.
- PreToolUse: :class:`ResearchBudget` denies every tool call once
  :data:`RESEARCH_SECONDS` of the turn have passed, so the tutor answers with
  what it has. Bash calls are capped at 60 s by env; both keep a turn well
  under ``session._TURN_TIMEOUT``.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import time
from typing import TYPE_CHECKING, Final

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from tutor.model_login import Login, real_cli, sync_login
from tutor.models import TURN_SCHEMA
from tutor.session import MODEL
from tutor.store import data_dir

if TYPE_CHECKING:
    from collections.abc import Callable

    from claude_agent_sdk import HookContext, HookInput, HookJSONOutput

RESEARCH_SECONDS: Final = 90
BASH_TIMEOUT_MS: Final = "60000"
WRAPPER: Final = (
    Path(__file__).resolve().parents[1] / "scripts" / "tutor_model_sandbox.sh"
)
# The tool that carries the structured turn: never denied, or a late turn fails.
_ANSWER_TOOL: Final = "StructuredOutput"
_DENY: Final = (
    "Research time is up: {seconds} seconds of this turn have passed. No more "
    "tool calls this turn; answer now with what you have, and say what you "
    "could not check."
)


def sandbox_root() -> Path:
    """The model's scratch root: ``$TUTOR_MODEL_SANDBOX``, else by data dir.

    A sandboxed run (``TUTOR_DATA``: the deploy smoke test, the agent E2E,
    tests) keeps it inside its data dir copy; the live server uses
    ``~/.cache/tutor/sandbox``, never the live data dir.
    """
    if override := os.environ.get("TUTOR_MODEL_SANDBOX"):
        return Path(override)
    if os.environ.get("TUTOR_DATA"):
        return data_dir() / "model-sandbox"
    return Path.home() / ".cache" / "tutor" / "sandbox"


class ResearchBudget:
    """The turn hooks: login refresh at the prompt, then a tool-time budget."""

    def __init__(
        self,
        seconds: float = RESEARCH_SECONDS,
        *,
        login: Login | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        """No turn yet: nothing is denied until :meth:`start`."""
        self.seconds = seconds
        self._login = login
        self._now = now
        self._started: float | None = None

    def start(self) -> None:
        """A turn begins now."""
        self._started = self._now()

    async def user_prompt_submit(
        self, data: HookInput, tool_use_id: str | None, context: HookContext
    ) -> HookJSONOutput:
        """The UserPromptSubmit hook: fresh login copy, then the clock starts."""
        del data, tool_use_id, context
        if self._login is not None:
            await asyncio.to_thread(self._login.ensure)
        self.start()
        return {}

    async def pre_tool_use(
        self, data: HookInput, tool_use_id: str | None, context: HookContext
    ) -> HookJSONOutput:
        """The PreToolUse hook: {} (no say) inside the budget, else deny."""
        del tool_use_id, context
        started = self._started
        if (
            started is None
            or data.get("tool_name") == _ANSWER_TOOL
            or self._now() - started < self.seconds
        ):
            return {}
        reason = _DENY.format(seconds=f"{self.seconds:g}")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }


def research_options(
    system_prompt: str,
    *,
    structured: bool = True,
    budget: ResearchBudget | None = None,
) -> ClaudeAgentOptions:
    """Every tool, permissions bypassed, inside the sandbox, on a budget."""
    root = sandbox_root()
    cwd = root / "home" / "work"
    cwd.mkdir(parents=True, exist_ok=True)
    sync_login(root / "home")  # the CLI may read it before the first prompt
    budget = budget or ResearchBudget(login=Login(root / "home"))
    return ClaudeAgentOptions(
        model=MODEL,
        system_prompt=system_prompt,
        tools={"type": "preset", "preset": "claude_code"},
        allowed_tools=[],
        disallowed_tools=[],
        permission_mode="bypassPermissions",
        setting_sources=[],
        strict_mcp_config=True,
        mcp_servers={},
        cli_path=WRAPPER,
        cwd=cwd,
        hooks={
            "UserPromptSubmit": [HookMatcher(hooks=[budget.user_prompt_submit])],
            "PreToolUse": [HookMatcher(hooks=[budget.pre_tool_use])],
        },
        include_hook_events=True,
        output_format=(
            {"type": "json_schema", "schema": TURN_SCHEMA} if structured else None
        ),
        effort="medium",
        env={
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "DISABLE_TELEMETRY": "1",
            "DISABLE_AUTOUPDATER": "1",
            "BASH_DEFAULT_TIMEOUT_MS": BASH_TIMEOUT_MS,
            "BASH_MAX_TIMEOUT_MS": BASH_TIMEOUT_MS,
            "TUTOR_MODEL_SANDBOX": str(root),
            "TUTOR_MODEL_CLI": str(real_cli()),
        },
        extra_args={"disable-slash-commands": None, "no-session-persistence": None},
    )

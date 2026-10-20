# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor's research tools: sandboxed options, the turn hooks, the 90 s budget."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from tutor import research, session
from tutor.engine import Engine
from tutor.relay import phases
from tutor.tests.test_model_login import copied, host_login

if TYPE_CHECKING:
    from claude_agent_sdk import HookContext, HookInput
    import pytest

CTX: HookContext = {"signal": None}


class Clock:
    """A settable monotonic clock."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def decide(budget: research.ResearchBudget, tool: str) -> dict[str, Any]:
    data = cast("HookInput", {"tool_name": tool})
    return dict(asyncio.run(budget.pre_tool_use(data, "id", CTX)))


def denied(budget: research.ResearchBudget, tool: str) -> bool:
    out = decide(budget, tool).get("hookSpecificOutput", {})
    return bool(out.get("permissionDecision") == "deny")


# --- where the sandbox lives ---------------------------------------------------


def test_sandbox_root_follows_tutor_data(tutor_sandbox: Path) -> None:
    assert research.sandbox_root() == tutor_sandbox / "data" / "model-sandbox"


def test_sandbox_root_defaults_to_the_cache(
    tutor_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TUTOR_DATA")
    assert research.sandbox_root() == tutor_sandbox / "home/.cache/tutor/sandbox"


def test_sandbox_root_override(
    tutor_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUTOR_MODEL_SANDBOX", str(tutor_sandbox / "box"))
    assert research.sandbox_root() == tutor_sandbox / "box"


# --- the options -------------------------------------------------------------


def test_research_options_run_every_tool_through_the_wrapper(
    tutor_sandbox: Path,
) -> None:
    host_login(tutor_sandbox / "home")
    opts = research.research_options("You teach.")
    wrapper = Path(str(opts.cli_path))
    assert wrapper == research.WRAPPER
    assert (wrapper.parent.name, wrapper.name) == ("scripts", "tutor_model_sandbox.sh")
    assert os.access(wrapper, os.X_OK)
    assert opts.permission_mode == "bypassPermissions"
    assert opts.tools == {"type": "preset", "preset": "claude_code"}
    assert opts.disallowed_tools == list(research.BLOCKED_TOOLS)
    # Still isolated from kuhy's CLAUDE.md, rules, hooks, skills and MCP.
    assert opts.setting_sources == []
    assert opts.strict_mcp_config is True
    assert opts.mcp_servers == {}
    root = research.sandbox_root()
    assert opts.env["TUTOR_MODEL_SANDBOX"] == str(root)
    assert Path(opts.env["TUTOR_MODEL_CLI"]).name.startswith("claude")
    assert opts.env["BASH_MAX_TIMEOUT_MS"] == "30000"
    assert opts.cwd is not None
    assert Path(opts.cwd) == root / "home" / "work"
    assert Path(opts.cwd).is_dir()
    assert opts.output_format is not None
    assert opts.system_prompt == "You teach."
    assert opts.hooks is not None
    assert set(opts.hooks) == {"UserPromptSubmit", "PreToolUse"}
    # The login copy is there before the CLI starts.
    assert copied(root / "home")["claudeAiOauth"]["accessToken"] == "access-1"


def test_free_text_research_options(tutor_sandbox: Path) -> None:
    assert research.research_options("x", structured=False).output_format is None


def test_research_budget_is_bounded_by_the_turn_timeout() -> None:
    assert research.RESEARCH_SECONDS == 90
    # Last tool call at the cap, a full Bash timeout, then the answer: well
    # inside the turn timeout and the app's 3 minute stall.
    bash = int(research.BASH_TIMEOUT_MS) / 1000
    assert research.RESEARCH_SECONDS + bash <= 120 < session._TURN_TIMEOUT


# --- the turn hooks ----------------------------------------------------------


def test_tools_are_allowed_until_the_budget_runs_out() -> None:
    clock = Clock()
    budget = research.ResearchBudget(90, now=clock)
    assert decide(budget, "WebSearch") == {}  # no turn started yet
    budget.start()
    clock.t += 89.9
    assert decide(budget, "WebSearch") == {}
    clock.t += 0.1
    out = decide(budget, "Bash")["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "deny"
    assert "90 seconds" in out["permissionDecisionReason"]
    assert "answer now" in out["permissionDecisionReason"]


def test_each_prompt_restarts_the_budget() -> None:
    clock = Clock()
    budget = research.ResearchBudget(90, now=clock)
    prompt = cast("HookInput", {"prompt": "hi"})
    assert asyncio.run(budget.user_prompt_submit(prompt, None, CTX)) == {}
    clock.t += 200
    assert denied(budget, "WebFetch")
    asyncio.run(budget.user_prompt_submit(prompt, None, CTX))
    assert not denied(budget, "WebFetch")


def test_the_structured_answer_is_never_denied() -> None:
    clock = Clock()
    budget = research.ResearchBudget(90, now=clock)
    budget.start()
    clock.t += 500
    assert decide(budget, "StructuredOutput") == {}
    assert denied(budget, "Task")


# 2026-10-20 (kuhy): tools that act through the claude.ai account (cloud
# routines, crons, other sessions, pushes to his phone) stay out of the box.
def test_account_wide_tools_are_blocked() -> None:
    assert set(research.BLOCKED_TOOLS) >= {
        "RemoteTrigger",
        "CronCreate",
        "CronDelete",
        "CronList",
        "ScheduleWakeup",
        "SendMessage",
        "Workflow",
        "PushNotification",
        "ListAgents",
        "DesignSync",
    }
    # The research tools stay.
    for kept in ("WebSearch", "WebFetch", "Bash", "Task", "Read", "Write"):
        assert kept not in research.BLOCKED_TOOLS


def test_remote_subagents_are_denied_at_any_time() -> None:
    clock = Clock()
    budget = research.ResearchBudget(90, now=clock)
    budget.start()
    for tool in ("Task", "Agent"):
        remote = {"tool_name": tool, "tool_input": {"isolation": "remote"}}
        out: dict[str, Any] = dict(
            asyncio.run(budget.pre_tool_use(cast("HookInput", remote), "i", CTX))
        )
        decision = out["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny"
        assert "this machine" in decision["permissionDecisionReason"]
        local = {"tool_name": tool, "tool_input": {"isolation": "worktree"}}
        assert (
            asyncio.run(budget.pre_tool_use(cast("HookInput", local), "i", CTX)) == {}
        )


def test_each_prompt_refreshes_the_login_copy_first(tutor_sandbox: Path) -> None:
    opts = research.research_options("p")  # no host login yet
    box = research.sandbox_root() / "home"
    assert not (box / ".claude/.credentials.json").exists()
    host_login(tutor_sandbox / "home")
    hooks = opts.hooks or {}
    on_prompt = hooks["UserPromptSubmit"][0].hooks[0]
    asyncio.run(on_prompt(cast("HookInput", {"prompt": "hi"}), None, CTX))
    assert copied(box)["claudeAiOauth"]["accessToken"] == "access-1"


def test_engine_and_relay_sessions_get_the_tools(tutor_sandbox: Path) -> None:
    engine_session = Engine()._factory("prompt")
    relay_session = phases.session_factory(phases.PhaseSink())("prompt")
    for made in (engine_session, relay_session):
        assert made._options.permission_mode == "bypassPermissions"
        assert made._options.cli_path == research.WRAPPER
    assert isinstance(relay_session, phases.PhasedSession)

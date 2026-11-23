# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Todo tasks the post-mortem files: an outbox, flushed to the todo MCP server.

A task is queued as ``postmortems/tasks/<name>.json`` (a name is queued once,
ever: ``<name>.filed.json`` is what a filed one becomes), then each tick
files the pending ones with ``add_task`` over the todo server's MCP HTTP
endpoint (``TUTOR_TODO_URL``, default ``127.0.0.1:8735/mcp``). The service
has no shell environment, so its bearer token lives in its own file
(``TUTOR_TODO_TOKEN_FILE``, default ``~/.config/tutor/todo_token``, minted by
``install.sh``). A failure is logged and retried on the next tick: a task is
never lost and never filed twice. Tests and the E2E sandbox point the URL at
a fake; nothing here may reach kuhy's real todo app from a test.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
import urllib.error
import urllib.request

from tutor.postmortem import files

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = logging.getLogger(__name__)
REPO: Final = "kuhyx/tutor"
URL_ENV: Final = "TUTOR_TODO_URL"
TOKEN_FILE_ENV: Final = "TUTOR_TODO_" + "TOKEN_FILE"  # an env name, not a secret
DEFAULT_TOKEN: Final = Path.home() / ".config/tutor/todo_token"
DEFAULT_URL: Final = "http://127.0.0.1:8735/mcp"
TIMEOUT_S: Final = 10.0
_PROTOCOL: Final = "2025-03-26"
type Post = Callable[[str, dict[str, str], dict[str, Any]], tuple[dict[str, str], str]]


class TodoError(Exception):
    """The task could not be filed (server down, token refused, tool error)."""


def _filed(path: Path) -> Path:
    return path.with_name(path.stem + ".filed.json")


def queue(name: str, title: str, body: str, priority: str = "high") -> bool:
    """Queue a task once; ``False`` when ``name`` was queued before."""
    path = files.tasks_dir() / f"{files.safe(name)}.json"
    if path.exists() or _filed(path).exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    task = {"title": title, "body": body, "priority": priority, "repo": REPO}
    path.write_text(json.dumps(task, indent=1), encoding="utf-8")
    return True


def pending() -> list[Path]:
    """The queued tasks not filed yet."""
    folder = files.tasks_dir()
    found = sorted(folder.glob("*.json")) if folder.is_dir() else []
    return [p for p in found if not p.name.endswith(".filed.json")]


def _token() -> str:
    path = os.environ.get(TOKEN_FILE_ENV) or str(DEFAULT_TOKEN)
    try:
        found = Path(path).read_text(encoding="utf-8").strip()
    except OSError as err:
        msg = f"no todo token: {err}"
        raise TodoError(msg) from err
    if not found:
        msg = f"empty todo token {path}"
        raise TodoError(msg)
    return found


def http_post(
    url: str, headers: dict[str, str], payload: dict[str, Any]
) -> tuple[dict[str, str], str]:
    """POST ``payload``; (response headers, body text)."""
    data = json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as reply:
            return dict(reply.headers), reply.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as err:
        msg = f"cannot reach {url}: {err}"
        raise TodoError(msg) from err


def _message(body: str) -> dict[str, Any]:
    """The JSON-RPC message of a plain or event-stream reply ({} when none)."""
    rows = [r.removeprefix("data:").strip() for r in body.splitlines()]
    for raw in [r for r in [body.strip(), *rows] if r.startswith("{")]:
        try:
            found = json.loads(raw)
        except ValueError as err:
            _logger.warning("todo MCP: a reply line is not JSON: %s", err)
            continue
        return dict(found)  # a "{" line that parses is an object
    return {}


def file_task(task: dict[str, Any], post: Post = http_post) -> str:
    """File ``task`` with ``add_task``; returns the tool's text."""
    url = os.environ.get(URL_ENV) or DEFAULT_URL
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    hello = {"protocolVersion": _PROTOCOL, "capabilities": {}}
    hello["clientInfo"] = {"name": "tutor-postmortem", "version": "1"}
    got, _ = post(
        url,
        headers,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": hello},
    )
    session = {k.lower(): v for k, v in got.items()}.get("mcp-session-id")
    if session:
        headers["Mcp-Session-Id"] = session
    post(url, headers, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    args = {k: str(task[k]) for k in ("repo", "title", "body", "priority")}
    call = {"name": "add_task", "arguments": args}
    _, body = post(
        url,
        headers,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": call},
    )
    result = _message(body).get("result")
    if not isinstance(result, dict) or result.get("isError"):
        msg = f"add_task failed: {body[:200]!r}"
        raise TodoError(msg)
    parts = result.get("content") or []
    return "\n".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))


def flush(post: Post = http_post) -> int:
    """File every pending task; how many were filed. A failure waits for next time."""
    done = 0
    for path in pending():
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
            text = file_task(task, post)
        except (TodoError, OSError, ValueError, KeyError) as err:
            _logger.warning("post-mortem task %s not filed: %s", path.name, err)
            continue
        path.write_text(json.dumps({**task, "filed": text}, indent=1), encoding="utf-8")
        path.replace(_filed(path))
        done += 1
    return done

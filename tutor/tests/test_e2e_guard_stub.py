# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""scripts/e2e_guard_stub.py: the sandbox's canned ``/api/theory``, loopback only."""

from __future__ import annotations

import http.client
import importlib.util
import json
from pathlib import Path
import threading
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "e2e_guard_stub.py"


def _module() -> Any:
    spec = importlib.util.spec_from_file_location("e2e_guard_stub", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_answer_fills_a_missing_day_and_keeps_a_given_one() -> None:
    stub = _module()
    got = json.loads(stub.answer('{"checked": true, "needed": 7}', "2026-11-22"))
    assert got == {"theory": {"day": "2026-11-22", "checked": True, "needed": 7}}
    kept = json.loads(stub.answer('{"day": "2026-01-01"}', "2026-11-22"))
    assert kept == {"theory": {"day": "2026-01-01"}}


def test_a_body_already_wrapped_in_theory_is_not_wrapped_twice() -> None:
    stub = _module()
    got = json.loads(stub.answer('{"theory": {"needed": 7}}', "2026-11-22"))
    assert got == {"theory": {"day": "2026-11-22", "needed": 7}}


def test_a_body_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(TypeError, match="JSON object"):
        _module().answer("[1]", "2026-11-22")


def test_the_route_answers_and_everything_else_is_404() -> None:
    stub = _module()
    server = stub.ThreadingHTTPServer(
        ("127.0.0.1", 0), stub.handler(stub.answer('{"needed": 7}', "2026-11-22"))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("GET", "/api/theory")
        found = conn.getresponse()
        assert found.status == 200
        assert json.loads(found.read())["theory"]["needed"] == 7
        conn.request("GET", "/other")
        other = conn.getresponse()
        assert (other.status, other.read()) == (404, b"{}")
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_it_refuses_the_live_guards_port() -> None:
    with pytest.raises(SystemExit):
        _module().main(["--port", "8771", "--body", "{}", "--day", "2026-11-22"])

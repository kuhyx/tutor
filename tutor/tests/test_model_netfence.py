# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The sandbox's egress fence (``scripts/tutor_model_netfence.sh``).

The internet stays open; the LAN, the tailnet, docker / VPN bridges,
link-local and this machine's own addresses are refused, and the model
cannot lift the fence from inside.
"""

from __future__ import annotations

import ipaddress
import json
import shutil
import socket
import subprocess
from typing import TYPE_CHECKING, Any

import pytest

from tutor import research
from tutor.tests.test_model_sandbox import inside, pytestmark

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

__all__ = ["pytestmark"]  # the same skip: no usable bwrap, no fence either

NETFENCE = research.WRAPPER.parent / "tutor_model_netfence.sh"
# Probe script: connect to each (host, port) of argv, 3 s each, and print
# REACHED / refused / TIMEOUT per address.
_CONNECT = (
    "import socket, sys\n"
    "for pair in sys.argv[1:]:\n"
    "    host, port = pair.rsplit(':', 1)\n"
    "    s = socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET)\n"
    "    s.settimeout(3)\n"
    "    try:\n"
    "        s.connect((host, int(port)))\n"
    "        print('REACHED', pair)\n"
    "    except TimeoutError:\n"
    "        print('TIMEOUT', pair)\n"
    "    except OSError as err:\n"
    "        print('refused', pair, err)\n"
)


def connect_script(pairs: Iterable[str]) -> str:
    """Bash that runs the connect probe on ``host:port`` pairs."""
    return f"python3 - {' '.join(pairs)} <<'PY'\n{_CONNECT}PY"


@pytest.fixture
def root(tutor_sandbox: Path) -> Path:
    found = research.sandbox_root()
    (found / "home").mkdir(parents=True)
    return found


def _ip_json(*args: str) -> list[dict[str, Any]]:
    run = subprocess.run(
        [str(shutil.which("ip")), "-j", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return list(json.loads(run.stdout))


def _host_private_addresses() -> list[str]:
    """This machine's private IPv4 addresses that pasta does NOT copy into the
    namespace (those off the default-route interface: docker, VPN, tailnet).
    A connect to one of them leaves the namespace and lands on the host."""
    upstream = {route.get("dev") for route in _ip_json("route", "show", "default")}
    return [
        info["local"]
        for link in _ip_json("-4", "addr", "show")
        if link["ifname"] not in upstream | {"lo"}
        for info in link.get("addr_info", [])
        if not ipaddress.ip_address(info["local"]).is_global
    ]


def test_host_private_addresses_are_unreachable(root: Path) -> None:
    """The host's own docker / VPN / tailnet addresses: a listener there is
    a host service, pasta must not carry the model to it."""
    addresses = _host_private_addresses()
    if not addresses:
        pytest.skip("this machine has no private address off its uplink")
    listeners = []
    for address in addresses:
        listener = socket.socket()
        listener.bind((address, 0))
        listener.listen()
        listeners.append(listener)
    pairs = [
        f"{address}:{listener.getsockname()[1]}"
        for address, listener in zip(addresses, listeners, strict=True)
    ]
    try:
        run = inside(root, connect_script(pairs))
    finally:
        for listener in listeners:
            listener.close()
    assert run.returncode == 0, run.stderr
    lines = run.stdout.splitlines()
    assert len(lines) == len(addresses)
    assert all(line.startswith("refused ") for line in lines), run.stdout


# 2026-10-20 (kuhy): the internet stays open, private ranges do not.
PRIVATE_TARGETS = (
    "10.123.45.67:80",  # RFC1918 10/8
    "172.31.250.1:80",  # RFC1918 172.16/12
    "192.168.254.253:80",  # RFC1918 192.168/16 (the LAN, the router)
    "100.64.0.1:80",  # CGNAT, the tailnet
    "169.254.169.254:80",  # link-local (cloud metadata)
)


def test_private_ranges_are_refused_at_once(root: Path) -> None:
    run = inside(root, connect_script(PRIVATE_TARGETS))
    assert run.returncode == 0, run.stderr
    lines = run.stdout.splitlines()
    assert len(lines) == len(PRIVATE_TARGETS)
    assert all(line.startswith("refused ") for line in lines), run.stdout


def test_the_fence_cannot_be_lifted_from_inside(root: Path) -> None:
    script = (
        "grep CapEff /proc/self/status; "
        "nft flush ruleset && echo FLUSHED; " + connect_script(PRIVATE_TARGETS[:1])
    )
    run = inside(root, script)
    assert run.returncode == 0, run.stderr
    assert "CapEff:\t0000000000000000" in run.stdout
    assert "FLUSHED" not in run.stdout
    assert f"refused {PRIVATE_TARGETS[0]}" in run.stdout


def _fenced(*args: str) -> subprocess.CompletedProcess[str]:
    """The fence alone in a fresh pasta namespace (root there, as in the wrapper)."""
    return subprocess.run(
        [
            str(shutil.which("pasta")),
            "--quiet",
            "--config-net",
            "--",
            str(NETFENCE),
            *args,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_the_fence_rules() -> None:
    run = _fenced(
        "--dns",
        "198.51.100.53",
        "--host",
        "203.0.113.7",
        "--host",
        "2001:db8::7",
        "--",
        "nft",
        "list",
        "ruleset",
    )
    assert run.returncode == 0, run.stderr
    rules = run.stdout
    for blocked in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",
        "169.254.0.0/16",
        "fc00::/7",
        "fe80::/10",
        "203.0.113.7",
        "2001:db8::7",
    ):
        assert blocked in rules, blocked
    assert "198.51.100.53" in rules  # the resolver, port 53 only
    assert "dport 53" in rules
    assert 'oifname "lo" accept' in rules


def test_the_fence_fails_closed() -> None:
    run = _fenced("--host", "not-an-address", "--", "echo", "RAN")
    assert run.returncode != 0
    assert "RAN" not in run.stdout
    assert "egress" in run.stderr

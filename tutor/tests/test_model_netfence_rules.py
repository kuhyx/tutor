# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The egress fence needs no loadable kernel module.

A kernel upgrade removes the old ``/lib/modules`` tree, so an nft module that
was not already loaded (``nft_reject``: the ``reject`` verb) can no longer
load and the fence fails closed for good. These tests load the real fence in
a fresh pasta namespace, as ``tutor_model_sandbox.sh`` does, and need only
``pasta`` and ``nft`` (not bwrap).
"""

from __future__ import annotations

import shutil
import subprocess

from tutor import research
from tutor.tests._capability import skip_unless

NETFENCE = research.WRAPPER.parent / "tutor_model_netfence.sh"
# Connect to each host:port of argv; print "<outcome> <pair>" per address.
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
    "        print('refused', pair, err.errno)\n"
)


def _pasta_works() -> bool:
    if not (shutil.which("pasta") and shutil.which("nft")):
        return False
    run = subprocess.run(
        [str(shutil.which("pasta")), "--quiet", "--config-net", "--", "true"],
        check=False,
        capture_output=True,
        timeout=20,
    )
    return run.returncode == 0


pytestmark = skip_unless(works=_pasta_works(), reason="no usable pasta")


def fenced(*args: str) -> subprocess.CompletedProcess[str]:
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
        timeout=30,
    )


def test_the_fence_rules() -> None:
    run = fenced(
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
    assert "@private4 drop" in rules
    assert "@private6 drop" in rules


def test_the_ruleset_uses_no_module_backed_verb() -> None:
    """``reject`` (nft_reject / nft_reject_inet) is a loadable module."""
    run = fenced("--dns", "198.51.100.53", "--", "nft", "list", "ruleset")
    assert run.returncode == 0, run.stderr
    assert "reject" not in run.stdout
    assert "@private4 drop" in run.stdout


def test_the_script_names_no_module_backed_verb() -> None:
    """The source itself never emits ``reject`` (comments aside)."""
    code = [
        line
        for line in NETFENCE.read_text().splitlines()
        if not line.lstrip().startswith("#")
    ]
    assert not [line for line in code if "reject" in line]


def test_private_ranges_get_prohibit_routes_for_a_fast_refusal() -> None:
    run = fenced(
        "--host",
        "203.0.113.7",
        "--",
        "bash",
        "-c",
        "ip -4 route show type prohibit; ip -6 route show type prohibit",
    )
    assert run.returncode == 0, run.stderr
    for rng in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "100.64.0.0/10",
        "169.254.0.0/16",
        "203.0.113.7",
        "fc00::/7",
    ):
        assert rng in run.stdout, rng


def test_private_destinations_are_refused_at_once() -> None:
    pairs = ["10.123.45.67:80", "172.31.250.1:80", "100.64.0.1:80", "203.0.113.7:80"]
    run = fenced(
        "--host",
        "203.0.113.7",
        "--",
        "python3",
        "-c",
        _CONNECT,
        *pairs,
    )
    assert run.returncode == 0, run.stderr
    lines = run.stdout.splitlines()
    assert len(lines) == len(pairs)
    assert all(line.startswith("refused ") for line in lines), run.stdout


def test_a_private_resolver_keeps_a_working_route() -> None:
    """--dns inside a private range: its host route outranks the prohibit."""
    run = fenced(
        "--dns",
        "100.100.100.100",
        "--",
        "bash",
        "-c",
        "ip -4 route get 100.100.100.100; ip -4 route get 100.64.0.1 || true",
    )
    assert run.returncode == 0, run.stderr
    first, *rest = run.stdout.splitlines()
    assert "100.100.100.100" in first
    assert "prohibit" not in first
    assert "prohibit" in "".join(rest) or "Permission" in run.stderr


def test_the_fence_fails_closed() -> None:
    run = fenced("--host", "not-an-address", "--", "echo", "RAN")
    assert run.returncode != 0
    assert "RAN" not in run.stdout
    assert "not starting" in run.stderr


@pytest.mark.parametrize(
    ("dns", "first"),
    [((), "prohibit"), (("--dns", "169.254.169.254"), "169.254.169.254")],
)
def test_a_more_specific_link_local_route_is_prohibited_too(
    dns: tuple[str, ...], first: str
) -> None:
    """A cloud runner's metadata route beats the /16 prohibit unless replaced.

    GitHub's runners route ``169.254.169.254`` via the gateway; pasta copies
    it, so only the drop stopped it, as a timeout instead of a refusal. A
    resolver there (``--dns``) keeps its route.
    """
    setup = (
        "gw=\"$(ip -4 route show default | awk '{print $3; exit}')\"; "
        'ip -4 route add 169.254.169.254 via "$gw" && exec "$0" "$@"'
    )
    run = subprocess.run(
        [
            str(shutil.which("pasta")),
            "--quiet",
            "--config-net",
            "--",
            "sh",
            "-c",
            setup,
            str(NETFENCE),
            *dns,
            "--",
            "ip",
            "-4",
            "route",
            "show",
            "169.254.169.254",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.split()[0] == first, run.stdout

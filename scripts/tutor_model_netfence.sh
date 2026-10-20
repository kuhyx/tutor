#!/bin/bash
# ============================================================================
# tutor_model_netfence.sh -- the egress fence of the model's network namespace.
#
# tutor_model_sandbox.sh runs this as pasta's command: inside pasta's own
# user + network namespace, as that namespace's root (CAP_NET_ADMIN over this
# netns only, nothing on the host). It loads an nftables output filter, then
# execs the rest of its argv (bwrap), which drops every capability and nests
# a user namespace of its own, so the model cannot unload the filter.
#
# Refused (fast, with an ICMP reject rather than a timeout):
#   - private and local ranges: RFC1918 10/8, 172.16/12, 192.168/16, CGNAT and
#     the tailnet 100.64/10, link-local 169.254/16, 0/8, IPv6 ULA fc00::/7,
#     link-local fe80::/10 and IPv4-mapped ::ffff:0:0/96;
#   - every --host address (the caller passes the host's own addresses).
# Allowed: the namespace's own loopback, and port 53 (UDP and TCP) to each
# --dns address (the host's resolvers, which may well be private: the router,
# Tailscale's 100.100.100.100). Everything else (the internet) passes.
# Fails closed: if the filter does not load, nothing is exec'd.
#
# Usage: tutor_model_netfence.sh [--dns ADDR]... [--host ADDR]... -- CMD...
# ============================================================================

set -euo pipefail

readonly PRIVATE_V4=(
    0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 169.254.0.0/16 172.16.0.0/12
    192.168.0.0/16
)
readonly PRIVATE_V6=(fc00::/7 fe80::/10 ::ffff:0:0/96)

die() {
    echo "tutor_model_netfence: $*" >&2
    exit 1
}

# "a, b, c" for an nft set literal.
joined() {
    local IFS=,
    echo "$*"
}

# The ruleset for the --dns and --host addresses in DNS / HOSTS.
ruleset() {
    local -a v4=("${PRIVATE_V4[@]}") v6=("${PRIVATE_V6[@]}") dns4=() dns6=()
    local addr
    for addr in "${HOSTS[@]}"; do
        if [[ "$addr" == *:* ]]; then v6+=("$addr"); else v4+=("$addr"); fi
    done
    for addr in "${DNS[@]}"; do
        if [[ "$addr" == *:* ]]; then dns6+=("$addr"); else dns4+=("$addr"); fi
    done
    echo "table inet tutor_fence {"
    echo "  set private4 { type ipv4_addr; flags interval; auto-merge; elements = { $(joined "${v4[@]}") } }"
    echo "  set private6 { type ipv6_addr; flags interval; auto-merge; elements = { $(joined "${v6[@]}") } }"
    echo "  chain output {"
    echo "    type filter hook output priority filter; policy accept;"
    echo "    oifname \"lo\" accept"
    # Neighbour discovery stays: without it IPv6 to the gateway never starts.
    echo "    icmpv6 type { nd-neighbor-solicit, nd-neighbor-advert, nd-router-solicit } accept"
    if ((${#dns4[@]})); then
        echo "    ip daddr { $(joined "${dns4[@]}") } meta l4proto { tcp, udp } th dport 53 accept"
    fi
    if ((${#dns6[@]})); then
        echo "    ip6 daddr { $(joined "${dns6[@]}") } meta l4proto { tcp, udp } th dport 53 accept"
    fi
    echo "    ip daddr @private4 reject with icmpx admin-prohibited"
    echo "    ip6 daddr @private6 reject with icmpx admin-prohibited"
    echo "  }"
    echo "}"
}

main() {
    DNS=()
    HOSTS=()
    while (($#)); do
        case "$1" in
            --dns) DNS+=("${2:?--dns needs an address}"); shift 2 ;;
            --host) HOSTS+=("${2:?--host needs an address}"); shift 2 ;;
            --) shift; break ;;
            *) die "unknown option: $1" ;;
        esac
    done
    (($#)) || die "no command to run behind the fence"
    command -v nft >/dev/null || die "nft (nftables) is not installed"
    ruleset | nft -f - || die "the egress filter did not load; not starting"
    exec "$@"
}

main "$@"

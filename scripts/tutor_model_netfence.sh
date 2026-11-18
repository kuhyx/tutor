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
# Refused:
#   - private and local ranges: RFC1918 10/8, 172.16/12, 192.168/16, CGNAT and
#     the tailnet 100.64/10, link-local 169.254/16, 0/8, IPv6 ULA fc00::/7,
#     link-local fe80::/10 and IPv4-mapped ::ffff:0:0/96;
#   - every --host address (the caller passes the host's own addresses).
# Allowed: the namespace's own loopback, and port 53 (UDP and TCP) to each
# --dns address (the host's resolvers, which may well be private: the router,
# Tailscale's 100.100.100.100). Everything else (the internet) passes.
# Fails closed: if the filter does not load, nothing is exec'd.
#
# Needs no loadable kernel module beyond nf_tables itself. A kernel upgrade
# deletes the old /lib/modules tree, after which an nft module that was not
# already loaded (nft_reject / nft_reject_inet, the verb "reject") cannot
# load, and a ruleset using one fails closed for good. So the filter only
# drops (nf_tables core: named interval sets, payload and meta matches), and
# the fast refusal comes from routing, which is never a module: a prohibit
# route per private range makes connect() fail at once with EACCES.
#   - A resolver inside a private range gets a host route copied from its
#     current route, so port 53 to it keeps working.
#   - A private address on the namespace's own connected subnet (the LAN) is
#     routed on-link, more specific than the prohibit: only the drop stops
#     it, as a timeout rather than a fast refusal.
# The drop is the guarantee; the routes only make refusals fast.
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
    echo "    ip daddr @private4 drop"
    echo "    ip6 daddr @private6 drop"
    echo "  }"
    echo "}"
}

# "-4 32" or "-6 128" for an address: the ip(8) family flag and host prefix.
family() {
    if [[ "$1" == *:* ]]; then echo "-6 128"; else echo "-4 32"; fi
}

# Keep every --dns resolver reachable under the prohibit routes: a host route
# copied from the route it has now (gateway and device). Made before them.
dns_routes() {
    local addr fam plen gw dev
    for addr in "${DNS[@]}"; do
        read -r fam plen <<<"$(family "$addr")"
        gw="" dev=""
        read -r gw dev < <(ip -j "$fam" route get "$addr" 2>/dev/null |
            jq -r '.[0] | "\(.gateway // "-") \(.dev)"') || true
        [[ -n "$dev" && "$dev" != lo ]] || continue
        if [[ "$gw" == - ]]; then
            ip "$fam" route replace "$addr/$plen" dev "$dev"
        else
            ip "$fam" route replace "$addr/$plen" via "$gw" dev "$dev"
        fi
    done
}

# One prohibit route per private range and --host address: connect() fails at
# once (EACCES) with no nft module. Fatal on failure, like the filter.
prohibit_routes() {
    local range addr
    for range in "${PRIVATE_V4[@]}"; do ip -4 route replace prohibit "$range" || return 1; done
    for range in "${PRIVATE_V6[@]}"; do ip -6 route replace prohibit "$range" || return 1; done
    for addr in "${HOSTS[@]}"; do
        if [[ "$addr" == *:* ]]; then
            ip -6 route replace prohibit "$addr/128" || return 1
        else
            ip -4 route replace prohibit "$addr/32" || return 1
        fi
    done
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
    command -v ip >/dev/null || die "ip (iproute2) is not installed"
    command -v jq >/dev/null || die "jq is not installed"
    dns_routes
    prohibit_routes || die "the prohibit routes did not load; not starting"
    ruleset | nft -f - || die "the egress filter did not load; not starting"
    exec "$@"
}

main "$@"

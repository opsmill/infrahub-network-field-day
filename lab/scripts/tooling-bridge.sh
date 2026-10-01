#!/usr/bin/env bash
# Create the tooling bridge, and give this host an address on it.
#
# WHY THIS EXISTS AT ALL, because a bridge is an odd thing for a lab to need.
#
# Everything else in this topology is a point-to-point veth between two
# containerlab nodes. The tooling network is different on purpose: the HOST has
# to be on it. That is what breaks the circular dependency Infrahub would
# otherwise have -- Infrahub configures the fabric, the fabric carries the
# workload cluster, and a tooling cluster reachable only through the fabric
# could never be brought up before the fabric existed.
#
# Being L2-adjacent to the host means the tooling cluster comes up with no
# fabric and no firewall in the path, while branch users still reach it the hard
# way: WAN -> border-leaf1 -> fw1 -> the `tooling` zone. One network, two paths,
# and the firewall governs only the one that should be governed.
#
# It also gives the lab a single address range that EVERY party can reach -- the
# host, containers on the host, pods in the tooling cluster, and the branch
# desktop. That is what makes one OIDC issuer possible; without it the issuer
# has to be reachable from both the management plane and the routed lab, and no
# such address exists.
#
# A PRECONDITION OF EVERY DEPLOY, not a one-off setup step. `br-otter-tool` is a
# `kind: bridge` node, and ContainerLab does not create one -- it refuses the
# whole topology before starting any node:
#
#   ERROR  Bridge "br-otter-tool" referenced in topology but does not exist.
#
# A host bridge does not survive a reboot, so both deploy paths run this first:
# the `deploy` and `deploy-lite` targets here, and `invoke lab` in the Infrahub
# repository, which drives ContainerLab directly and never reads this Makefile.
# It is idempotent so running it twice costs nothing.
set -eu

BRIDGE="${OTTERNET_TOOLING_BRIDGE:-br-otter-tool}"
HOST_ADDR="${OTTERNET_TOOLING_HOST_ADDR:-10.90.0.1/24}"
# The branch LAN, and the firewall's address on this bridge. See the return-path
# note further down for why the host needs a route for one via the other.
BRANCH_LAN="${OTTERNET_BRANCH_LAN:-10.70.0.0/24}"
TOOLING_GW="${OTTERNET_TOOLING_GW:-10.90.0.254}"

log() { echo "[tooling-bridge] $*"; }

if ! ip link show "$BRIDGE" >/dev/null 2>&1; then
    sudo ip link add name "$BRIDGE" type bridge
    log "created $BRIDGE"
else
    log "$BRIDGE already exists"
fi

sudo ip link set "$BRIDGE" up

# The host's own address on the tooling network. `replace` rather than `add` so
# re-running does not fail on an address that is already there.
sudo ip addr replace "$HOST_ADDR" dev "$BRIDGE"
log "$BRIDGE -> $HOST_ADDR"

# Containers on the host's docker networks reach the tooling network through the
# host, so the host must forward between them. Docker usually sets this
# globally, but a lab should not depend on another daemon's side effect.
if [ "$(cat /proc/sys/net/ipv4/ip_forward)" != "1" ]; then
    sudo sysctl -w net.ipv4.ip_forward=1 >/dev/null
    log "enabled net.ipv4.ip_forward"
fi

# Bridges inherit the host's netfilter rules. Docker's default FORWARD policy is
# DROP, which silently blackholes traffic between a docker network and this
# bridge -- the symptom is Infrahub being unable to reach the tooling cluster
# while the host itself can, which reads as a container DNS problem.
if command -v iptables >/dev/null 2>&1; then
    if ! sudo iptables -C DOCKER-USER -i "$BRIDGE" -j ACCEPT 2>/dev/null; then
        sudo iptables -I DOCKER-USER -i "$BRIDGE" -j ACCEPT
        log "allowed $BRIDGE -> docker networks in DOCKER-USER"
    fi
    if ! sudo iptables -C DOCKER-USER -o "$BRIDGE" -j ACCEPT 2>/dev/null; then
        sudo iptables -I DOCKER-USER -o "$BRIDGE" -j ACCEPT
        log "allowed docker networks -> $BRIDGE in DOCKER-USER"
    fi
fi

# THE RETURN PATH, which is the half that is easy to forget.
#
# A branch user reaching Infrahub arrives at 10.90.0.1:8000 from 10.70.0.20,
# having come through fw1. The host answers -- and with no route for the branch
# LAN it answers out its DEFAULT route, to the internet, where the reply is
# dropped. The symptom is a connection that hangs and then times out with no
# packet logged anywhere in the lab: the request arrived, the firewall permitted
# it, and only the reply went missing.
#
# `onlink` because fw1's 10.90.0.254 is on this bridge and the host has no other
# way to know that before the firewall is up.
if ! ip route show "$BRANCH_LAN" | grep -q "$TOOLING_GW"; then
    sudo ip route replace "$BRANCH_LAN" via "$TOOLING_GW" dev "$BRIDGE" onlink
    log "$BRANCH_LAN via $TOOLING_GW (return path for branch users)"
fi

log "ready"

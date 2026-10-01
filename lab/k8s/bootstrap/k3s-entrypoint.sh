#!/bin/sh
# Bring the fabric-facing interface up before handing over to k3s.
#
# containerlab creates the container first and wires veth pairs into it a moment
# later, so k3s cannot be allowed to start until eth1 exists and carries the node
# IP -- otherwise kubelet and Cilium latch onto the management address and the
# fabric never learns a usable next hop.
#
# Usage: k3s-entrypoint.sh <server|agent> [k3s args...]
# Env:   FABRIC_IPV4    address/prefix for eth1   (e.g. 10.110.0.11/24)
#        FABRIC_GW      EVPN anycast gateway      (e.g. 10.110.0.1)
#        FABRIC_ROUTES  space-separated prefixes to route via the fabric
#        FABRIC_MTU     must match the switch MTU (default 9214)
set -eu

ROLE="${1:?usage: k3s-entrypoint.sh <server|agent> [args...]}"
shift

log() { echo "[k3s-entrypoint] $*"; }

# --- wait for containerlab to wire the fabric link ---------------------------
# Be patient here, and understand why: giving up is not recoverable.
#
# containerlab adds this veth into the container's network namespace from the
# outside, after the container is already running. If this script exits, docker
# restarts the container, and the restart builds a NEW network sandbox -- which
# does not have the veth, and containerlab is long gone and will not add it
# again. So the node restarts, times out, and restarts forever, having
# permanently lost its fabric link. The only recovery is a full redeploy.
#
# The original 120s was enough on an idle host and not enough on a busy one: a
# redeploy while seven ceOS nodes are booting pushed two of the three k8s nodes
# past it and into exactly that loop. Ten minutes costs nothing when the link
# does appear (it usually takes a second or two) and avoids an unrecoverable
# state when it does not.
FABRIC_LINK_TIMEOUT="${FABRIC_LINK_TIMEOUT:-600}"
waited=0
while [ ! -e /sys/class/net/eth1 ]; do
    waited=$((waited + 1))
    # Say something occasionally, so a slow wire looks different from a hang.
    if [ $((waited % 60)) -eq 0 ]; then
        log "still waiting for eth1 after $((waited / 2))s (timeout ${FABRIC_LINK_TIMEOUT}s)"
    fi
    if [ "$waited" -gt $((FABRIC_LINK_TIMEOUT * 2)) ]; then
        log "FATAL: eth1 did not appear after ${FABRIC_LINK_TIMEOUT}s."
        log "       Is the topology link defined? Note that exiting here is"
        log "       unrecoverable: the restart drops the namespace containerlab"
        log "       wired into, so fix the topology and redeploy the lab."
        exit 1
    fi
    sleep 0.5
done
log "eth1 present after $((waited / 2))s"

# --- address the fabric side -------------------------------------------------
# MTU must match what AVD configures on the switch (p2p_uplinks_mtu /
# default_interface_mtu = 9214). containerlab creates workload veths at 9500,
# so leaving it alone means TCP negotiates a ~9460 byte MSS, the resulting
# frames exceed the leaf MTU and are silently dropped. The symptom is nasty:
# ping works (it fragments), the k3s agent's API connections show as
# ESTABLISHED, but Send-Q never drains and the cluster never converges.
ip link set eth1 mtu "${FABRIC_MTU:-9214}"
ip link set eth1 up
log "eth1 MTU ${FABRIC_MTU:-9214} (must match the switch)"
if [ -n "${FABRIC_IPV4:-}" ]; then
    ip addr replace "$FABRIC_IPV4" dev eth1
    log "eth1 -> $FABRIC_IPV4"
fi

# Default route deliberately stays on eth0 (containerlab management) so image
# pulls keep working; only fabric prefixes are steered at the anycast gateway.
if [ -n "${FABRIC_GW:-}" ]; then
    for prefix in ${FABRIC_ROUTES:-}; do
        ip route replace "$prefix" via "$FABRIC_GW" dev eth1 && \
            log "route $prefix via $FABRIC_GW"
    done
fi

# --- pod egress to the internet ----------------------------------------------
# Masquerade pod traffic leaving via the MANAGEMENT interface only.
#
# Cilium runs with masquerading disabled on purpose: pods have to appear on the
# fabric as pod IPs, or the leaf ACLs and the firewall zone policies are acting
# on node addresses and the whole security story is decorative. That is right
# for east-west traffic and fatal for anything that has to reach a registry or a
# chart repo from *inside* a pod -- the packet leaves with source 10.111.x.y,
# hits the internet, and nothing comes back.
#
# It goes unnoticed for a long time because image pulls work: containerd runs in
# this container's own netns, not a pod's. The moment an in-cluster controller
# needs to fetch something -- Crossplane resolving a package, provider-helm
# pulling a chart -- it fails with a DNS or connection timeout that looks like a
# cluster networking fault.
#
# The exclusion is what keeps both properties: anything destined for 10.0.0.0/8
# (the fabric, the other tenant, pods, services, nodes) is never touched, so the
# fabric still sees real pod addresses. Only traffic that is actually leaving for
# the internet, via eth0, gets SNATed to the node's management address. A real
# cluster has exactly this shape: a management egress path separate from the
# data fabric.
POD_CIDR="${POD_CIDR:-10.111.0.0/16}"
if ! iptables -t nat -C POSTROUTING -s "$POD_CIDR" ! -d 10.0.0.0/8 -o eth0 \
        -j MASQUERADE 2>/dev/null; then
    iptables -t nat -A POSTROUTING -s "$POD_CIDR" ! -d 10.0.0.0/8 -o eth0 \
        -j MASQUERADE
fi
log "pod egress: $POD_CIDR -> eth0 masqueraded (10.0.0.0/8 excluded)"

# --- DNS that a pod can actually use -----------------------------------------
# Docker hands this container a resolv.conf pointing at 127.0.0.11, its embedded
# resolver. That listener lives in *this* netns, so CoreDNS -- which runs with
# dnsPolicy: Default and therefore inherits this file -- forwards every external
# query to a loopback address inside its own pod, where nothing is listening.
# Cluster-internal names resolve fine (CoreDNS answers those itself), external
# names fail with "server misbehaving", and it is not obvious that DNS is only
# half broken.
#
# Docker records the real upstreams it is proxying for in a comment in the same
# file, so use those; fall back to a public resolver if the comment is absent.
# Override with DNS_UPSTREAM if this host resolves differently.
if [ -z "${DNS_UPSTREAM:-}" ]; then
    DNS_UPSTREAM=$(sed -n 's/^# ExtServers: \[\(.*\)\]$/\1/p' /etc/resolv.conf \
        | tr -d ' ' | tr ',' ' ')
fi
DNS_UPSTREAM="${DNS_UPSTREAM:-1.1.1.1}"
if echo "$DNS_UPSTREAM" | grep -q '[0-9]'; then
    {
        echo "# Rewritten by k3s-entrypoint.sh: 127.0.0.11 is unreachable from a"
        echo "# pod netns, and CoreDNS inherits this file."
        for ns in $DNS_UPSTREAM; do echo "nameserver $ns"; done
    } > /etc/resolv.conf.new
    cat /etc/resolv.conf.new > /etc/resolv.conf 2>/dev/null \
        && log "resolv.conf upstream -> $DNS_UPSTREAM" \
        || log "warning: could not rewrite resolv.conf"
    rm -f /etc/resolv.conf.new
fi

# --- k3s runtime prerequisites ----------------------------------------------
# The image declares no tmpfs and its entrypoint is the k3s binary itself, so the
# bits k3d normally sets up have to happen here.
grep -q ' /run ' /proc/mounts || mount -t tmpfs -o mode=755 tmpfs /run
[ -e /dev/kmsg ] || ln -s /dev/console /dev/kmsg

# --- Cilium prerequisites ----------------------------------------------------
# Cilium's mount-bpf-fs init container mounts bpffs from inside a pod, which
# requires /sys/fs/bpf to already exist here AND to be a *shared* mount so the
# nested mount propagates. Without this every cilium pod dies in
# CreateContainerError with:
#   path "/sys/fs/bpf" is mounted on "/sys" but it is not a shared mount
# k3d does this for you; running k3s as a plain containerlab node does not.
mount --make-rshared / 2>/dev/null || log "warning: could not make / rshared"
grep -q ' /sys/fs/bpf ' /proc/mounts || mount -t bpf bpf /sys/fs/bpf
mount --make-shared /sys/fs/bpf
log "bpffs mounted shared at /sys/fs/bpf"

# --- hand over to k3s as PID 1 ----------------------------------------------
# `exec` is load-bearing. k3s must BE pid 1.
#
# On cgroups v2 k3s applies its own nesting workaround before starting kubelet:
# it moves the existing processes into a child cgroup and enables the
# controllers in the subtree, because cgroup v2 forbids a cgroup from having
# both processes and domain controllers ("no internal processes"). k3s only does
# this when it finds itself running as pid 1.
#
# Supervising k3s from a wrapper -- which is tempting, see below -- means it is
# pid 2 and skips that entirely, and kubelet then dies on:
#   Failed to start ContainerManager
#   cannot enter cgroupv2 "/sys/fs/cgroup/kubepods" with domain controllers
#   -- it is in an invalid state
# which looks like a host cgroup problem and is not. If a wrapper is ever
# genuinely needed here, it has to do the nesting itself the way k3d's
# entrypoint does: create /sys/fs/cgroup/init, move every pid into it, then
# write the controllers into cgroup.subtree_control.
#
# The tempting reason to wrap it: containerlab starts these nodes with
# --restart=always, and pushes each veth into the network namespace from the
# outside after the container is up. A restart builds a NEW namespace without
# that veth, and containerlab will not add it again -- so anything that kills
# pid 1 costs the node its fabric link until the lab is redeployed. Keeping pid
# 1 alive would avoid that, but it breaks the cluster outright, so the trade is
# not available. The mitigations are instead: do not give k3s arguments it will
# reject (a server-only flag on an agent is the way this has actually bitten),
# and the long link wait above, which leaves a window to rebuild the veth by
# hand -- see docs/troubleshooting.md, "A k8s node has no eth1".
log "starting k3s $ROLE"
exec /bin/k3s "$ROLE" "$@"

"""`invoke demo-break-peer`: a Cilium BGP peer whose AS number disagrees with the cluster's.

Two values in Infrahub describe one BGP session from its two ends. ``ClusterKubernetes.local_asn``
is the AS number Cilium runs, delivered through Crossplane. ``RoutingVrfBgpPeer.remote_asn`` is the
AS number the k8s leaves expect from each node, rendered into their configuration. No check
compares the two, so a proposed change that mistypes one passes every validator, merges, and is
pushed by the reconciler. The switch then runs exactly its artifact and the session never comes
up: every tool that compares a device with its intent reports that nothing is wrong.

The demonstration starts from that state. The audience investigates the switch through the
Arista EOS MCP server and the intent through the Infrahub MCP server, and fixes it with a
proposed change. Only pure functions live here; ``tasks.py`` does the I/O. Host-side only.
"""

from __future__ import annotations

from typing import Any

# The node broken by default. k8s-node2 is the only node behind the lab DNS and Grafana
# addresses (both use externalTrafficPolicy Local), so breaking it takes those down too.
DEFAULT_NODE = "k8s-node3"
# 65401 with two digits swapped: the mistake a person makes typing it.
WRONG_ASN = 64501
BREAK_BRANCH_PREFIX = "demo-peer-asn"
FIX_BRANCH_PREFIX = "demo-peer-asn-fix"
# The two k8s leaves, by ContainerLab container. Both peer with every node.
LEAF_CONTAINERS = ("clab-otternet-k8s-leaf1", "clab-otternet-k8s-leaf2")
VRF = "K8S_PROD"


def peer_description(node: str) -> str:
    """The `description` that names a node's Cilium peer in the seed data (`k8s-node3-cilium`)."""
    return f"{node}-cilium"


def sole_backed_services(services: dict[str, Any], slices: dict[str, Any], node: str) -> list[str]:
    """LoadBalancer services whose every ready endpoint runs on ``node``, as `namespace/name`.

    With externalTrafficPolicy Local a service's address is announced only from the nodes that run
    one of its pods. If all of them are on ``node``, losing that node's BGP session takes the
    service off the network, which is a different and much louder fault than the one wanted.
    ``services`` and ``slices`` are `kubectl get svc,endpointslices -A -o json` output.
    """
    nodes_by_service: dict[tuple[str, str], set[str]] = {}
    for item in slices.get("items") or []:
        meta = item.get("metadata") or {}
        service = (meta.get("labels") or {}).get("kubernetes.io/service-name")
        if not service:
            continue
        key = (str(meta.get("namespace")), str(service))
        for endpoint in item.get("endpoints") or []:
            if (endpoint.get("conditions") or {}).get("ready") is False:
                continue
            if endpoint.get("nodeName"):
                nodes_by_service.setdefault(key, set()).add(str(endpoint["nodeName"]))
    hit = []
    for item in services.get("items") or []:
        if (item.get("spec") or {}).get("type") != "LoadBalancer":
            continue
        meta = item.get("metadata") or {}
        key = (str(meta.get("namespace")), str(meta.get("name")))
        if nodes_by_service.get(key) == {node}:
            hit.append(f"{key[0]}/{key[1]}")
    return sorted(hit)


def leaf_peer(summary: dict[str, Any], address: str, vrf: str = VRF) -> tuple[int | None, str]:
    """The AS number a leaf expects from ``address`` and the session state, from `show ip bgp summary | json`."""
    peer = (((summary.get("vrfs") or {}).get(vrf) or {}).get("peers") or {}).get(address) or {}
    asn = str(peer.get("asn") or "")
    return (int(asn) if asn.isdigit() else None), str(peer.get("peerState") or "missing")


def leaf_reached(asn: int | None, state: str, want_asn: int, *, broken: bool) -> bool:
    """Whether a leaf runs ``want_asn`` for the peer, and the session is in the state that goes with it.

    A wrong AS number never establishes, so when breaking, the leaf is done as soon as it runs it.
    When fixing, it is done only once the session is up.
    """
    if asn != want_asn:
        return False
    return broken or state == "Established"

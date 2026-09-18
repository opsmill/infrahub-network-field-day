"""Contract tests for the Kubernetes layer built on the marketplace cluster schema.

`schemas/cluster/cluster.yml` is downloaded (`infrahub/cluster`);
`schemas/cluster/kubernetes.yml` is authored here and holds only what nothing
published covers -- the CNI, the pod/service/node ranges, the VIP pools, and
the BGP contract with the fabric.

The assertions that matter most are the ones proving we did NOT re-model what
upstream already provides: no second cluster kind, no Kubernetes-specific node
kind, and no restated name or description.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).parents[2]

CLUSTER_SCHEMA = "schemas/cluster/cluster.yml"
KUBERNETES_SCHEMA = "schemas/cluster/kubernetes.yml"

IPAM_PREFIX_RELATIONSHIPS = ("pod_prefix", "service_prefix", "node_prefix")


def _load_yaml(path: str) -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def _nodes(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return list(schema.get("nodes", []))


def _node(schema: dict[str, Any], namespace: str, name: str) -> dict[str, Any]:
    for node in _nodes(schema):
        if node.get("namespace") == namespace and node.get("name") == name:
            return node
    raise AssertionError(f"{namespace}{name} node not found")


def _generic(schema: dict[str, Any], namespace: str, name: str) -> dict[str, Any]:
    for generic in schema.get("generics") or []:
        if generic.get("namespace") == namespace and generic.get("name") == name:
            return generic
    raise AssertionError(f"{namespace}{name} generic not found")


def _attributes(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {attr["name"]: attr for attr in node.get("attributes", [])}


def _relationships(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rel["name"]: rel for rel in node.get("relationships", [])}


def _all_attribute_kinds(schema: dict[str, Any]) -> set[str]:
    kinds: set[str] = set()
    for section in ("generics", "nodes"):
        for entry in schema.get(section) or []:
            kinds.update(attr.get("kind", "") for attr in entry.get("attributes") or [])
    return kinds


# ---------------------------------------------------------------------------
# The contract with upstream
# ---------------------------------------------------------------------------


def test_adopted_cluster_schema_provides_the_generics_we_build_on() -> None:
    schema = _load_yaml(CLUSTER_SCHEMA)

    assert _generic(schema, "Cluster", "Generic")
    assert _generic(schema, "Cluster", "GenericComputeUnitNodes")


def test_cluster_members_are_plain_compute_units() -> None:
    """Upstream already models "machine that belongs to a cluster".

    `ClusterGenericComputeUnitNodes.nodes` peers ComputeGenericUnit, which this
    repository already defines. That is why there is no Kubernetes node kind
    here -- a second kind for the same idea would be a parallel structure, and
    the per-node BGP flag it would carry is expressed by the cluster's
    node_selector instead, which is how the CNI actually decides.
    """
    binding = _generic(_load_yaml(CLUSTER_SCHEMA), "Cluster", "GenericComputeUnitNodes")
    nodes = _relationships(binding)["nodes"]

    assert nodes["peer"] == "ComputeGenericUnit"
    assert nodes["kind"] == "Component"
    assert nodes["identifier"] == "worker_in_cluster"


def test_no_kubernetes_node_kind_is_declared() -> None:
    """The regression this file exists to prevent."""
    declared = {f"{n.get('namespace', '')}{n.get('name', '')}" for n in _nodes(_load_yaml(KUBERNETES_SCHEMA))}

    assert "KubernetesNode" not in declared
    assert "ClusterKubernetesNode" not in declared


def test_no_second_cluster_kind_is_declared() -> None:
    declared = {f"{n.get('namespace', '')}{n.get('name', '')}" for n in _nodes(_load_yaml(KUBERNETES_SCHEMA))}

    assert declared == {"ClusterKubernetes", "ClusterFabricPeering"}


# ---------------------------------------------------------------------------
# ClusterKubernetes -- the authored additions
# ---------------------------------------------------------------------------


def test_kubernetes_cluster_inherits_rather_than_restates() -> None:
    cluster = _node(_load_yaml(KUBERNETES_SCHEMA), "Cluster", "Kubernetes")
    inherits = set(cluster.get("inherit_from") or [])

    assert {"ClusterGeneric", "ClusterGenericComputeUnitNodes", "GeneratorTarget"} <= inherits


def test_kubernetes_cluster_does_not_redeclare_inherited_fields() -> None:
    """name, description, locations and tags come from ClusterGeneric."""
    cluster = _node(_load_yaml(KUBERNETES_SCHEMA), "Cluster", "Kubernetes")
    attributes = set(_attributes(cluster))
    relationships = set(_relationships(cluster))

    assert not {"name", "description"} & attributes
    assert not {"locations", "tags", "nodes"} & relationships
    for inherited in ("human_friendly_id", "display_label", "order_by", "uniqueness_constraints"):
        assert inherited not in cluster, f"{inherited} is inherited from ClusterGeneric"


def test_kubernetes_cluster_carries_the_cni_and_bgp_settings() -> None:
    """The genuinely absent part: nothing published models a CNI that peers BGP."""
    cluster = _node(_load_yaml(KUBERNETES_SCHEMA), "Cluster", "Kubernetes")
    attributes = _attributes(cluster)

    assert attributes["cni_kind"]["kind"] == "Dropdown"
    assert "cilium" in {c["name"] for c in attributes["cni_kind"]["choices"]}
    assert attributes["local_asn"]["kind"] == "Number"
    assert attributes["local_asn"]["parameters"]["max_value"] == 4294967295
    assert attributes["bgp_timers"]["kind"] == "JSON"
    # A List of key=value strings, not a JSON map: Infrahub 1.10.6 returns a
    # 500 for a JSON attribute key containing a dot or a slash, and every
    # Kubernetes label selector looks like `otternet.lab/bgp`.
    assert attributes["node_selector"]["kind"] == "List"


def test_kubernetes_cluster_stores_only_a_secret_name() -> None:
    """The secret's name, never its value -- Infrahub is not a secret store."""
    cluster = _node(_load_yaml(KUBERNETES_SCHEMA), "Cluster", "Kubernetes")
    attributes = _attributes(cluster)

    assert attributes["bgp_auth_secret_name"]["kind"] == "Text"
    assert not {name for name in attributes if "password" in name}


def test_cluster_networks_are_ipam_relationships_not_attributes() -> None:
    """The same ranges are matched on by the leaves, the firewall and the CNI."""
    cluster = _node(_load_yaml(KUBERNETES_SCHEMA), "Cluster", "Kubernetes")
    relationships = _relationships(cluster)
    attribute_names = set(_attributes(cluster))

    for name in IPAM_PREFIX_RELATIONSHIPS:
        assert relationships[name]["peer"] == "IpamPrefix"
        assert relationships[name]["cardinality"] == "one"
        assert relationships[name]["optional"] is False
        assert name not in attribute_names


# ---------------------------------------------------------------------------
# ClusterFabricPeering
# ---------------------------------------------------------------------------


def test_peering_is_unique_per_cluster_and_peer_device() -> None:
    peering = _node(_load_yaml(KUBERNETES_SCHEMA), "Cluster", "FabricPeering")

    assert peering["uniqueness_constraints"] == [["cluster", "peer_device"]]


def test_peering_names_one_device_and_one_address_on_it() -> None:
    """Both mandatory and singular, which forces a leaf's own SVI address to be
    recorded rather than the MLAG pair's shared VARP gateway -- an anycast
    address cannot identify a single BGP peer."""
    peering = _node(_load_yaml(KUBERNETES_SCHEMA), "Cluster", "FabricPeering")
    relationships = _relationships(peering)

    for name, peer in (("peer_device", "DcimGenericDevice"), ("peer_address", "IpamIPAddress")):
        assert relationships[name]["peer"] == peer
        assert relationships[name]["cardinality"] == "one"
        assert relationships[name]["optional"] is False


def test_peering_links_to_the_fabric_side_neighbour() -> None:
    """Reuses the repository's existing BGP model for the other half.

    The marketplace's routing_bgp was evaluated and rejected: it brings a
    second RoutingBGPPeerGroup colliding with this repository's, and a
    RoutingAutonomousSystem duplicating RoutingAsn.
    """
    peering = _node(_load_yaml(KUBERNETES_SCHEMA), "Cluster", "FabricPeering")
    relationships = _relationships(peering)

    assert relationships["peer_neighbor"]["peer"] == "RoutingBGPNeighbor"
    assert relationships["svi"]["peer"] == "EvpnSvi"


def test_peering_points_back_at_its_cluster_as_parent() -> None:
    peering = _node(_load_yaml(KUBERNETES_SCHEMA), "Cluster", "FabricPeering")
    cluster_rel = _relationships(peering)["cluster"]

    assert cluster_rel["kind"] == "Parent"
    assert cluster_rel["peer"] == "ClusterKubernetes"
    assert cluster_rel["identifier"] == "cluster__fabric_peerings"


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------


def test_no_inline_network_attributes_are_declared() -> None:
    assert not {"IPNetwork", "IPHost"} & _all_attribute_kinds(_load_yaml(KUBERNETES_SCHEMA))


def test_no_cluster_node_references_a_service_kind() -> None:
    peers = {
        rel.get("peer", "") for node in _nodes(_load_yaml(KUBERNETES_SCHEMA)) for rel in node.get("relationships") or []
    }

    assert not {peer for peer in peers if peer.startswith("Service")}

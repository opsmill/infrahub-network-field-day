"""Unit tests for the Crossplane FabricPeering manifest transform.

Fixtures rather than a live server, for a reason beyond speed: the error paths
are only reachable this way. A cluster with no ``local_asn`` or a peering with
no ``peer_address`` cannot be created against the live schema, because the
schema's own constraints forbid them -- but a transform can still be handed
that shape by a partially-migrated database or a future schema edit, so the
guard has to be tested.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
import yaml

from transforms.crossplane_fabric_peering import CrossplaneFabricPeeringTransform

# The values actually loaded, so a fixture failure means the transform changed
# rather than the lab did.
LEAF1_ADDRESS = "10.110.0.2/24"
LEAF2_ADDRESS = "10.110.0.3/24"
LOCAL_ASN = 65401
PEER_ASN = 65101


def _peering(
    name: str,
    address: str | None,
    *,
    enabled: bool = True,
    peer_asn: int = PEER_ASN,
) -> dict[str, Any]:
    """One ClusterFabricPeering edge. `address=None` omits the relationship."""
    return {
        "node": {
            "id": f"peering-{name}",
            "name": {"value": name},
            "peer_asn": {"value": peer_asn},
            "enabled": {"value": enabled},
            "peer_address": ({"node": {"address": {"value": address}}} if address else {"node": None}),
        }
    }


def _data(
    *,
    peerings: list[dict[str, Any]] | None = None,
    local_asn: int | None = LOCAL_ASN,
    node_selector: list[str] | None = None,
    advertisement_selector: list[str] | None = None,
    service_advertisement_selector: list[str] | None = None,
    # S107 is suppressed below: ruff flags any default whose name contains
    # "secret" as a possible hardcoded password. This is the *name* of an
    # in-cluster secret, which is precisely what the transform renders instead
    # of a password -- and test_no_secret_value_is_ever_rendered asserts that.
    auth_secret_name: str | None = "otternet-bgp-auth",  # noqa: S107
    pod_cidr_communities: list[str] | None = None,
    bgp_timers: dict[str, int] | None = None,
    service_name: str = "otternet-fabric-peering",
) -> dict[str, Any]:
    """A query response shaped like CrossplaneFabricPeeringQuery."""
    if peerings is None:
        peerings = [_peering("k8s-leaf1", LEAF1_ADDRESS), _peering("k8s-leaf2", LEAF2_ADDRESS)]
    if node_selector is None:
        node_selector = ["otternet.lab/bgp=true"]
    if advertisement_selector is None:
        advertisement_selector = ["otternet.lab/advertise=fabric"]
    if pod_cidr_communities is None:
        pod_cidr_communities = ["65401:110"]
    if bgp_timers is None:
        bgp_timers = {"connectRetrySeconds": 5, "holdTimeSeconds": 9, "keepAliveSeconds": 3}

    return {
        "target": {
            "edges": [
                {
                    "node": {
                        "id": "svc-1",
                        "name": {"value": service_name},
                        "status": {"value": "active"},
                        "communities": {"value": ["65401:110"]},
                        "advertisement_selector": {"value": service_advertisement_selector},
                        "cluster": {
                            "node": {
                                "id": "cluster-1",
                                "name": {"value": "otternet"},
                                "local_asn": {"value": local_asn},
                                "bgp_auth_secret_name": {"value": auth_secret_name},
                                "bgp_timers": {"value": bgp_timers},
                                "pod_cidr_communities": {"value": pod_cidr_communities},
                                "node_selector": {"value": node_selector},
                                "advertisement_selector": {"value": advertisement_selector},
                            }
                        },
                        "peerings": {"edges": peerings},
                    }
                }
            ]
        }
    }


def _render(**kwargs: Any) -> dict[str, Any]:
    """Render and parse back, so assertions read against the real document."""
    transform = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform)
    return yaml.safe_load(transform.transform(_data(**kwargs)))


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


def test_renders_the_xrd_apiversion_and_kind() -> None:
    """FR-041. The contract with the lab's composition starts here."""
    rendered = _render()

    assert rendered["apiVersion"] == "otternet.lab/v1alpha1"
    assert rendered["kind"] == "FabricPeering"
    assert rendered["metadata"]["name"] == "otternet"


def test_metadata_name_comes_from_the_cluster_not_the_service() -> None:
    """The XRD is cluster-scoped with one resource per cluster.

    Naming the resource after the service would let a service rename produce a
    second FabricPeering beside the deployed one rather than updating it, so
    renaming the service must not move the manifest's identity.
    """
    rendered = _render(service_name="something-else-entirely")

    assert rendered["metadata"]["name"] == "otternet"


def test_renders_every_field_the_composition_consumes() -> None:
    spec = _render()["spec"]

    assert spec["localASN"] == LOCAL_ASN
    assert spec["authSecretName"] == "otternet-bgp-auth"
    assert spec["podCIDRCommunities"] == ["65401:110"]
    assert spec["timers"] == {
        "connectRetrySeconds": 5,
        "holdTimeSeconds": 9,
        "keepAliveSeconds": 3,
    }
    assert len(spec["peers"]) == 2


# ---------------------------------------------------------------------------
# Selector parsing
# ---------------------------------------------------------------------------


def test_selector_becomes_a_label_map() -> None:
    """The storage shape is a workaround, not a preference.

    Selectors are stored as `key=value` strings because Infrahub 1.10.6 returns
    a 500 for a JSON attribute key containing a dot or a slash, and every
    Kubernetes label selector has both. The XRD wants a real map.
    """
    spec = _render()["spec"]

    assert spec["nodeSelector"] == {"otternet.lab/bgp": "true"}
    assert spec["advertisementSelector"] == {"otternet.lab/advertise": "fabric"}


def test_selector_value_may_contain_an_equals_sign() -> None:
    """Split on the FIRST `=` only -- a label value may legitimately have one."""
    spec = _render(node_selector=["otternet.lab/x=a=b"])["spec"]

    assert spec["nodeSelector"] == {"otternet.lab/x": "a=b"}


def test_selector_label_value_stays_a_string() -> None:
    """`true` is a label value, not a boolean.

    A Kubernetes label map is map[string]string; an unquoted `true` would come
    back as a bool and the API would reject it.
    """
    spec = _render()["spec"]

    assert spec["nodeSelector"]["otternet.lab/bgp"] == "true"
    assert isinstance(spec["nodeSelector"]["otternet.lab/bgp"], str)


def test_service_advertisement_selector_wins_over_the_cluster() -> None:
    """The service is the more specific statement of intent."""
    spec = _render(service_advertisement_selector=["otternet.lab/advertise=override"])["spec"]

    assert spec["advertisementSelector"] == {"otternet.lab/advertise": "override"}


# ---------------------------------------------------------------------------
# Peers
# ---------------------------------------------------------------------------


def test_peer_address_is_stripped_of_its_prefix_length() -> None:
    """A BGP neighbour is an address, not a prefix.

    `peer_address` resolves to an IpamIPAddress, whose value carries the mask.
    """
    peers = _render()["spec"]["peers"]

    assert [p["address"] for p in peers] == ["10.110.0.2", "10.110.0.3"]


def test_peers_are_ordered_deterministically() -> None:
    """SC-004. Asserting it from a reversed fixture makes the guarantee
    independent of the schema's own `order_by`, which a future edit could
    remove silently."""
    peers = _render(peerings=[_peering("k8s-leaf2", LEAF2_ADDRESS), _peering("k8s-leaf1", LEAF1_ADDRESS)])["spec"][
        "peers"
    ]

    assert [p["name"] for p in peers] == ["k8s-leaf1", "k8s-leaf2"]


def test_disabled_peering_is_omitted() -> None:
    """FR-016. A disabled session is not a peer."""
    peers = _render(
        peerings=[
            _peering("k8s-leaf1", LEAF1_ADDRESS),
            _peering("k8s-leaf2", LEAF2_ADDRESS, enabled=False),
        ]
    )["spec"]["peers"]

    assert [p["name"] for p in peers] == ["k8s-leaf1"]


def test_peer_carries_its_own_asn() -> None:
    peers = _render()["spec"]["peers"]

    assert {p["asn"] for p in peers} == {PEER_ASN}


# ---------------------------------------------------------------------------
# Omission and determinism
# ---------------------------------------------------------------------------


def test_unset_optional_fields_are_omitted_not_nulled() -> None:
    """FR-018. The XRD carries its own defaults; an explicit null overrides one."""
    spec = _render(auth_secret_name=None, pod_cidr_communities=[], bgp_timers={})["spec"]

    assert "authSecretName" not in spec
    assert "podCIDRCommunities" not in spec
    assert "timers" not in spec


def test_every_value_survives_a_round_trip_with_its_type_intact() -> None:
    """The dumper decides what needs quoting, so assert what it decided.

    Two values are ambiguous unquoted: `true` would come back a boolean, and
    a community like `65401:110` carries a colon, the one construct YAML
    parsers have historically read differently. Both are `map[string]string`
    and `[]string` in the XRD, so a coerced type is a rejected manifest.
    """
    transform = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform)
    output = transform.transform(_data())
    spec = yaml.safe_load(output)["spec"]

    assert isinstance(spec["nodeSelector"]["otternet.lab/bgp"], str)
    assert isinstance(spec["podCIDRCommunities"][0], str)
    assert spec["podCIDRCommunities"] == ["65401:110"]
    assert "'65401:110'" in output, "a colon-bearing scalar must be quoted for the Go parser"
    assert isinstance(spec["localASN"], int)
    assert isinstance(spec["peers"][0]["asn"], int)


def test_sequences_are_indented_under_their_parent_key() -> None:
    """Matches the hand-written 10-peering.yaml this artifact replaces, so a
    diff between the two reads as a field comparison rather than a reindent."""
    output = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform).transform(_data())

    assert "\n  peers:\n    - name: k8s-leaf1\n" in output


def test_rendering_is_byte_identical_for_an_unchanged_model() -> None:
    """SC-004 at the string level, not just the parsed level."""
    transform = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform)

    assert transform.transform(_data()) == transform.transform(_data())


def test_no_secret_value_is_ever_rendered() -> None:
    """SC-007. Only the name of the secret holding the password."""
    transform = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform)
    output = transform.transform(_data())

    assert "otternet-bgp-auth" in output
    for forbidden in ("password", "Otternet-Cilium", "cleartext"):
        assert forbidden not in output


# ---------------------------------------------------------------------------
# Failure behaviour -- US3
# ---------------------------------------------------------------------------


def test_missing_local_asn_raises_naming_the_cluster_and_field() -> None:
    """V-1. A session with no local AS cannot come up, so rendering one is
    worse than failing: the resource would apply cleanly and carry nothing."""
    transform = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform)

    with pytest.raises(ValueError, match="local_asn") as excinfo:
        transform.transform(_data(local_asn=None))

    assert "otternet" in str(excinfo.value)


def test_no_enabled_peerings_raises() -> None:
    """V-2. An empty `peers` list yields a resource that applies cleanly,
    reports healthy, and carries no routes."""
    transform = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform)

    with pytest.raises(ValueError, match="peering"):
        transform.transform(_data(peerings=[_peering("k8s-leaf1", LEAF1_ADDRESS, enabled=False)]))


def test_empty_peerings_raises() -> None:
    transform = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform)

    with pytest.raises(ValueError, match="peering"):
        transform.transform(_data(peerings=[]))


def test_missing_peer_address_raises_naming_the_peering() -> None:
    """V-3."""
    transform = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform)

    with pytest.raises(ValueError, match="peer_address") as excinfo:
        transform.transform(_data(peerings=[_peering("k8s-leaf1", None)]))

    assert "k8s-leaf1" in str(excinfo.value)


def test_malformed_selector_raises_naming_the_entry() -> None:
    """V-4. A selector with no `=` cannot become a label."""
    transform = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform)

    with pytest.raises(ValueError, match=re.escape("otternet.lab/bgp")) as excinfo:
        transform.transform(_data(node_selector=["otternet.lab/bgp"]))

    assert "=" in str(excinfo.value)


def test_missing_target_raises() -> None:
    """A name that matches nothing is a caller error, not an empty manifest."""
    transform = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform)

    with pytest.raises(ValueError, match="ServiceFabricPeering"):
        transform.transform({"target": {"edges": []}})


def test_provisioning_status_still_renders() -> None:
    """R10. Whether to apply a manifest is an operator's decision.

    Refusing to render an un-activated service would make the artifact useless
    for review before activation.
    """
    data = _data()
    data["target"]["edges"][0]["node"]["status"]["value"] = "provisioning"
    transform = CrossplaneFabricPeeringTransform.__new__(CrossplaneFabricPeeringTransform)

    assert yaml.safe_load(transform.transform(data))["kind"] == "FabricPeering"

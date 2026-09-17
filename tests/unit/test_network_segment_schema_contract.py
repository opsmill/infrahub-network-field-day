"""Contract tests for the network segment service.

The generic service-layer contracts in `test_service_layer_schema_contract.py`
already cover this kind -- it inherits `ServiceGeneric` and `GeneratorTarget`
like every other, and none of its relationships cascades. What follows is what
is specific to a segment, and most of it is one decision.

**A segment ALLOCATES; it does not select.** `ServiceL3vpn` and its WAN siblings
name technical objects that already exist, which is why a generator beneath them
would have nothing to create. A segment instead states a size and a tenant and
lets the generator take the next free subnet and VLAN id. That is the difference
between a service and a filled-in form, and `vlan_id` being optional is where it
lives -- a request that had to name its own VLAN id would be a work order, and
the requester is exactly the person who does not know which ids are free.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parents[2]
SEGMENT_SCHEMA = REPO_ROOT / "schemas/service/network_services.yml"
POOLS = REPO_ROOT / "objects/21_nfd41_pools.yml"

SUBNET_POOL = "NFD41-Segment-Subnet-Pool"
VLAN_POOL = "NFD41-Segment-VLAN-Pool"
SEGMENT_SUPERNET = "10.230.0.0/16"

# Written by the generator, never by a requester. Each records one of the three
# objects a segment actually is.
MATERIALISED = ("subnet", "vlan", "svi")


def _segment() -> dict[str, Any]:
    document = yaml.safe_load(SEGMENT_SCHEMA.read_text(encoding="utf-8"))
    for node in document.get("nodes", []):
        if node["name"] == "NetworkSegment":
            return node
    pytest.fail("schemas/service/network_services.yml declares no NetworkSegment")


def _attributes() -> dict[str, dict[str, Any]]:
    return {a["name"]: a for a in _segment().get("attributes", [])}


def _relationships() -> dict[str, dict[str, Any]]:
    return {r["name"]: r for r in _segment().get("relationships", [])}


def _pool_documents() -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(POOLS.read_text(encoding="utf-8")) if d]


def _rows(kind: str) -> list[dict[str, Any]]:
    for document in _pool_documents():
        spec = document.get("spec", {})
        if spec.get("kind") == kind:
            return spec.get("data", [])
    return []


# ---------------------------------------------------------------------------
# The decision this kind exists to make
# ---------------------------------------------------------------------------


def test_the_vlan_id_is_optional_so_a_request_need_not_know_one() -> None:
    """Empty means "allocate one", which is the normal case.

    Making it mandatory would turn the service into a work order and hand the
    hardest question -- which ids are free -- to the person least able to answer
    it.
    """
    assert _attributes()["vlan_id"].get("optional") is True


def test_the_vlan_id_refuses_the_ids_eos_reserves() -> None:
    """1 and 4094 are reserved on EOS. Excluded in the model rather than left
    for AVD to render a VLAN the switch will not accept."""
    parameters = _attributes()["vlan_id"]["parameters"]
    assert parameters["min_value"] == 1
    assert parameters["max_value"] == 4094
    assert parameters["excluded_values"] == "1,4094"


def test_a_size_is_always_stated_even_when_a_subnet_is_not() -> None:
    """`prefix_length` carries a default rather than being optional: the
    generator always needs a size to allocate, and /24 is what every
    hand-written segment in this lab uses."""
    prefix_length = _attributes()["prefix_length"]
    assert prefix_length.get("optional") is not True
    assert prefix_length["default_value"] == 24


# ---------------------------------------------------------------------------
# Intent versus outcome
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["tenant", "vrf", "fabric"])
def test_the_intent_relationships_are_mandatory(name: str) -> None:
    """A segment with no tenant, no routing domain or no fabric is not an
    under-specified request; it is not a request."""
    relationship = _relationships()[name]
    assert relationship["cardinality"] == "one"
    assert relationship.get("optional") is False


def test_the_vrf_is_named_rather_than_created() -> None:
    """A segment joins a routing domain that already exists and is shared.
    Creating one per segment would give every segment its own routing table,
    which is the opposite of what a tenant network is for.
    """
    assert _relationships()["vrf"]["peer"] == "IpamVRF"
    assert _relationships()["vrf"].get("on_delete") == "no-action"


@pytest.mark.parametrize("name", MATERIALISED)
def test_the_materialised_objects_are_optional_and_never_cascade(name: str) -> None:
    """They are empty until a generator runs, and deleting the service must not
    take a subnet other things route to with it."""
    relationship = _relationships()[name]
    assert relationship.get("optional") is True
    assert relationship.get("on_delete") == "no-action"


def test_the_segment_is_scoped_by_avd_tag_and_not_by_rack() -> None:
    """The measured correction to this kind's first draft.

    AVD renders an SVI onto a device only where the SVI's tags intersect that
    device's node-group filter, and in this fabric those filters are AvdTags:
    `{"tags": ["k8s"]}` on K8S_LEAFS. `EvpnSvi.rack_tags` exists and looks like
    the scoping mechanism, but it contributes the rack's NAME -- `K8S_LEAFS` --
    which matches no filter.

    Measured on a branch: an SVI with no tags rendered on zero switches, and the
    same SVI tagged `k8s` rendered on exactly the two K8S leaves. A `racks`
    relationship would have produced the first result while reading like the
    second.
    """
    avd_tags = _relationships()["avd_tags"]
    assert avd_tags["peer"] == "AvdTag"
    assert avd_tags["cardinality"] == "many"
    assert "racks" not in _relationships()


def test_the_scope_is_mandatory_because_empty_means_nowhere() -> None:
    """There is no filter in this fabric accepting every leaf.

    So an empty list is not "the whole fabric"; it is a segment that renders on
    nothing, silently, with a configuration that simply lacks the interface and
    no error anywhere. Mandatory turns that into a rejected request.
    """
    assert _relationships()["avd_tags"].get("optional") is False


# ---------------------------------------------------------------------------
# The pools the allocation depends on
# ---------------------------------------------------------------------------


def test_both_pools_are_seeded() -> None:
    """Without them the kind loads and can allocate nothing."""
    assert any(row["name"] == SUBNET_POOL for row in _rows("CoreIPPrefixPool"))
    assert any(row["name"] == VLAN_POOL for row in _rows("CoreNumberPool"))


def test_the_subnet_pool_has_a_declared_supernet() -> None:
    """A CoreIPPrefixPool's `resources` must name prefixes that already exist.

    Omitting the declaration fails the object load with "Unable to find the node
    10.230.0.0/16 / BuiltinIPPrefix in the database", which says nothing about
    pools and sends you looking in the wrong file.
    """
    pool = next(row for row in _rows("CoreIPPrefixPool") if row["name"] == SUBNET_POOL)
    assert pool["resources"] == [SEGMENT_SUPERNET]
    assert any(row.get("prefix") == SEGMENT_SUPERNET for row in _rows("IpamPrefix"))


def test_the_subnet_pool_declares_what_it_allocates() -> None:
    """`default_prefix_type` is what a pool creates when it allocates.

    Omitting it costs nothing at load time and fails at allocation with
    "A prefix_type or a default_value type must be provided" -- which names the
    pool and not the file declaring it. Every other prefix pool here sets it.
    """
    pool = next(row for row in _rows("CoreIPPrefixPool") if row["name"] == SUBNET_POOL)
    assert pool["default_prefix_type"] == "IpamPrefix"
    assert pool["default_prefix_length"] == 24


def test_every_prefix_pool_declares_what_it_allocates() -> None:
    """The same trap for the fabric pools beside it, so a new one cannot omit it."""
    for pool in _rows("CoreIPPrefixPool"):
        assert pool.get("default_prefix_type"), f"{pool['name']} allocates an unnamed kind"


def test_the_segment_pools_do_not_collide_with_the_lab() -> None:
    """The lab's own VLANs are 110, 210, 310 and 320, and its addressing runs
    10.41, 10.50-10.60, 10.70, 10.110-10.112, 10.210-10.220 and 10.250."""
    vlan_pool = next(row for row in _rows("CoreNumberPool") if row["name"] == VLAN_POOL)
    assert vlan_pool["start_range"] > 320
    assert vlan_pool["end_range"] < 4094
    assert SEGMENT_SUPERNET.startswith("10.230.")

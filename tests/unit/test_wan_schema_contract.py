"""Contract tests for the provider, WAN and branch technical layer.

Everything outside the fabric that ``../lab/wan/tenants.yml`` holds today: the
ISP, its two PE roles, the internet autonomous system, each tenant site's
attachment circuit and how it attaches, and the branch office's private
circuit.

The lab's own file is emphatic about two distinctions this layer has to keep,
and both are asserted here: a tenant is not a site, and the branch office is
not a customer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).parents[2]

WAN_SCHEMA = "schemas/wan/wan.yml"
TENANCY_EXTENSIONS = "schemas/tenancy_extensions.yml"
CIRCUIT_EXTENSIONS = "schemas/circuit_extensions.yml"
DCIM_EXTENSIONS = "schemas/dcim_extensions.yml"

WAN_NODE_NAMES = ("Site", "InternetPeering")


def _load_yaml(path: str) -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def _nodes(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return list(schema.get("nodes", []))


def _node(schema: dict[str, Any], namespace: str, name: str) -> dict[str, Any]:
    for node in _nodes(schema):
        if node.get("namespace") == namespace and node.get("name") == name:
            return node
    raise AssertionError(f"{namespace}{name} node not found")


def _extension_nodes(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return list(schema.get("extensions", {}).get("nodes", []))


def _extension_node(schema: dict[str, Any], kind: str) -> dict[str, Any]:
    for node in _extension_nodes(schema):
        if node.get("kind") == kind:
            return node
    raise AssertionError(f"{kind} extension not found")


def _attributes(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {attr["name"]: attr for attr in node.get("attributes", [])}


def _relationships(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rel["name"]: rel for rel in node.get("relationships", [])}


def _choice_names(attribute: dict[str, Any]) -> set[str]:
    return {choice["name"] for choice in attribute.get("choices", [])}


def _all_attribute_kinds(schema: dict[str, Any]) -> set[str]:
    kinds: set[str] = set()
    for section in ("generics", "nodes"):
        for entry in schema.get(section) or []:
            kinds.update(attr.get("kind", "") for attr in entry.get("attributes") or [])
    return kinds


# ---------------------------------------------------------------------------
# WanTenant -- the unit of isolation on the provider edge
# ---------------------------------------------------------------------------


def test_every_wan_node_exists() -> None:
    schema = _load_yaml(WAN_SCHEMA)

    for name in WAN_NODE_NAMES:
        assert _node(schema, "Wan", name)


def test_there_is_no_wan_specific_tenant_kind() -> None:
    """A tenant crosses every domain, so it cannot be a per-domain kind.

    `acme` is one organization with a VRF on the provider edge, an isolated
    subnet in the fabric, and applications in the cluster. An earlier draft had
    a `WanTenant` alongside the adopted OrganizationTenant, which meant two
    objects for one tenant and two places for its identity to drift.
    """
    declared = {f"{n.get('namespace', '')}{n.get('name', '')}" for n in _nodes(_load_yaml(WAN_SCHEMA))}

    assert "WanTenant" not in declared
    assert declared == {"WanSite", "WanInternetPeering"}


def test_site_hangs_off_the_one_adopted_tenant() -> None:
    site = _node(_load_yaml(WAN_SCHEMA), "Wan", "Site")
    tenant = _relationships(site)["tenant"]

    assert tenant["peer"] == "OrganizationTenant"
    assert tenant["kind"] == "Parent"
    assert tenant["identifier"] == "tenant__sites"


def test_tenancy_extension_carries_the_id_and_classification() -> None:
    """Trust, not scope. The branch office is structurally a tenant -- site,
    circuit, LAN -- but deliberately not a paying customer."""
    tenant = _extension_node(_load_yaml(TENANCY_EXTENSIONS), "OrganizationTenant")
    attributes = _attributes(tenant)

    assert attributes["tenant_id"]["kind"] == "Number"
    assert attributes["tenant_id"]["optional"] is True
    classification = attributes["classification"]
    assert {c["name"] for c in classification["choices"]} == {"customer", "internal"}
    assert classification["default_value"] == "customer"


def test_tenant_scope_is_not_a_stored_field() -> None:
    """Which domains a tenant reaches is derived from its services.

    A ServiceL3vpn names it for the provider edge, a ServiceTenantCloud for the
    fabric, a ServiceFabricApp owns it for the cluster. A stored `scope` would
    have to be kept in step by hand, and it would have to be a relationship
    into the service layer -- which the technical layer may not hold.
    """
    tenant = _extension_node(_load_yaml(TENANCY_EXTENSIONS), "OrganizationTenant")
    attributes = set(_attributes(tenant))

    assert "scope" not in attributes
    peers = {rel.get("peer", "") for rel in tenant.get("relationships") or []}
    assert not {peer for peer in peers if peer.startswith("Service")}


def test_no_vrf_fields_are_restated_on_the_tenant() -> None:
    """The provider-edge VRF is ServiceL3vpn.vrf; the fabric VRF is
    ServiceTenantCloud.vrf. An IpamVRF carries its own name and route targets,
    so there is nothing left for the tenant to hold."""
    tenant = _extension_node(_load_yaml(TENANCY_EXTENSIONS), "OrganizationTenant")
    attributes = set(_attributes(tenant))

    assert not {"vrf_name", "vrf_table_id", "dc_vrf"} & attributes


# ---------------------------------------------------------------------------
# WanSite
# ---------------------------------------------------------------------------


def test_site_attachment_kind_covers_both_lab_handoffs() -> None:
    """FR-028 / US6 acceptance scenario 3.

    acme has two sites attached two different ways: hq speaks eBGP, dr runs no
    routing protocol at all. The PE normalises both into the same L3VPN.
    """
    site = _node(_load_yaml(WAN_SCHEMA), "Wan", "Site")
    attachment = _attributes(site)["attachment_kind"]

    assert _choice_names(attachment) == {"bgp", "static"}
    assert attachment["default_value"] == "bgp"


def test_site_is_unique_per_tenant() -> None:
    """FR-074. Two tenants may each have a site called ``hq``."""
    site = _node(_load_yaml(WAN_SCHEMA), "Wan", "Site")

    assert site["uniqueness_constraints"] == [["tenant", "name__value"]]
    assert site["human_friendly_id"] == ["tenant__name__value", "name__value"]


def test_site_asn_is_optional_because_a_static_site_has_none() -> None:
    """Required exactly when attachment_kind is bgp -- a conditional the schema
    cannot express, so it is optional here and enforced by a check."""
    site = _node(_load_yaml(WAN_SCHEMA), "Wan", "Site")

    assert _attributes(site)["site_asn"]["optional"] is True


def test_site_lan_is_an_ipam_prefix() -> None:
    site = _node(_load_yaml(WAN_SCHEMA), "Wan", "Site")
    lan = _relationships(site)["lan_prefix"]

    assert lan["peer"] == "IpamPrefix"
    assert lan["cardinality"] == "one"
    assert lan["optional"] is False


# ---------------------------------------------------------------------------
# WanCircuit
# ---------------------------------------------------------------------------


def test_site_uses_the_marketplace_circuit_not_a_wan_specific_one() -> None:
    """The single most important adoption assertion in this file.

    An earlier locally-authored WanCircuit carried four flat relationships --
    provider interface, provider address, customer interface, customer address
    -- to model a two-ended circuit. infrahub/circuit already does this better:
    DcimCircuit owns two DcimCircuitEndpoint objects, each with a `side`,
    unique on [circuit, side], and each inheriting DcimEndpoint so it joins an
    interface through the repository's existing NetworkLink connector.
    """
    site = _node(_load_yaml(WAN_SCHEMA), "Wan", "Site")
    circuit = _relationships(site)["circuit"]

    assert circuit["peer"] == "DcimCircuit"
    assert circuit["cardinality"] == "one"


def test_no_wan_specific_circuit_kind_is_declared() -> None:
    """The regression this test exists to prevent."""
    declared = {f"{n.get('namespace', '')}{n.get('name', '')}" for n in _nodes(_load_yaml(WAN_SCHEMA))}

    assert "WanCircuit" not in declared
    assert declared == {"WanSite", "WanInternetPeering"}


def test_adopted_circuit_schema_models_two_sides() -> None:
    """The contract with upstream: a re-download must keep the side split."""
    schema = _load_yaml("schemas/circuit/circuit.yml")
    endpoint = _node(schema, "Dcim", "CircuitEndpoint")

    assert "side" in _attributes(endpoint)
    assert ["circuit", "side__value"] in (endpoint.get("uniqueness_constraints") or [])
    assert "DcimEndpoint" in (endpoint.get("inherit_from") or [])


def test_circuit_endpoint_names_the_interface_it_terminates_on() -> None:
    """Cycle 020: the change that makes the WAN's addressing queryable.

    Without it, objects/33_otternet_wan.yml can only record a circuit end as
    `name: isp-pe1-eth2` plus an address inside a description sentence -- an
    interface as a string and a CIDR as prose, which is what cycle 010's
    assumption 4 and SC-008 forbid.

    One relationship is enough because InterfaceLayer3 already carries
    `ip_addresses`, so this completes circuit -> endpoint -> interface ->
    address in a single step.
    """
    endpoint = _extension_node(_load_yaml(CIRCUIT_EXTENSIONS), "DcimCircuitEndpoint")
    interface = _relationships(endpoint)["interface"]

    assert interface["peer"] == "DcimInterface"
    assert interface["cardinality"] == "one"
    assert interface["optional"] is True
    assert interface["identifier"] == "circuit_endpoint__interface"


def test_the_interface_peer_is_the_generic_not_a_concrete_kind() -> None:
    """InterfacePhysical would work today and fail on the first sub-interface.

    Both InterfacePhysical and InterfaceVirtual inherit DcimInterface, so
    peering with the generic accepts either.
    """
    endpoint = _extension_node(_load_yaml(CIRCUIT_EXTENSIONS), "DcimCircuitEndpoint")

    assert _relationships(endpoint)["interface"]["peer"] not in {"InterfacePhysical", "InterfaceVirtual"}


def test_the_adopted_circuit_file_declares_no_interface_relationship() -> None:
    """SC-009: the addition lands in the extension, never in the adopted file.

    infrahub/circuit is kept byte-identical to the published version so a
    re-download diffs cleanly. This is the assertion that catches someone
    editing it directly.
    """
    endpoint = _node(_load_yaml("schemas/circuit/circuit.yml"), "Dcim", "CircuitEndpoint")

    assert "interface" not in _relationships(endpoint)


def test_a_device_can_name_its_router_id() -> None:
    """Cycle 020: `bgp router-id` needs a source that is not guesswork.

    Three of the six routers the WAN renders take their router ID from a
    loopback; the customer edges use their LAN address and internet-rtr uses
    its peering address. Deriving it from an interface role would therefore be
    wrong for half the fleet, and silently -- a router-id that is merely
    different still forms a session.

    Kept distinct from `loopback_ip`, which would record a falsehood for the
    three that are not loopbacks.
    """
    schema = _load_yaml(DCIM_EXTENSIONS)
    router_id = _relationships(_extension_node(schema, "DcimDevice"))["router_id"]

    assert router_id["peer"] == "IpamIPAddress"
    assert router_id["cardinality"] == "one"
    assert router_id["optional"] is True
    assert router_id["identifier"] == "device__router_id"

    # Since cycle 027 the two live on different kinds -- `loopback_ip` is
    # fabric-only -- which makes the point more strongly than the original
    # inequality did: a router cannot even reach the loopback relationship.
    fabric = _relationships(_extension_node(schema, "DcimFabricSwitch"))
    assert router_id["identifier"] != fabric["loopback_ip"]["identifier"]
    assert "loopback_ip" not in _relationships(_extension_node(schema, "DcimDevice"))


def test_the_loopback_interface_role_was_already_modelled() -> None:
    """FR-020 was withdrawn during Phase 0 research, and this records why.

    The specification asked for a `loopback` role choice, reading the generic
    in schemas/base/dcim.yml. That is not the effective list:
    dcim_extensions.yml re-declares DcimInterface.role and already carries both
    loopback choices. In this repository the base file is where a kind starts
    and the extension is what it actually is.
    """
    interface = _extension_node(_load_yaml(DCIM_EXTENSIONS), "DcimInterface")
    roles = _choice_names(_attributes(interface)["role"])

    assert {"loopback", "vtep_loopback"} <= roles


def test_site_reuses_existing_routing_kinds_for_both_handoffs() -> None:
    """FR-010: no parallel BGP-session or static-route model.

    A bgp site uses RoutingBGPNeighbor, a static site uses
    RoutingVrfStaticRoute. Both already exist in this repository.
    """
    site = _node(_load_yaml(WAN_SCHEMA), "Wan", "Site")
    relationships = _relationships(site)

    assert relationships["bgp_sessions"]["peer"] == "RoutingBGPNeighbor"
    assert relationships["bgp_sessions"]["cardinality"] == "many"
    assert relationships["static_routes"]["peer"] == "RoutingVrfStaticRoute"


def test_site_holds_both_ends_of_its_bgp_session() -> None:
    """Cycle 020: a session between two devices is two objects, not one.

    RoutingBGPNeighbor is device-scoped and unique on
    [device, peer_address__value], so a PE-to-CE attachment produces one object
    on the PE and one on the CE. The original cardinality-one `bgp_session`
    could hold only half of that.

    Optional as well as many: acme's DR site is statically attached and runs no
    protocol at all, so zero sessions is valid rather than missing.
    """
    site = _node(_load_yaml(WAN_SCHEMA), "Wan", "Site")
    sessions = _relationships(site)["bgp_sessions"]

    assert sessions["cardinality"] == "many"
    assert sessions["optional"] is True
    assert sessions["identifier"] == "wan_site__bgp_sessions"


def test_the_old_single_bgp_session_is_tombstoned_not_deleted() -> None:
    """The tombstone is load-bearing; deleting it would be a silent regression.

    A schema load is an upsert. A relationship merely removed from the YAML is
    left alone on the server, and `infrahubctl schema check` reports the rename
    as a pure addition with an empty `removed` block -- so the old
    cardinality-one relationship survives with no warning anywhere. Only
    `state: absent` actually removes it.

    This test exists so that a future tidy-up of the tombstone has to be
    deliberate. It may be removed once the instance is rebuilt from empty.
    """
    site = _node(_load_yaml(WAN_SCHEMA), "Wan", "Site")
    relationships = _relationships(site)

    assert "bgp_session" in relationships, "tombstone removed; the old relationship will linger on the server"
    assert relationships["bgp_session"]["state"] == "absent"
    assert relationships["bgp_session"]["cardinality"] == "one"


def test_internet_peering_holds_both_ends_of_the_transit_session() -> None:
    """The transit link is one wire and two objects.

    isp-pe2 holds `neighbor 10.52.0.2 remote-as 64500` and internet-rtr holds
    `neighbor 10.52.0.1 remote-as 65500`. Cardinality one here would make this
    the only place in the model where half a session is recorded.
    """
    peering = _node(_load_yaml(WAN_SCHEMA), "Wan", "InternetPeering")
    sessions = _relationships(peering)["bgp_sessions"]

    assert sessions["peer"] == "RoutingBGPNeighbor"
    assert sessions["cardinality"] == "many"
    assert sessions["optional"] is True
    assert sessions["identifier"] == "internet_peering__bgp_sessions"


def test_internet_peering_names_two_distinct_providers() -> None:
    """The ISP on one side, AS 64500 on the other."""
    peering = _node(_load_yaml(WAN_SCHEMA), "Wan", "InternetPeering")
    relationships = _relationships(peering)

    assert relationships["provider"]["peer"] == "OrganizationProvider"
    assert relationships["internet_provider"]["peer"] == "OrganizationProvider"
    assert relationships["provider"]["identifier"] != relationships["internet_provider"]["identifier"]


def test_internet_peering_runs_over_a_marketplace_circuit() -> None:
    """The two physical sides live on the circuit's endpoints, not here.

    An earlier draft carried provider_interface and peer_interface directly.
    DcimCircuit already models a two-ended link, so the peering references one
    rather than restating both ends.
    """
    peering = _node(_load_yaml(WAN_SCHEMA), "Wan", "InternetPeering")

    assert _relationships(peering)["circuit"]["peer"] == "DcimCircuit"


def test_internet_peering_carries_the_customer_aggregate() -> None:
    """The prefix the ISP announces outward on its tenants' behalf."""
    peering = _node(_load_yaml(WAN_SCHEMA), "Wan", "InternetPeering")

    assert _relationships(peering)["customer_aggregate"]["peer"] == "IpamPrefix"


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------


def test_no_inline_network_attributes_are_declared() -> None:
    """SC-008 for this domain."""
    assert not {"IPNetwork", "IPHost"} & _all_attribute_kinds(_load_yaml(WAN_SCHEMA))


def test_no_wan_node_references_a_service_kind() -> None:
    """FR-080 for this file specifically."""
    peers = {rel.get("peer", "") for node in _nodes(_load_yaml(WAN_SCHEMA)) for rel in node.get("relationships") or []}

    assert not {peer for peer in peers if peer.startswith("Service")}


def test_no_site_to_site_relationship_exists() -> None:
    """GI-12: sites reach each other by sharing a VPN, not by a direct link.

    The lab: hq and dr "reach each other because they share a VRF, not because
    anything was leaked between them". A site-to-site relationship here would
    invite modelling that reachability as an edge, which is the confusion the
    tenant/site split exists to prevent.
    """
    site = _node(_load_yaml(WAN_SCHEMA), "Wan", "Site")
    peers = {rel.get("peer") for rel in site.get("relationships") or []}

    assert "WanSite" not in peers


def test_every_wan_node_declares_display_properties() -> None:
    schema = _load_yaml(WAN_SCHEMA)

    for name in WAN_NODE_NAMES:
        node = _node(schema, "Wan", name)
        assert node["human_friendly_id"], f"{name} needs a human_friendly_id"
        assert node["display_label"], f"{name} needs a display_label"
        assert node["icon"], f"{name} needs an icon"

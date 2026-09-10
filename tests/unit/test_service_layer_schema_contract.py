"""Contract tests for the service layer of the NFD41 lab schema feature.

The service layer is the abstraction that separates ordered intent from device
fact. These tests assert the functional requirements in
``specs/010-lab-service-layer-model/spec.md`` against the YAML, including the
one requirement no server-side schema check can verify: that the dependency
between the two layers runs one way only (FR-080, SC-009).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parents[2]

SERVICE_SCHEMA = "schemas/service/service.yml"

# Every schema file that belongs to the technical layer. None of these may
# reference a Service* kind, or the technical layer stops being loadable on its
# own -- see test_no_technical_schema_references_a_service_kind.
TECHNICAL_SCHEMA_FILES = [
    "schemas/cluster/cluster.yml",
    "schemas/cluster/kubernetes.yml",
    "schemas/security/security.yml",
    "schemas/security_extensions.yml",
    "schemas/circuit/circuit.yml",
    "schemas/tenancy/tenancy.yml",
    "schemas/wan/wan.yml",
]

EXPECTED_STATUS_CHOICES = {
    "provisioning",
    "active",
    "error",
    "decommissioning",
    "decommissioned",
}


def _load_yaml(path: str) -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def _generics(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return list(schema.get("generics", []))


def _nodes(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return list(schema.get("nodes", []))


def _extension_nodes(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return list(schema.get("extensions", {}).get("nodes", []))


def _generic(schema: dict[str, Any], namespace: str, name: str) -> dict[str, Any]:
    for generic in _generics(schema):
        if generic.get("namespace") == namespace and generic.get("name") == name:
            return generic
    raise AssertionError(f"{namespace}{name} generic not found")


def _node(schema: dict[str, Any], namespace: str, name: str) -> dict[str, Any]:
    for node in _nodes(schema):
        if node.get("namespace") == namespace and node.get("name") == name:
            return node
    raise AssertionError(f"{namespace}{name} node not found")


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


def _iter_relationship_peers(schema: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Yield (container_kind, relationship_name, peer) for every relationship.

    Covers generics, nodes and extension blocks, so a Service peer cannot hide
    in any of the three.
    """
    declared = [
        (f"{entry.get('namespace', '')}{entry.get('name', '')}", entry)
        for section in ("generics", "nodes")
        for entry in schema.get(section) or []
    ]
    extended = [(entry.get("kind", ""), entry) for entry in _extension_nodes(schema)]

    return [
        (kind, rel.get("name", ""), rel.get("peer", ""))
        for kind, entry in declared + extended
        for rel in entry.get("relationships") or []
    ]


# ---------------------------------------------------------------------------
# US1 -- the ServiceGeneric abstraction
# ---------------------------------------------------------------------------


def test_service_generic_is_a_generic_not_a_node() -> None:
    """Concrete kinds inherit it; it must not be instantiable itself."""
    schema = _load_yaml(SERVICE_SCHEMA)

    assert _generic(schema, "Service", "Generic")
    with pytest.raises(AssertionError):
        _node(schema, "Service", "Generic")


def test_service_generic_name_is_unique_text() -> None:
    service = _generic(_load_yaml(SERVICE_SCHEMA), "Service", "Generic")
    name = _attributes(service)["name"]

    assert name["kind"] == "Text"
    assert name["unique"] is True


def test_service_generic_name_is_branch_aware() -> None:
    """Deliberate divergence from opsmill/infrahub-demo-dc.

    demo-dc marks ServiceGeneric.name ``branch: agnostic``. A branch-agnostic
    attribute is global, so a change on a branch takes effect everywhere
    immediately -- which would bypass the proposed-change review AGENTS.md
    requires of every service workflow. Leaving it branch-aware keeps ordering
    a service and reviewing it the same operation.
    """
    service = _generic(_load_yaml(SERVICE_SCHEMA), "Service", "Generic")
    name = _attributes(service)["name"]

    assert name.get("branch") != "agnostic"


def test_service_generic_status_choices_and_default() -> None:
    """FR-020: a pre-deployment, an active and a decommissioning state at least.

    ``error`` is present so a service whose generator ran and failed is
    distinguishable from one that has not been materialized yet -- the edge
    case spec.md raises.
    """
    service = _generic(_load_yaml(SERVICE_SCHEMA), "Service", "Generic")
    status = _attributes(service)["status"]

    assert status["kind"] == "Dropdown"
    assert _choice_names(status) == EXPECTED_STATUS_CHOICES
    assert status["default_value"] == "provisioning"


def test_service_generic_owner_is_mandatory_and_singular() -> None:
    """FR-040. OrganizationCustomer exists so this peer is instantiable."""
    service = _generic(_load_yaml(SERVICE_SCHEMA), "Service", "Generic")
    owner = _relationships(service)["owner"]

    assert owner["peer"] == "OrganizationGeneric"
    assert owner["cardinality"] == "one"
    assert owner["optional"] is False
    assert owner["on_delete"] == "no-action"


def test_service_generic_constrains_name_uniqueness() -> None:
    service = _generic(_load_yaml(SERVICE_SCHEMA), "Service", "Generic")

    assert service["uniqueness_constraints"] == [["name__value"]]


def test_service_generic_declares_display_properties() -> None:
    service = _generic(_load_yaml(SERVICE_SCHEMA), "Service", "Generic")

    assert service["human_friendly_id"] == ["name__value"]
    assert service["display_label"]
    assert service["order_by"]


# ---------------------------------------------------------------------------
# US1 -- the binding generics and the single DCIM coupling
# ---------------------------------------------------------------------------


def test_binding_generics_exist_with_expected_identifiers() -> None:
    schema = _load_yaml(SERVICE_SCHEMA)

    device_binding = _generic(schema, "Service", "GenericDevice")
    interface_binding = _generic(schema, "Service", "GenericInterface")

    assert _relationships(device_binding)["devices"]["identifier"] == "device_services"
    assert _relationships(interface_binding)["interfaces"]["identifier"] == "interface_services"


def test_binding_generics_are_hidden_from_the_menu() -> None:
    schema = _load_yaml(SERVICE_SCHEMA)

    for name in ("Generic", "GenericDevice", "GenericInterface"):
        assert _generic(schema, "Service", name)["include_in_menu"] is False


def test_dcim_back_references_are_declared_via_extensions() -> None:
    """FR-052 and research.md R6.

    These must be an ``extensions:`` block in the service file, never an edit
    to schemas/base/dcim.yml -- adding a Service peer to the base schema would
    make the technical layer depend on the service layer and break SC-009.
    """
    schema = _load_yaml(SERVICE_SCHEMA)

    device = _extension_node(schema, "DcimGenericDevice")
    interface = _extension_node(schema, "DcimInterface")

    device_rel = _relationships(device)["device_services"]
    interface_rel = _relationships(interface)["interface_services"]

    for rel in (device_rel, interface_rel):
        assert rel["peer"] == "ServiceGeneric"
        assert rel["cardinality"] == "many"
        assert rel["optional"] is True
        assert rel["on_delete"] == "no-action"

    assert device_rel["identifier"] == "device_services"
    assert interface_rel["identifier"] == "interface_services"


def test_base_dcim_schema_is_not_modified_to_reference_services() -> None:
    """The other half of FR-052: prove the base schema stayed clean."""
    peers = {peer for _, _, peer in _iter_relationship_peers(_load_yaml("schemas/base/dcim.yml"))}

    assert not {peer for peer in peers if peer.startswith("Service")}


# ---------------------------------------------------------------------------
# FR-080 / SC-009 -- the layering invariant
# ---------------------------------------------------------------------------


def test_no_technical_schema_references_a_service_kind() -> None:
    """FR-080: the technical layer must be usable with the service layer absent.

    This is the only enforcement of the layering direction. ``infrahubctl
    schema check`` will happily validate a technical file that peers a service
    kind -- it resolves fine when both are loaded together. The breakage only
    appears when someone tries to load the technical layer on its own, which
    is what SC-009 promises they can do.

    Tolerates files that do not exist yet so the test stays valid while the
    later user stories are still being implemented.
    """
    offenders: list[str] = []

    for path in TECHNICAL_SCHEMA_FILES:
        if not (REPO_ROOT / path).exists():
            continue
        for kind, rel_name, peer in _iter_relationship_peers(_load_yaml(path)):
            if peer.startswith("Service"):
                offenders.append(f"{path}: {kind}.{rel_name} -> {peer}")

    assert not offenders, "technical schemas must not reference service kinds:\n" + "\n".join(offenders)


def test_only_the_service_schema_couples_dcim_to_the_service_layer() -> None:
    """Exactly one file may hold a ``peer: ServiceGeneric`` relationship."""
    coupling_files = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "schemas").rglob("*.yml")
        if "peer: ServiceGeneric" in path.read_text(encoding="utf-8")
    )

    assert coupling_files == [SERVICE_SCHEMA]


# ---------------------------------------------------------------------------
# FR-053 / FR-081 / FR-083 -- inheritance and delete behaviour across every
# concrete service kind. These run over whichever service files exist, so they
# tighten as US3, US5 and US7 land.
# ---------------------------------------------------------------------------


def _existing_service_schemas() -> list[str]:
    return [path.relative_to(REPO_ROOT).as_posix() for path in sorted((REPO_ROOT / "schemas/service").glob("*.yml"))]


def _concrete_service_nodes() -> list[tuple[str, dict[str, Any]]]:
    """Every concrete node declared in a service schema file."""
    return [(path, node) for path in _existing_service_schemas() for node in _nodes(_load_yaml(path))]


def test_every_concrete_service_kind_is_a_generator_target() -> None:
    """FR-081: a generator must be able to sit underneath each service kind.

    GeneratorTarget supplies the ``checksum`` attribute the project's
    idempotence rules operate on. Without it a generator can still target the
    node, but every run does full work and has no field to compare against.
    """
    for path, node in _concrete_service_nodes():
        kind = f"{node['namespace']}{node['name']}"
        inherits = node.get("inherit_from", [])
        assert "ServiceGeneric" in inherits, f"{kind} in {path} must inherit ServiceGeneric"
        assert "GeneratorTarget" in inherits, f"{kind} in {path} must inherit GeneratorTarget"


def test_no_service_relationship_cascades_into_infrastructure() -> None:
    """FR-053: deleting a service must never delete a device or a prefix.

    A service is a statement of intent about technical objects it references
    but does not own. The only exception is a Parent relationship, where
    ownership is the point.
    """
    offenders: list[str] = []

    for path, node in _concrete_service_nodes():
        kind = f"{node['namespace']}{node['name']}"
        for rel in node.get("relationships") or []:
            if rel.get("kind") == "Parent":
                continue
            if rel.get("on_delete") != "no-action":
                offenders.append(f"{path}: {kind}.{rel['name']} -> {rel.get('on_delete')!r}")

    assert not offenders, "service relationships must set on_delete: no-action:\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# US3 -- the two service kinds that render Crossplane manifests
# ---------------------------------------------------------------------------

KUBERNETES_SERVICES_SCHEMA = "schemas/service/kubernetes_services.yml"


def test_cluster_bound_services_are_artifact_targets() -> None:
    """FR-083 and research.md R3.

    These two are rendered into Crossplane manifests and delivered as
    Infrahub artifacts, so marking them now means the transform cycle needs no
    schema change. The generic contributes no user-visible attribute.
    """
    schema = _load_yaml(KUBERNETES_SERVICES_SCHEMA)

    for name in ("FabricPeering", "FabricApp"):
        inherits = _node(schema, "Service", name)["inherit_from"]
        assert "CoreArtifactTarget" in inherits, f"Service{name} must be an artifact target"


def test_fabric_peering_service_records_what_realizes_it() -> None:
    """FR-082: the technical objects a service caused to exist."""
    peering = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", "FabricPeering")
    relationships = _relationships(peering)

    assert relationships["cluster"]["peer"] == "ClusterKubernetes"
    assert relationships["cluster"]["cardinality"] == "one"
    assert relationships["cluster"]["optional"] is False
    assert relationships["peerings"]["peer"] == "ClusterFabricPeering"
    assert relationships["peerings"]["cardinality"] == "many"


def test_fabric_app_allowed_sources_are_ipam_prefixes() -> None:
    """US3 acceptance scenario 3, and the load-bearing assertion of this story.

    The lab permits three source networks to reach the demo frontend --
    10.210.0.0/24 (the app tenant, across the firewall), 10.60.0.0/16 (WAN
    customers) and 10.70.0.0/24 (the branch). Those same three networks are
    named by the vSRX zone policy and the leaf ACL. A List of CIDR strings
    here would leave three independent restatements of one fact; a
    relationship makes them the same objects.
    """
    app = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", "FabricApp")
    allowed = _relationships(app)["allowed_source_prefixes"]

    assert allowed["peer"] == "IpamPrefix"
    assert allowed["cardinality"] == "many"
    assert "allowed_source_prefixes" not in _attributes(app)


def test_fabric_app_exposure_fields_are_optional() -> None:
    """US3 acceptance scenario 4: an unexposed app must be valid.

    The lab expresses this as the presence or absence of an ``expose`` block.
    A schema has no optional-block construct, so the faithful translation is
    an ``exposed`` boolean with optional VIP fields -- and an object with
    exposed false and no vip_block has to validate.
    """
    app = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", "FabricApp")
    attributes = _attributes(app)
    relationships = _relationships(app)

    assert attributes["exposed"]["kind"] == "Boolean"
    assert attributes["exposed"]["default_value"] is False
    assert relationships["vip_block"]["optional"] is True
    assert attributes["service_selector"]["optional"] is True


def test_fabric_app_workload_source_supports_chart_manifests_or_both() -> None:
    """FR-025: three valid combinations, so every field must be optional."""
    app = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", "FabricApp")
    attributes = _attributes(app)

    for name in ("chart_repository", "chart_name", "chart_version", "chart_values", "manifests"):
        assert attributes[name]["optional"] is True, f"{name} must be optional"


def test_fabric_app_namespace_attribute_avoids_the_reserved_word() -> None:
    """``namespace`` is a schema-level key; the attribute must not shadow it."""
    app = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", "FabricApp")
    attributes = _attributes(app)

    assert "namespace_name" in attributes
    assert "namespace" not in attributes


def test_fabric_app_policy_baseline_is_discrete_flags() -> None:
    """FR-024: not one opaque blob, so each gate is queryable."""
    app = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", "FabricApp")
    attributes = _attributes(app)

    assert attributes["policy_default_deny"]["default_value"] is True
    assert attributes["policy_allow_dns"]["default_value"] is True
    # Almost every multi-component app needs this: default-deny denies egress
    # too, so without it a chart's own components cannot reach each other and
    # the app fails in a way that looks like the chart is broken.
    assert attributes["policy_allow_intra_namespace"]["default_value"] is True
    assert attributes["policy_allow_egress_api_server"]["default_value"] is False
    assert attributes["policy_allow_egress_internet"]["default_value"] is False


# ---------------------------------------------------------------------------
# US5 -- the access grant
# ---------------------------------------------------------------------------

ACCESS_SERVICES_SCHEMA = "schemas/service/access_services.yml"


def test_app_access_is_an_artifact_target() -> None:
    """FR-083: the grant renders into a Crossplane manifest like the other two."""
    access = _node(_load_yaml(ACCESS_SERVICES_SCHEMA), "Service", "AppAccess")

    assert "CoreArtifactTarget" in access["inherit_from"]


def test_app_access_approval_gate_defaults_to_false() -> None:
    """FR-029 / US5 acceptance scenario 2.

    Nothing is composed while this is false, so an unapproved request is inert
    rather than merely hidden. Approval is a patch on one field, which means it
    lands in the change history and can come from the portal or from the API.
    """
    access = _node(_load_yaml(ACCESS_SERVICES_SCHEMA), "Service", "AppAccess")
    approved = _attributes(access)["approved"]

    assert approved["kind"] == "Boolean"
    assert approved["default_value"] is False
    assert approved["optional"] is False


def test_app_access_records_who_approved_and_when() -> None:
    """US5 acceptance scenario 3: the audit trail lives on the grant."""
    access = _node(_load_yaml(ACCESS_SERVICES_SCHEMA), "Service", "AppAccess")
    attributes = _attributes(access)

    assert attributes["requester"]["optional"] is False
    assert attributes["approved_by"]["kind"] == "Text"
    assert attributes["approved_at"]["kind"] == "DateTime"
    assert attributes["justification"]["kind"] == "TextArea"


def test_app_access_names_every_object_needed_to_grant_and_revoke() -> None:
    """FR-049 and FR-082.

    An app that is deployed and not permitted is a ticket; a firewall hole with
    nothing behind it is an audit finding. All four targets are mandatory so a
    grant cannot exist naming only half of the path.
    """
    access = _node(_load_yaml(ACCESS_SERVICES_SCHEMA), "Service", "AppAccess")
    relationships = _relationships(access)

    for name, peer in (
        ("application", "ServiceFabricApp"),
        ("source_zone", "SecurityZone"),
        ("source_address", "SecurityGenericAddress"),
        ("destination_vip", "IpamIPAddress"),
    ):
        assert relationships[name]["peer"] == peer
        assert relationships[name]["cardinality"] == "one"
        assert relationships[name]["optional"] is False

    # What the grant caused to exist, so revocation is traceable.
    assert relationships["granted_rules"]["peer"] == "SecurityPolicyRule"
    assert relationships["granted_rules"]["cardinality"] == "many"


def test_app_access_source_is_a_firewall_object_not_a_cidr() -> None:
    """The firewall's own vocabulary stays the vocabulary.

    The lab's FirewallAccess CRD names an existing address-book entry rather
    than synthesising a source CIDR, so the generated rules read the same way
    as the hand-written ones sitting beside them.
    """
    access = _node(_load_yaml(ACCESS_SERVICES_SCHEMA), "Service", "AppAccess")
    attributes = _attributes(access)

    assert not {name for name in attributes if "cidr" in name or name == "source"}


def test_app_access_ports_are_a_list_attribute() -> None:
    """Empty is rejected by the generator, never read as "all"."""
    access = _node(_load_yaml(ACCESS_SERVICES_SCHEMA), "Service", "AppAccess")

    assert _attributes(access)["ports"]["kind"] == "List"


# ---------------------------------------------------------------------------
# US7 -- the provider and tenant services
# ---------------------------------------------------------------------------

WAN_SERVICES_SCHEMA = "schemas/service/wan_services.yml"


def test_wan_services_are_not_artifact_targets() -> None:
    """research.md R3.

    These three render through device-scoped artifacts -- FRR on the PE and CE,
    EOS on the fabric -- not through a cluster manifest. Marking them as
    artifact targets would imply a per-service artifact that will never exist.
    """
    schema = _load_yaml(WAN_SERVICES_SCHEMA)

    for name in ("L3vpn", "InternetAccess", "TenantCloud"):
        inherits = _node(schema, "Service", name)["inherit_from"]
        assert "CoreArtifactTarget" not in inherits, f"Service{name} is not artifact-rendered"
        assert "GeneratorTarget" in inherits


def test_l3vpn_spans_one_tenant_and_many_circuits() -> None:
    """FR-048 / US7 acceptance scenario 4.

    One tenant, many member sites' circuits. This is what makes two sites of
    one tenant reach each other by shared VPN membership rather than by a
    leaked route.
    """
    l3vpn = _node(_load_yaml(WAN_SERVICES_SCHEMA), "Service", "L3vpn")
    relationships = _relationships(l3vpn)

    assert relationships["tenant"]["peer"] == "OrganizationTenant"
    assert relationships["tenant"]["cardinality"] == "one"
    assert relationships["tenant"]["optional"] is False
    assert relationships["circuits"]["peer"] == "DcimCircuit"
    assert relationships["circuits"]["cardinality"] == "many"


def test_internet_access_attaches_to_an_l3vpn() -> None:
    """US7 acceptance scenario 2."""
    access = _node(_load_yaml(WAN_SERVICES_SCHEMA), "Service", "InternetAccess")
    relationships = _relationships(access)

    assert relationships["l3vpn"]["peer"] == "ServiceL3vpn"
    assert relationships["l3vpn"]["cardinality"] == "one"
    assert relationships["l3vpn"]["optional"] is False


def test_internet_access_duplicates_nothing_the_l3vpn_holds() -> None:
    """SC-007 / US7 acceptance scenario 3.

    acme buys internet access and globex does not. The whole difference between
    the two tenants must be the presence of this one object -- so it may not
    carry a tenant, a VRF, or a circuit set of its own, which would be a second
    place for the same fact to live and a second place for it to disagree.
    """
    access = _node(_load_yaml(WAN_SERVICES_SCHEMA), "Service", "InternetAccess")
    relationships = set(_relationships(access))

    assert not {"tenant", "vrf", "circuits", "sites"} & relationships


def test_tenant_cloud_couples_vrf_zone_and_prefix() -> None:
    """FR-047 / US7 acceptance scenario 4.

    The bridge between the provider edge and the fabric. All three are
    mandatory because a tenant cloud with no zone is unreachable and a tenant
    cloud with no VRF is not isolated -- the lab's isolation is structural,
    and it needs all three to be so.
    """
    cloud = _node(_load_yaml(WAN_SERVICES_SCHEMA), "Service", "TenantCloud")
    relationships = _relationships(cloud)

    for name, peer in (
        ("tenant", "OrganizationTenant"),
        ("vrf", "IpamVRF"),
        ("zone", "SecurityZone"),
        ("prefix", "IpamPrefix"),
    ):
        assert relationships[name]["peer"] == peer
        assert relationships[name]["cardinality"] == "one"
        assert relationships[name]["optional"] is False


def test_no_tenant_cloud_to_tenant_cloud_relationship_exists() -> None:
    """The isolation is the absence of a path, and must stay absent.

    Two tenant clouds must have no route between them. A relationship here
    would invite modelling one, which is the failure the lab's negative
    assertions exist to catch.
    """
    cloud = _node(_load_yaml(WAN_SERVICES_SCHEMA), "Service", "TenantCloud")
    peers = {rel.get("peer") for rel in cloud.get("relationships") or []}

    assert "ServiceTenantCloud" not in peers

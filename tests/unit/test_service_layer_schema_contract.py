"""Contract tests for the service layer of the OTTERNET lab schema feature.

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


def test_service_generic_carries_no_requested_by() -> None:
    """Withdrawn, and asserted rather than assumed.

    `requested_by` pointed at a CoreGenericAccount and was meant to record the
    authenticated identity behind a request. Nothing ever wrote it: the
    generated Backstage forms drop every relationship whose peer starts with
    `Core`, and neither the curated template nor the Streamlit pages set it
    either, so it read null on every service object including the ones a real
    portal request created.

    What survives it is the record that is actually filled. Attribution for the
    WRITE is `InfrahubEvent.account_id`, which the portal's mutation `context`
    populates with the signed-in user; who asked in prose is
    `ServiceAppAccess.requester` and the proposed change's description. An empty
    relationship beside those three is a field a reviewer can only misread.

    Re-adding it means committing to a writer for it, so the absence is a test.
    """
    service = _generic(_load_yaml(SERVICE_SCHEMA), "Service", "Generic")

    assert "requested_by" not in _relationships(service), (
        "requested_by is back; it needs a writer in the Backstage templates and the "
        "Streamlit pages, or it reads null on every service object"
    )


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


def _is_owned_attachment(node: dict[str, Any]) -> bool:
    """Is this node a payload file owned by a service, rather than a service?

    Introduced by specs/013-app-file-attachments. A node inheriting
    ``CoreFileObject`` lives in the service directory because the service owns
    it, but it is not itself a service: it has no ordered intent, no owner and
    no status, so the service-kind invariants below do not apply to it.

    This narrows two invariants to what they actually mean rather than to
    "every node in the service directory", the same way ``NON_AVD_DEVICE_ROLES``
    narrows the AVD role mapping in tests/unit/test_avd.py.
    """
    return "CoreFileObject" in (node.get("inherit_from") or [])


def _owned_attachment_kinds() -> set[str]:
    """The kinds a service may legitimately own and cascade to."""
    return {f"{node['namespace']}{node['name']}" for _, node in _concrete_service_nodes() if _is_owned_attachment(node)}


def test_every_concrete_service_kind_is_a_generator_target() -> None:
    """FR-081: a generator must be able to sit underneath each service kind.

    GeneratorTarget supplies the ``checksum`` attribute the project's
    idempotence rules operate on. Without it a generator can still target the
    node, but every run does full work and has no field to compare against.
    """
    for path, node in _concrete_service_nodes():
        if _is_owned_attachment(node):
            continue
        kind = f"{node['namespace']}{node['name']}"
        inherits = node.get("inherit_from", [])
        assert "ServiceGeneric" in inherits, f"{kind} in {path} must inherit ServiceGeneric"
        assert "GeneratorTarget" in inherits, f"{kind} in {path} must inherit GeneratorTarget"


def test_no_service_relationship_cascades_into_infrastructure() -> None:
    """FR-053: deleting a service must never delete a device or a prefix.

    A service is a statement of intent about technical objects it references
    but does not own. Two exceptions, both about genuine ownership: a Parent
    relationship, and a payload file the service owns (specs/013).
    """
    offenders: list[str] = []
    owned = _owned_attachment_kinds()

    for path, node in _concrete_service_nodes():
        kind = f"{node['namespace']}{node['name']}"
        for rel in node.get("relationships") or []:
            if rel.get("kind") == "Parent":
                continue
            # A payload file the service owns is not infrastructure. Cascading
            # to it is the point -- deleting an application must not leave its
            # manifests behind as orphans. The guarantee this test exists for
            # is that deleting a service never deletes a device or a prefix,
            # and that is untouched.
            if rel.get("peer") in owned:
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


def test_fabric_app_workload_source_is_a_chart_and_nothing_else() -> None:
    """033 FR-010 to FR-012. One way to describe a workload, not three.

    Cycle 010 made every chart field optional because an application could be a
    chart, raw manifests, or both -- so the renderer decided which by looking at
    what happened to be populated, and refused only when everything was empty.

    The three chart fields are now mandatory TOGETHER, which is the constraint
    the Crossplane XRD already imposes (`required: [repository, name, version]`).
    Stating it here catches an incomplete chart before an artifact renders,
    rather than after the cluster rejects it.
    """
    app = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", "FabricApp")
    attributes = _attributes(app)

    for name in ("chart_repository", "chart_name", "chart_version"):
        assert attributes[name].get("optional") is False, f"{name} must be mandatory"

    # The inline escape hatch for values small enough not to need a file. The
    # attachment still wins when both are present.
    assert attributes["chart_values"]["optional"] is True


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


def test_app_access_carries_no_approval_fields() -> None:
    """FR-029 / US5 scenario 2, INVERTED, and deliberately.

    The kind carried `approved`, `approved_by` and `approved_at`, and nothing
    was composed while the first was false. That was a second gate in front of
    one the workflow already has: a request is made on a branch and reaches no
    device until its proposed change merges. Two gates can only disagree --
    approved but unmerged changed nothing, and merged but unapproved left an
    object on main doing nothing and saying nothing about why.

    Merging is the approval, and it is the better record: a reviewer, a diff and
    a history, where the Boolean had one person's patch. Re-adding any of these
    fields means re-deciding that, so the absence is asserted rather than
    assumed.
    """
    access = _node(_load_yaml(ACCESS_SERVICES_SCHEMA), "Service", "AppAccess")
    attributes = _attributes(access)

    for gone in ("approved", "approved_by", "approved_at"):
        assert gone not in attributes, f"{gone} is back; the branch is the gate, and two gates can only disagree"


def test_app_access_still_records_who_asked_and_why() -> None:
    """Removing the approval trail does not remove the REQUEST trail.

    Who asked and why are the parts a reviewer needs; who approved is now the
    proposed change's own history.
    """
    access = _node(_load_yaml(ACCESS_SERVICES_SCHEMA), "Service", "AppAccess")
    attributes = _attributes(access)

    assert attributes["requester"]["optional"] is False
    assert attributes["justification"]["kind"] == "TextArea"


def test_app_access_names_every_object_needed_to_grant_and_revoke() -> None:
    """FR-049 and FR-082.

    An app that is deployed and not permitted is a ticket; a firewall hole with
    nothing behind it is an audit finding. All four targets are mandatory so a
    grant cannot exist naming only half of the path.
    """
    access = _node(_load_yaml(ACCESS_SERVICES_SCHEMA), "Service", "AppAccess")
    relationships = _relationships(access)

    # Mandatory: nothing can derive this one.
    assert relationships["application"]["peer"] == "ServiceFabricApp"
    assert relationships["application"]["cardinality"] == "one"
    assert relationships["application"]["optional"] is False

    # Derivable from `source_site`, which is the half of the question a
    # requester can actually answer -- a person knows where they sit far better
    # than they know which security zone that is. Naming either directly still
    # wins, which is how the platform team asks for a source that is not
    # somebody's desk. The generator refuses a grant where neither resolves.
    for name, peer in (
        ("source_site", "LocationSite"),
        ("source_zone", "SecurityZone"),
        ("source_address", "SecurityGenericAddress"),
    ):
        assert relationships[name]["peer"] == peer
        assert relationships[name]["cardinality"] == "one"
        assert relationships[name]["optional"] is True

    # OPTIONAL, and empty is the normal case. Cilium assigns the VIP to a
    # LoadBalancer service at runtime, so a requester cannot honestly know it;
    # left empty the generator permits to the application's own `vip_block`,
    # the set of addresses it can ever be advertised on. Naming one is how you
    # ask for a single address instead.
    assert relationships["destination_vip"]["peer"] == "IpamIPAddress"
    assert relationships["destination_vip"]["cardinality"] == "one"
    assert relationships["destination_vip"]["optional"] is True

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


# ---------------------------------------------------------------------------
# Application file attachments (specs/013-app-file-attachments)
# ---------------------------------------------------------------------------

# One kind, not two. Cycle 033 withdrew the manifests attachment along with the
# raw-manifests path it carried; Helm values are the only payload an application
# still attaches, and they stay a file because a JSON attribute whose keys
# contain dots or slashes cannot be seeded through the object-load path.
APP_FILE_KINDS = ("FabricAppValuesFile",)

# Both sides of each relationship must carry these exact strings.
APP_FILE_IDENTIFIERS = {
    "FabricAppValuesFile": ("values_file", "fabricapp__values_file"),
}

# Supplied by CoreFileObject. Redeclaring any of them looks harmless and
# silently stops it being inherited.
CORE_FILE_OBJECT_FIELDS = {"file_name", "file_size", "file_type", "checksum", "storage_id"}


@pytest.mark.parametrize("name", APP_FILE_KINDS)
def test_app_file_kinds_exist_and_inherit_core_file_object(name: str) -> None:
    """GI-4. The checksum arrives by inheritance, not by declaration.

    `CoreFileObject` is Infrahub's file-attachment interface, already used
    twice in this repository by AvdHostvarFile and AvdStructuredConfigFile.
    """
    node = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", name)

    assert "CoreFileObject" in (node.get("inherit_from") or [])
    assert node.get("include_in_menu") is False


@pytest.mark.parametrize("name", APP_FILE_KINDS)
def test_app_file_kinds_do_not_redeclare_inherited_fields(name: str) -> None:
    """Redeclaring an inherited field is the quiet way to lose it."""
    node = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", name)

    assert not CORE_FILE_OBJECT_FIELDS & set(_attributes(node))


@pytest.mark.parametrize("name", APP_FILE_KINDS)
def test_app_file_parent_relationship(name: str) -> None:
    """GI-1. A payload file cannot exist without the application it belongs to."""
    node = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", name)
    app_rel = _relationships(node)["app"]

    assert app_rel["peer"] == "ServiceFabricApp"
    assert app_rel["kind"] == "Parent"
    assert app_rel["cardinality"] == "one"
    assert app_rel["optional"] is False


@pytest.mark.parametrize("name", APP_FILE_KINDS)
def test_app_file_relationship_identifiers_match(name: str) -> None:
    """GI-5, and the schema skill's CRITICAL relationship rule.

    Both sides of a bidirectional relationship must share one identifier
    string. Mismatched identifiers do not error -- they silently create two
    one-way relationships instead of one link.
    """
    schema = _load_yaml(KUBERNETES_SERVICES_SCHEMA)
    app_side_name, identifier = APP_FILE_IDENTIFIERS[name]

    child = _node(schema, "Service", name)
    assert _relationships(child)["app"]["identifier"] == identifier

    parent_rel = _relationships(_node(schema, "Service", "FabricApp"))[app_side_name]
    assert parent_rel["identifier"] == identifier
    assert parent_rel["peer"] == f"Service{name}"
    assert parent_rel["kind"] == "Component"
    assert parent_rel["cardinality"] == "one"
    assert parent_rel["optional"] is True


@pytest.mark.parametrize("name", APP_FILE_KINDS)
def test_app_file_uniqueness_and_hfid(name: str) -> None:
    """GI-2, and the uniqueness-constraint format rule.

    A relationship is named bare in a uniqueness constraint; an attribute
    takes `__value`. Getting it the wrong way round fails at load with
    "references unknown field".
    """
    node = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", name)

    assert node["uniqueness_constraints"] == [["app"]]
    assert node["human_friendly_id"] == ["app__name__value"]


@pytest.mark.parametrize("name", APP_FILE_KINDS)
def test_precedence_rule_is_documented(name: str) -> None:
    """FR-011. The rule must be discoverable from the schema itself.

    Two mechanisms for one payload need a stated winner, and a consumer
    should not have to read a spec document to find it.
    """
    node = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", name)
    description = (node.get("description") or "").lower()

    assert "precedence" in description or "wins" in description


def test_app_keeps_its_inline_payload_attributes() -> None:
    """FR-010, GI-6, 033 FR-013. The attribute stays as an inline escape hatch.

    Singular since cycle 033: `manifests` went with the raw-manifests path, so
    `chart_values` is the only inline payload left.
    """
    app = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", "FabricApp")
    attributes = _attributes(app)

    assert attributes["chart_values"]["kind"] == "JSON"


# ---------------------------------------------------------------------------
# A chart is the whole workload source (specs/033-fabricapp-helm-chart)
# ---------------------------------------------------------------------------


def test_the_raw_manifests_path_is_gone_from_the_yaml() -> None:
    """033 FR-003, FR-014, FR-020, SC-003. Absent, not merely marked absent.

    `state: absent` is how Infrahub is TOLD to remove something, and it is a
    migration instruction rather than an end state. `infrahubctl protocols`
    reads these YAML files rather than the loaded schema, so it does not honour
    it: a `state: absent` block left in place keeps generating a protocol class
    and two fields for things the graph no longer has, and mypy stays clean
    because the types are internally consistent.

    So the blocks come out once the removal has been loaded, and this is what
    notices when they do not.
    """
    schema = _load_yaml(KUBERNETES_SERVICES_SCHEMA)
    app = _node(schema, "Service", "FabricApp")

    assert "manifests" not in _attributes(app)
    assert "manifests_file" not in _relationships(app)

    kinds = {f"{node.get('namespace')}{node.get('name')}" for node in _nodes(schema)}
    assert "ServiceFabricAppManifestsFile" not in kinds

    # The identifier has to go with it, or a relationship is left pointing at a
    # kind nothing defines.
    raw = (REPO_ROOT / KUBERNETES_SERVICES_SCHEMA).read_text(encoding="utf-8")
    assert "fabricapp__manifests_file" not in raw


def test_advertised_services_relationship_shape() -> None:
    """033 FR-024, FR-026. What a grant reads instead of the manifests.

    `generate-app-access` derived a grant's destination ports by reading the
    application's manifests for LoadBalancer Services. A chart's Services exist
    only once Helm has run, which Infrahub cannot do -- so the application names
    the service objects instead.

    `on_delete` is the field to watch. Its only alternative, `cascade`, deletes
    the PEER: deleting an application would delete `junos-http` and take the
    four hand-written baseline rules that share it with it.
    """
    app = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", "FabricApp")
    relationship = _relationships(app)["advertised_services"]

    assert relationship["peer"] == "SecurityService"
    assert relationship["kind"] == "Generic"
    assert relationship["cardinality"] == "many"
    assert relationship["optional"] is True
    assert relationship["on_delete"] == "no-action"
    assert relationship["identifier"] == "service__app_advertised_services"


def test_advertised_services_peers_the_node_and_not_the_generic() -> None:
    """033 FR-027. Every peer must have exactly one port.

    `SecurityGenericService` also covers `SecurityServiceRange`, which has a
    `start` and an `end`, and `SecurityServiceGroup`, which has neither. The
    access generator resolves a grant's ports to integers from end to end, so
    admitting either would hand it a peer it cannot turn into a port number.

    Naming a range is a coherent feature; it is simply not this one.
    """
    app = _node(_load_yaml(KUBERNETES_SERVICES_SCHEMA), "Service", "FabricApp")
    relationship = _relationships(app)["advertised_services"]

    assert relationship["peer"] != "SecurityGenericService"

    security = _load_yaml("schemas/security/security.yml")
    service = _node(security, "Security", "Service")
    assert "port" in _attributes(service), "the peer must carry a single port"

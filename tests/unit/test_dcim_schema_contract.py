"""Contract tests for the split of ``DcimDevice`` into router and fabric-switch kinds.

Cycle 027 adds ``DcimFabricSwitch`` beside ``DcimDevice`` and moves twelve
fabric-only fields onto it. Two failure modes make this cycle worth pinning, and
neither produces an error at load time:

* **A one-way relationship.** If a forward side moves to the new kind and its
  reverse side is left pointing at ``DcimDevice``, Infrahub creates two
  independent one-way relationships. The schema loads, it validates, and the
  field is silently always empty. ``test_every_identifier_is_two_sided_and_agrees``
  is written against *every* identifier in ``schemas/``, not the ones this cycle
  touched, because cycle 024 found a careless global ``sed`` had flipped five
  unrelated peers and nothing in 998 green tests noticed.
* **A query that names the wrong kind.** A concrete-kind fragment that meets a
  switch returns nothing at all. That is the failure that hid the cabling plan's
  missing cables for months.

THE COUNT THAT MATTERS: thirteen ``peer: DcimDevice`` sites exist across
``schemas/``. Seven become ``DcimFabricSwitch``, **two widen to
``DcimGenericDevice``** because their objects span both kinds, and four stay.
Four of the seven have no forward side on ``DcimDevice`` at all, so a reader
working from the moved-field list alone would miss them.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).parents[2]
SCHEMAS_DIR = REPO_ROOT / "schemas"


def _schema_files() -> list[Path]:
    return sorted(p for p in SCHEMAS_DIR.rglob("*.yml") if p.is_file())


def _load(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _kind_of(entry: dict[str, Any]) -> str:
    """Full kind for a node/generic entry, or the ``kind:`` of an extension entry."""
    if "kind" in entry and "name" not in entry:
        return str(entry["kind"])
    return f"{entry.get('namespace', '')}{entry.get('name', '')}"


def _owners() -> list[tuple[str, dict[str, Any]]]:
    """Every kind that can own relationships, paired with its declaring entry.

    A kind appears more than once when a base file declares it and an extension
    file adds to it -- which is exactly how ``DcimDevice`` is built here.
    """
    owners: list[tuple[str, dict[str, Any]]] = []
    for path in _schema_files():
        schema = _load(path)
        for section in ("generics", "nodes"):
            owners.extend((_kind_of(entry), entry) for entry in schema.get(section) or [])
        owners.extend((_kind_of(entry), entry) for entry in (schema.get("extensions") or {}).get("nodes") or [])
    return owners


def _inheritance() -> dict[str, set[str]]:
    """kind -> the generics it inherits, transitively."""
    direct: dict[str, set[str]] = defaultdict(set)
    for kind, entry in _owners():
        direct[kind] |= set(entry.get("inherit_from") or [])

    resolved: dict[str, set[str]] = {}
    for kind, parents in direct.items():
        seen: set[str] = set()
        stack = list(parents)
        while stack:
            parent = stack.pop()
            if parent in seen:
                continue
            seen.add(parent)
            stack.extend(direct.get(parent, ()))
        resolved[kind] = seen
    return resolved


def _relationship_ends() -> dict[str, list[dict[str, str]]]:
    """identifier -> the relationship declarations carrying it."""
    ends: dict[str, list[dict[str, str]]] = defaultdict(list)
    for kind, entry in _owners():
        for rel in entry.get("relationships") or []:
            identifier = rel.get("identifier")
            if not identifier:
                continue
            ends[str(identifier)].append(
                {"owner": kind, "peer": str(rel.get("peer", "")), "name": str(rel.get("name", ""))}
            )
    return ends


# Two identifiers fail this clause on the UNTOUCHED tree, and they are real --
# found by writing the test, not by suspecting them. `schemas/service/service.yml`
# declares two "binding generics", ServiceGenericDevice and ServiceGenericInterface,
# meant to be inherited by service kinds that scope to devices or interfaces.
# **Nothing inherits either of them.** So `DcimGenericDevice.device_services` peers
# ServiceGeneric while the only other end of that identifier sits on a generic no
# kind opts into, and the reverse side is dead.
#
# That is a pre-existing defect in the service layer and entirely outside cycle 027,
# which touches neither file. It is pinned here rather than excused: the clause still
# catches anything new, and the equality assertion below fails if this list goes stale
# in either direction -- a third one appearing, or one of these being repaired.
KNOWN_ONE_WAY = frozenset({"device_services", "interface_services"})


def test_every_identifier_is_two_sided_and_agrees() -> None:
    """C6e. The clause that makes thirteen peer edits verifiable in one number.

    For an identifier declared on more than one relationship, every declaration's
    ``peer`` must be another declaration's *owner*, or a generic that owner
    inherits. A reverse side left pointing at ``DcimDevice`` while its forward
    side moved to ``DcimFabricSwitch`` fails here -- and fails nowhere else,
    because Infrahub accepts it without complaint.

    Identifiers declared once are skipped: they are one-sided by design (the
    device end of ``EvpnSviNode``, for instance, exists only on the related
    node), and there is no second end to disagree with.
    """
    inherits = _inheritance()
    descendants: dict[str, set[str]] = defaultdict(set)
    for kind, parents in inherits.items():
        for parent in parents:
            descendants[parent].add(kind)

    def _reaches(peer: str, owner: str) -> bool:
        """Can a relationship peering ``peer`` land on something that is an ``owner``?

        Three ways. The third covers pairing through a concrete kind that inherits
        both ends' generics, which is how a *binding* generic is meant to work.
        """
        if peer == owner or peer in inherits.get(owner, set()):
            return True
        return any(peer == kind or peer in inherits.get(kind, set()) for kind in descendants.get(owner, set()))

    problems: list[str] = []

    for identifier, declarations in sorted(_relationship_ends().items()):
        if len(declarations) < 2:
            continue
        owners = {d["owner"] for d in declarations}
        for declaration in declarations:
            peer = declaration["peer"]
            reachable = any(_reaches(peer, owner) for owner in owners)
            if not reachable:
                problems.append(
                    f"{identifier}: {declaration['owner']}.{declaration['name']} peers {peer}, "
                    f"which is neither another end's owner nor a generic one inherits "
                    f"(other ends: {sorted(owners - {declaration['owner']})})"
                )

    unexpected = [p for p in problems if not p.startswith(tuple(KNOWN_ONE_WAY))]
    assert not unexpected, "one-way relationships (they load without error):\n" + "\n".join(unexpected)

    still_broken = {p.split(":", 1)[0] for p in problems}
    assert still_broken == KNOWN_ONE_WAY, (
        "the known-one-way allowlist is stale. Remove an identifier once it is "
        f"repaired; do not add one to silence this clause. now broken: {sorted(still_broken)}"
    )


# ---------------------------------------------------------------------------
# C1 to C5: the node, the fields, the dropdowns
# ---------------------------------------------------------------------------

BASE_DCIM = "schemas/base/dcim.yml"
DCIM_EXTENSIONS = "schemas/dcim_extensions.yml"

# Copied from DcimDevice verbatim rather than redesigned. All three earn their
# place: CoreArtifactTarget because a switch carries EOS configs, device docs and
# an ANTA catalog; DcimGenericDevice so every polymorphic relationship keeps
# resolving; DcimPhysicalDevice because a switch is rack-mounted.
FABRIC_SWITCH_GENERICS = ["CoreArtifactTarget", "DcimGenericDevice", "DcimPhysicalDevice"]

# The twelve. Measured across the 7 switches and 7 routers in the live graph
# before anything moved: each is populated on switches and on no router.
MOVED_TO_FABRIC_SWITCH = (
    "vtep_loopback_ip",
    "mlag_domain",
    "evpn_gateway_group",
    "node_id",
    "index",
    "pod",
    "rack",
    "avd_artifact",
    # `object_template` is deliberately absent from this list -- see
    # test_the_object_template_moved_with_its_flag. It is not a declared field.
    "loopback_ip",
    "mgmt_ip",
    "avd_custom_hostvars",
)

# `router_id` is populated on 6 of 7 routers and no switch; `bgp_neighbors` has
# 10 objects, all on routers.
#
# FR-006 also listed `location`, and that was wrong -- found by implementing it.
# `location` is not on DcimDevice at all: it is declared on the
# DcimPhysicalDevice GENERIC, which DcimDevice, DcimFabricSwitch,
# SecurityFirewall and ComputePhysicalServer all inherit. It cannot be made
# router-only without changing a generic shared with the firewall and the
# servers, which is a different cycle's decision. It is pinned as shared below.
STAYS_ON_DCIM_DEVICE = ("router_id", "bgp_neighbors")

FABRIC_ROLES = {
    "super_spine",
    "spine",
    "leaf",
    "border_leaf",
    "l2leaf",
    "l2spine",
    "l3spine",
    "p",
    "pe",
    "rr",
}
ROUTER_ROLES = {
    "isp_edge",
    "isp_core",
    "internet_edge",
    "customer_edge",
    "branch_router",
    "k8s_node",
}


def _yaml(path: str) -> dict[str, Any]:
    return _load(REPO_ROOT / path)


def _node_entry(schema: dict[str, Any], namespace: str, name: str) -> dict[str, Any]:
    for node in schema.get("nodes") or []:
        if node.get("namespace") == namespace and node.get("name") == name:
            return node
    raise AssertionError(f"{namespace}{name} not found")


def _extension_entry(schema: dict[str, Any], kind: str) -> dict[str, Any]:
    for entry in (schema.get("extensions") or {}).get("nodes") or []:
        if entry.get("kind") == kind:
            return entry
    raise AssertionError(f"no extension entry for {kind}")


def _field_names(entry: dict[str, Any]) -> set[str]:
    return {f["name"] for f in (entry.get("attributes") or []) + (entry.get("relationships") or [])}


def _all_fields(kind: str) -> set[str]:
    """Every attribute and relationship declared for a kind, across all files."""
    return {name for owner, entry in _owners() if owner == kind for name in _field_names(entry)}


def _role_choices(kind: str) -> set[str]:
    for owner, entry in _owners():
        if owner != kind:
            continue
        for attribute in entry.get("attributes") or []:
            if attribute.get("name") == "role" and "choices" in attribute:
                return {c["name"] for c in attribute["choices"]}
    raise AssertionError(f"no role dropdown found for {kind}")


def test_fabric_switch_node_exists_and_inherits_exactly_three_generics() -> None:
    """C1. The list is asserted exactly, not as a superset.

    A fourth generic appearing later is a design change and should fail a test
    rather than land quietly.
    """
    node = _node_entry(_yaml(BASE_DCIM), "Dcim", "FabricSwitch")
    assert node["inherit_from"] == FABRIC_SWITCH_GENERICS


def test_the_twelve_fields_moved_in_both_directions() -> None:
    """C2. Presence alone would pass if the fields were COPIED rather than moved.

    That is the likeliest way to get this half-right, so absence is asserted too.
    """
    switch_fields = _all_fields("DcimFabricSwitch")
    device_fields = _all_fields("DcimDevice")

    missing = [f for f in MOVED_TO_FABRIC_SWITCH if f not in switch_fields]
    assert not missing, f"DcimFabricSwitch is missing moved fields: {missing}"

    left_behind = [f for f in MOVED_TO_FABRIC_SWITCH if f in device_fields]
    assert not left_behind, f"these were copied, not moved -- still on DcimDevice: {left_behind}"


def test_the_router_fields_stayed() -> None:
    """C3. `bgp_neighbors` is the one worth naming: 10 objects, all on routers."""
    device_fields = _all_fields("DcimDevice")
    switch_fields = _all_fields("DcimFabricSwitch")

    for field in STAYS_ON_DCIM_DEVICE:
        assert field in device_fields, f"{field} must stay on DcimDevice"
        assert field not in switch_fields, f"{field} is router-only and must not be on the switch"


def test_both_kinds_keep_the_shared_fields() -> None:
    """C4. `asn` being on both is what forces RoutingAsn.devices to peer the generic.

    `location` is here rather than in C3 because it is inherited from
    DcimPhysicalDevice by every physical device kind, the firewall and the
    servers included.
    """
    inherits = _inheritance()
    for kind in ("DcimDevice", "DcimFabricSwitch"):
        reachable = _all_fields(kind) | {name for generic in inherits.get(kind, set()) for name in _all_fields(generic)}
        for field in ("status", "role", "rack_face", "asn", "device_type", "platform", "location"):
            assert field in reachable, f"{field} must resolve on {kind}"


def test_the_two_role_dropdowns_are_disjoint_and_exhaustive() -> None:
    """C5. Three assertions, because each catches a different way to get it wrong.

    The fabric set must EQUAL ``ROLE_TO_AVD_TYPE``, because ``get_avd_type``
    raises on anything else -- the schema and the code then say the same thing
    from two directions. The disjointness clause is the one that catches the
    split silently undoing itself: a fabric role reappearing on the router kind
    would let an FRR router be handed to pyAVD.
    """
    from solution_arista_avd.avd import ROLE_TO_AVD_TYPE

    fabric = _role_choices("DcimFabricSwitch")
    router = _role_choices("DcimDevice")

    assert fabric == set(ROLE_TO_AVD_TYPE), "the fabric dropdown must equal ROLE_TO_AVD_TYPE exactly"
    assert router == ROUTER_ROLES
    assert not fabric & router, f"a role on both kinds undoes the split: {fabric & router}"
    assert fabric | router == FABRIC_ROLES | ROUTER_ROLES, (
        "the union must equal the sixteen values the single dropdown carried before "
        "the split; retiring a role is a separate, visible decision"
    )


def test_the_object_template_moved_with_its_flag() -> None:
    """The twelfth moved field is not a field, and that was found by implementing it.

    FR-005 lists ``object_template`` among the twelve. It is not declared in
    ``schemas/`` at all: Infrahub generates it, together with a
    ``TemplateDcimDevice`` kind, from ``generate_template: true`` on the node. So
    it moves by moving the flag, not by moving a YAML block -- and the seeded
    templates in ``objects/20_nfd41_device_types.yml`` must change kind with it.

    Checked before moving it: all seven ``object_template`` values in
    ``objects/26_nfd41_devices.yml`` are spines and leaves. No router uses one.
    """
    schema = _yaml(BASE_DCIM)
    assert _node_entry(schema, "Dcim", "FabricSwitch").get("generate_template") is True
    assert _node_entry(schema, "Dcim", "Device").get("generate_template") is not True, (
        "DcimDevice must lose generate_template, or it keeps an object_template relationship the routers never use"
    )
    assert "kind: TemplateDcimFabricSwitch" in _text("objects/20_nfd41_device_types.yml")


def test_display_properties_match_dcim_device() -> None:
    """C7. So nothing downstream has to special-case the new kind."""
    schema = _yaml(BASE_DCIM)
    device = _node_entry(schema, "Dcim", "Device")
    switch = _node_entry(schema, "Dcim", "FabricSwitch")

    for prop in ("human_friendly_id", "display_label", "order_by"):
        assert switch.get(prop) == device.get(prop), f"{prop} must match DcimDevice"


# ---------------------------------------------------------------------------
# C9 to C11: the consumers
#
# Phase 0 of this cycle put these at "3 queries, 6 fragments, 5 Python places".
# Generating the task list required naming every file, so the enumeration finally
# covered `checks/`, `src/` and Python string literals -- and the real surface is
# 6 query roots, 20 fragments and a dozen Python sites. The numbers below were
# re-derived, not carried forward.
# ---------------------------------------------------------------------------

# Every GraphQL root that names a device kind. `frr_config` is deliberately
# absent: its two roots target routers and must not move (C10).
EXPECTED_QUERY_ROOTS = {
    "generators/avd_device_hostvar.gql": 1,
    "transforms/avd_device_config.gql": 1,
    "transforms/avd_anta_catalog.gql": 2,  # :2 (`target:`) and :31 -- a one-site fix misses the second
    "transforms/avd_fabric_devices.gql": 1,
    "checks/cv_config_check.gql": 1,
}

# Per-file fragment counts after the split. Pinned exactly, in both kinds, so a
# retarget that drops a fragment instead of moving it fails here.
#
# `... on DcimDevice` survives in exactly ONE file: the service portal's
# interface view, which legitimately shows routers, servers and switches side by
# side and needs a fragment for each.
EXPECTED_FRAGMENTS = {
    "transforms/containerlab_topology.gql": {"DcimDevice": 0, "DcimFabricSwitch": 2},
    "transforms/cabling_plan.gql": {"DcimDevice": 0, "DcimFabricSwitch": 1},
    "transforms/cabling_plan.py": {"DcimDevice": 0, "DcimFabricSwitch": 2},
    "generators/avd_device_hostvar.gql": {"DcimDevice": 0, "DcimFabricSwitch": 5},
    "generators/generate_avd.gql": {"DcimDevice": 0, "DcimFabricSwitch": 1},
    "generators/backfill_structured_config.gql": {"DcimDevice": 0, "DcimFabricSwitch": 1},
    "generators/generate_fabric_peering.gql": {"DcimDevice": 0, "DcimFabricSwitch": 1},
    "checks/fabric_pool_check.gql": {"DcimDevice": 0, "DcimFabricSwitch": 1},
    "checks/peering_consistency_check.gql": {"DcimDevice": 0, "DcimFabricSwitch": 1},
    "service_catalog/pages/4_Fabric_View.py": {"DcimDevice": 2, "DcimFabricSwitch": 3},
}

# The sites no fragment grep reaches: Python comparing a kind as a string.
# Three of these fail SILENTLY -- the first returns a valid, empty result.
KIND_STRING_SITES = (
    "transforms/containerlab_topology.py",
    "generators/generate_avd_device_hostvar.py",
    "checks/cv_config_check.py",
    "src/solution_arista_avd/sorting.py",
)

MUTATION_STRING_SITES = ("generators/asn.py", "src/solution_arista_avd/generator.py")


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _root_count(text: str, kind: str) -> int:
    """Query roots only -- a `... on Kind {` fragment is not a root."""
    return len(re.findall(rf"(?<!\.\.\. on ){kind}\s*[({{]", text))


def test_the_six_query_roots_target_the_fabric_switch() -> None:
    """C9. Asserted by reading the files, so a missed retarget fails offline."""
    for path, expected in EXPECTED_QUERY_ROOTS.items():
        text = _text(path)
        assert _root_count(text, "DcimDevice") == 0, f"{path} still opens a query root on DcimDevice"
        found = _root_count(text, "DcimFabricSwitch")
        assert found == expected, f"{path}: expected {expected} DcimFabricSwitch roots, found {found}"


def test_frr_config_query_is_untouched() -> None:
    """C10. The file that "change every DcimDevice" would break.

    Its targets are the WAN's routers, which keep the kind. Asserted explicitly
    rather than left to review, because the obvious wrong way to do this cycle
    is a global replace.
    """
    text = _text("transforms/frr_config.gql")
    assert text.count("DcimDevice(") == 2, "frr_config.gql must keep both DcimDevice roots"
    assert "DcimFabricSwitch" not in text, "frr_config renders routers; the switch kind has no place in it"


def test_every_fragment_site_has_a_disposition() -> None:
    """C11a. Twenty sites across ten files, each pinned in both kinds.

    SC-008 rejects counting as sufficient, so this asserts the resulting shape
    rather than that the sites were visited.
    """
    for path, expected in EXPECTED_FRAGMENTS.items():
        text = _text(path)
        for kind, count in expected.items():
            found = text.count(f"... on {kind} {{")
            assert found == count, f"{path}: expected {count} `... on {kind}` fragments, found {found}"


def test_no_kind_name_is_compared_as_a_bare_string() -> None:
    """C11b and C11c. The clause that catches what a fragment grep cannot.

    ``transforms/containerlab_topology.py`` guarded on
    ``node.typename != "DcimDevice"``. After the split that skips every fabric
    switch and emits a topology with seven servers, no switches, **no error and
    valid YAML**. Two more read a response key that moves with the query root.

    ``*_query.py`` files are excluded: they are generated, and their
    ``Literal[...]`` unions legitimately name every kind a polymorphic field can
    return.
    """
    for path in KIND_STRING_SITES:
        # Comments are stripped first: several of these sites carry a comment
        # naming the OLD kind to explain why the guard moved, and that prose is
        # the most useful thing on the line. Only executable text is checked.
        code = "\n".join(line.split("#", 1)[0] for line in _text(path).splitlines())
        assert '"DcimDevice"' not in code, f'{path} still compares the kind name "DcimDevice" as a string'

    for path in MUTATION_STRING_SITES:
        assert "DcimDeviceUpsert" not in _text(path), f"{path} still embeds a DcimDeviceUpsert mutation string"

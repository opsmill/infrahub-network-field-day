"""Contract tests for the adopted marketplace security schema.

`schemas/security/security.yml` is downloaded from the Infrahub Marketplace
(`infrahub/security`) and is deliberately NOT authored here, so these tests
assert two different things:

1. The adopted file still provides the kinds this project depends on. If a
   future re-download drops or renames one, the service layer breaks and this
   fails first.
2. The local additions in `schemas/security_extensions.yml` land on the right
   kinds, and are the only local changes.

They do NOT re-assert the marketplace's own design. Attribute kinds, dropdown
choices and cardinalities inside the adopted file are upstream's to own;
testing them here would freeze someone else's schema against our opinion of it.
See `schemas/MARKETPLACE.md`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).parents[2]

SECURITY_SCHEMA = "schemas/security/security.yml"
SECURITY_EXTENSIONS = "schemas/security_extensions.yml"

# Kinds the service layer and the object cycle reference by name. This is the
# contract with upstream: these must survive any version bump.
REQUIRED_KINDS = {
    "SecurityZone",
    "SecurityGenericAddress",
    "SecurityGenericAddressGroup",
    "SecurityPolicy",
    "SecurityPolicyRule",
    "SecurityFirewall",
    "SecurityFirewallInterface",
    # The IPAM-backed address variants are the ones this project uses, so a
    # prefix referenced by a route policy and by a firewall rule is one object.
    "SecurityIPAMIPPrefix",
    "SecurityIPAMIPAddress",
}


def _load_yaml(path: str) -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def _kinds(schema: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for section in ("generics", "nodes"):
        found.update(f"{entry.get('namespace', '')}{entry.get('name', '')}" for entry in schema.get(section) or [])
    return found


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


# ---------------------------------------------------------------------------
# The contract with upstream
# ---------------------------------------------------------------------------


def test_adopted_schema_provides_every_kind_this_project_references() -> None:
    """A re-download that drops one of these breaks the service layer."""
    missing = REQUIRED_KINDS - _kinds(_load_yaml(SECURITY_SCHEMA))

    assert not missing, f"infrahub/security no longer provides: {sorted(missing)}"


def test_firewall_is_a_device_kind_so_no_firewall_role_is_needed() -> None:
    """Why `firewall` is absent from the DcimDevice role dropdown.

    SecurityFirewall inherits the DCIM device generics, so the perimeter
    firewall is its own kind rather than a DcimDevice carrying a role. If
    upstream ever changed that, the role would have to come back.
    """
    firewall = _node(_load_yaml(SECURITY_SCHEMA), "Security", "Firewall")
    inherits = set(firewall.get("inherit_from") or [])

    assert "DcimGenericDevice" in inherits
    assert "DcimPhysicalDevice" in inherits


def test_no_firewall_role_exists_in_the_device_dropdown() -> None:
    """The other half of the assertion above."""
    device = _extension_node(_load_yaml("schemas/dcim_extensions.yml"), "DcimDevice")
    choices = {choice["name"] for choice in _attributes(device)["role"].get("choices") or []}

    assert "firewall" not in choices


def test_address_book_is_polymorphic_via_a_generic() -> None:
    """The reason this project has no exactly-one-of check left to write.

    An earlier locally-authored model gave its address kind two optional
    relationships -- one to a prefix, one to an address -- and pushed "exactly
    one of these" to a future check, because a schema cannot express it.
    Upstream solves it properly: SecurityGenericAddress is a generic and each
    concrete address kind inherits it, so the choice is made by picking a kind
    rather than by leaving a field null.
    """
    schema = _load_yaml(SECURITY_SCHEMA)
    generic_names = {f"{g.get('namespace', '')}{g.get('name', '')}" for g in schema.get("generics") or []}

    assert "SecurityGenericAddress" in generic_names

    ipam_prefix = _node(schema, "Security", "IPAMIPPrefix")
    assert "SecurityGenericAddress" in (ipam_prefix.get("inherit_from") or [])
    # And it references an IPAM object rather than restating the CIDR.
    assert _relationships(ipam_prefix)["ip_prefix"]["peer"] == "IpamPrefix"


def test_policy_rules_carry_their_own_zone_pair_and_an_index() -> None:
    """Upstream puts the zone pair on the rule, not the policy.

    More general than a policy-per-zone-pair model, and it makes evaluation
    order unique per zone pair within a policy -- which is exactly the
    first-match behaviour a Junos zone pair needs.
    """
    rule = _node(_load_yaml(SECURITY_SCHEMA), "Security", "PolicyRule")
    relationships = _relationships(rule)

    assert relationships["source_zone"]["peer"] == "SecurityZone"
    assert relationships["destination_zone"]["peer"] == "SecurityZone"
    assert "index" in _attributes(rule)
    assert ["index__value", "source_zone", "destination_zone", "policy"] in (rule.get("uniqueness_constraints") or [])


# ---------------------------------------------------------------------------
# The local additions
# ---------------------------------------------------------------------------


def test_zone_gains_a_fabric_vrf_link() -> None:
    """Every tenant VRF's only route out is a default pointing at its zone.

    That pairing is what makes the firewall unavoidable rather than
    decorative, and without this relationship it lives only in a route-map
    comment.
    """
    zone = _extension_node(_load_yaml(SECURITY_EXTENSIONS), "SecurityZone")
    vrf = _relationships(zone)["vrf"]

    assert vrf["peer"] == "IpamVRF"
    assert vrf["cardinality"] == "one"
    assert vrf["optional"] is True


def test_zone_gains_a_bounded_trust_level() -> None:
    zone = _extension_node(_load_yaml(SECURITY_EXTENSIONS), "SecurityZone")
    trust_level = _attributes(zone)["trust_level"]

    assert trust_level["kind"] == "Number"
    assert trust_level["optional"] is True
    assert trust_level["parameters"] == {"min_value": 0, "max_value": 100}


def test_policy_rule_gains_the_unmanaged_object_guard() -> None:
    """What lets a generator reconcile a firewall that also has hand-written rules.

    A reconciling generator must delete rules with no service behind them, but
    the baseline -- the anti-spoofing deny at the head of every zone pair --
    is hand-written and must survive. Defaulting to false means everything
    already on the box loads as unmanaged, which is correct.
    """
    rule = _extension_node(_load_yaml(SECURITY_EXTENSIONS), "SecurityPolicyRule")
    managed = _attributes(rule)["managed_by_service"]

    assert managed["kind"] == "Boolean"
    assert managed["default_value"] is False
    assert managed["optional"] is False


def test_extensions_touch_only_the_four_intended_kinds() -> None:
    """Keeps local divergence from upstream small and reviewable.

    SecurityGenericAddress joined in cycle 023, for `book_index`: Junos writes
    the address book in authoring order and Infrahub stores none, so without it
    the rendered book is semantically identical to the device's and textually
    different. It is added on the generic so one attribute covers all six
    concrete address kinds.

    SecurityFirewall joined in cycle 026, for `tcp_mss`. The count is raised
    deliberately each time a kind is added -- never loosened to "at least" --
    so that growing the local divergence is a visible decision rather than a
    test quietly accommodating it.
    """
    extended = {node["kind"] for node in _extension_nodes(_load_yaml(SECURITY_EXTENSIONS))}

    assert extended == {
        "SecurityZone",
        "SecurityPolicyRule",
        "SecurityGenericAddress",
        "SecurityFirewall",
    }


def test_the_tcp_mss_clamp_is_optional_with_no_default() -> None:
    """C8. The pair that makes an unset clamp render nothing.

    `optional: true` alone is not enough: a default would still give every
    firewall a value, and the template would emit `mss 0` or an empty `flow`
    block on one that needs no clamp.
    """
    firewall = next(
        node for node in _extension_nodes(_load_yaml(SECURITY_EXTENSIONS)) if node["kind"] == "SecurityFirewall"
    )
    tcp_mss = next(a for a in firewall["attributes"] if a["name"] == "tcp_mss")

    assert tcp_mss["kind"] == "Number"
    assert tcp_mss["optional"] is True
    assert "default_value" not in tcp_mss


def test_the_address_book_index_is_optional_and_numeric() -> None:
    """Optional because `any` has none -- it is a keyword Junos never declares,
    so an absent index is also the signal to leave it out of the rendered book.
    """
    address = _extension_node(_load_yaml(SECURITY_EXTENSIONS), "SecurityGenericAddress")
    book_index = _attributes(address)["book_index"]

    assert book_index["kind"] == "Number"
    assert book_index["optional"] is True


def test_the_adopted_file_is_not_extended_in_place() -> None:
    """The adopted file must stay diffable against the published version.

    Upstream ships its own `extensions:` block (it adds `policy` to
    LocationGeneric), so the file having one is expected. What must not happen
    is a *local* addition being made there instead of in
    security_extensions.yml, because a re-download would silently drop it.
    Extending either of the two kinds we extend locally is the tell.
    """
    upstream_extended = {node["kind"] for node in _extension_nodes(_load_yaml(SECURITY_SCHEMA))}

    assert upstream_extended == {"LocationGeneric"}, (
        "the adopted file extends kinds upstream does not; local additions belong in schemas/security_extensions.yml"
    )


def test_marketplace_manifest_records_the_adopted_files() -> None:
    """Provenance has to be written down or the next re-sync is guesswork."""
    manifest = (REPO_ROOT / "schemas/MARKETPLACE.md").read_text(encoding="utf-8")

    for identifier in (
        "infrahub/security",
        "infrahub/cluster",
        "infrahub/circuit",
        "infrahub/tenancy",
    ):
        assert identifier in manifest, f"{identifier} missing from schemas/MARKETPLACE.md"

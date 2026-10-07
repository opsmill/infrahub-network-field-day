"""The service layer's event rules, and the one discipline that keeps them finite.

Every service kind expands on its branch through `triggers.yml`: a `created`
rule builds it, and per-field `updated` rules rebuild it -- or withdraw it,
because `status` is how every one of these kinds is decommissioned.

The rules are scoped to the generator's INPUTS, one per field, and the reason
is a loop. Each generator writes back to its own target (a status, the objects
it built, the block it allocated), so a bare `updated` rule -- or one watching
an output -- fires on the generator's own write and feeds every run into the
next. `status` is the one field that is both an input and an output; it
terminates only because every `_set_status` and every record step is guarded
on the current value, which the generator unit tests hold.

So this file pins three things:

- the exact set of watched fields per kind, so adding or dropping one is a
  deliberate edit here rather than an accident in YAML;
- that no rule watches a field its generator writes back;
- that every watched field exists on the kind AND is selected by the
  generator's own query, so a rule cannot watch something the run never reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from graphql import FieldNode, OperationDefinitionNode, parse

ROOT = Path(__file__).resolve().parents[2]

# The fields each generator reads from its target and acts on. Fields its query
# selects but whose value cannot change the output are deliberately absent: a
# segment's `tenant`/`fabric` and a placement's `tenant` appear only in logs.
# Keyed by kind and then by the generator the rules run: a kind may have more
# than one (specs/037-lab-dns-service adds `generate-dns-record` beside
# `generate-fabric-app`), and each is held to its own inputs and its own writes.
WATCHED: dict[str, dict[str, set[str]]] = {
    "ServiceAppAccess": {
        "generate-app-access": {
            "status",
            "ports",
            "application",
            "destination_vip",
            "source_site",
            "source_zone",
            "source_address",
        },
    },
    "ServiceNetworkSegment": {
        "generate-network-segment": {
            "status",
            "description",
            "vlan_id",
            "prefix_length",
            "vrf",
            "avd_tags",
            "subnet_pool",
            "vlan_pool",
        },
    },
    "ServiceFabricApp": {
        "generate-fabric-app": {"status", "exposed", "vip_block_size", "cluster"},
        # `vip_block` is an input HERE and an output of generate-fabric-app, which
        # is the point: the name can only be written once the block exists. It
        # cannot loop, because this generator writes an IpamIPAddress and never
        # the application (WRITE_BACKS below holds that).
        "generate-dns-record": {"status", "exposed", "vip_block", "dns_address"},
    },
    "ServiceTenantOnboarding": {"generate-tenant-onboarding": {"status", "description", "organization", "fabric"}},
    "ServiceServerPlacement": {
        "generate-server-placement": {"status", "description", "hostname", "server_role", "rack", "template"},
    },
    "ServiceFabricPeering": {"generate-fabric-peering": {"status", "cluster"}},
}

# What each generator WRITES onto its own target, besides `status`. Watching
# any of these turns a run into its own trigger.
WRITE_BACKS: dict[str, dict[str, set[str]]] = {
    "ServiceAppAccess": {"generate-app-access": {"granted_rules", "granted_source_prefixes"}},
    "ServiceNetworkSegment": {"generate-network-segment": {"subnet", "vlan", "svi"}},
    # `allowed_source_prefixes` is written by generate-app-access, not by this
    # kind's generator -- watching it would run generate-fabric-app per grant.
    #
    # `definition_pinned` is written once by the generator's pin step
    # (specs/035-application-catalogue), and `definition` is deliberately NOT
    # watched either: re-pointing an application at another catalogue entry is
    # an upgrade, which is its own reviewed change and not an automatic rebuild.
    "ServiceFabricApp": {
        "generate-fabric-app": {"vip_block", "vip_block_managed", "allowed_source_prefixes", "definition_pinned"},
        # Writes `fqdn` on an IpamIPAddress and nothing on the application.
        "generate-dns-record": set(),
    },
    "ServiceTenantOnboarding": {"generate-tenant-onboarding": {"evpn_tenant", "mac_vrf_vni_base"}},
    "ServiceServerPlacement": {"generate-server-placement": {"server"}},
    "ServiceFabricPeering": {"generate-fabric-peering": {"peerings"}},
}

PAIRS = [(kind, generator) for kind in sorted(WATCHED) for generator in sorted(WATCHED[kind])]


def _documents(relative: str) -> list[dict[str, Any]]:
    return [doc for doc in yaml.safe_load_all((ROOT / relative).read_text(encoding="utf-8")) if doc]


def _rules() -> list[dict[str, Any]]:
    return [
        rule
        for doc in _documents("triggers.yml")
        if doc.get("spec", {}).get("kind") == "CoreNodeTriggerRule"
        for rule in doc["spec"]["data"]
    ]


def _actions() -> dict[str, str]:
    return {
        action["name"]: action["generator"]
        for doc in _documents("triggers.yml")
        if doc.get("spec", {}).get("kind") == "CoreGeneratorAction"
        for action in doc["spec"]["data"]
    }


def _matched_field(rule: dict[str, Any]) -> str:
    (match,) = rule["matches"]["data"]
    return match.get("attribute_name") or match["relationship_name"]


def _updated_rules(kind: str, generator: str | None = None) -> list[dict[str, Any]]:
    return [
        r
        for r in _rules()
        if r["node_kind"] == kind
        and r["mutation_action"] == "updated"
        and (generator is None or _actions().get(r["action"]) == generator)
    ]


def _schema_fields(kind: str) -> set[str]:
    nodes: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "schemas").rglob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for node in document.get("nodes", []) + document.get("generics", []):
            nodes[f"{node['namespace']}{node['name']}"] = node
    node = nodes[kind]
    fields: set[str] = set()
    for owner in [node, *(nodes[g] for g in node.get("inherit_from", []) if g in nodes)]:
        fields |= {a["name"] for a in owner.get("attributes", [])}
        fields |= {r["name"] for r in owner.get("relationships", [])}
    return fields


def _query_target_fields(generator: str) -> set[str]:
    """The fields the generator's query selects on its `target:` node."""
    config = yaml.safe_load((ROOT / ".infrahub.yml").read_text(encoding="utf-8"))
    definition = next(g for g in config["generator_definitions"] if g["name"] == generator)
    query = next(q for q in config["queries"] if q["name"] == definition["query"])
    document = parse((ROOT / query["file_path"]).read_text(encoding="utf-8"))
    operation = next(d for d in document.definitions if isinstance(d, OperationDefinitionNode))
    target = next(
        s
        for s in operation.selection_set.selections
        if isinstance(s, FieldNode) and s.alias is not None and s.alias.value == "target"
    )

    def child(field: FieldNode, name: str) -> FieldNode:
        assert field.selection_set is not None
        return next(s for s in field.selection_set.selections if isinstance(s, FieldNode) and s.name.value == name)

    node = child(child(target, "edges"), "node")
    assert node.selection_set is not None
    return {s.name.value for s in node.selection_set.selections if isinstance(s, FieldNode)}


@pytest.mark.parametrize(("kind", "generator"), PAIRS)
def test_each_generator_watches_exactly_its_inputs(kind: str, generator: str) -> None:
    assert {_matched_field(r) for r in _updated_rules(kind, generator)} == WATCHED[kind][generator]


@pytest.mark.parametrize("kind", sorted(WATCHED))
def test_every_rule_of_a_kind_runs_a_generator_this_file_knows(kind: str) -> None:
    """A new generator on a kind has to be added to the tables above, not slipped in."""
    generators = {_actions()[r["action"]] for r in _rules() if r["node_kind"] == kind and r["action"] in _actions()}
    assert generators == set(WATCHED[kind])


@pytest.mark.parametrize(("kind", "generator"), PAIRS)
def test_status_is_watched_because_it_is_how_a_service_is_withdrawn(kind: str, generator: str) -> None:
    """The reason these rules exist: `decommissioning` set by hand must fire."""
    assert "status" in {_matched_field(r) for r in _updated_rules(kind, generator)}


@pytest.mark.parametrize(("kind", "generator"), PAIRS)
def test_no_rule_watches_what_its_generator_writes_back(kind: str, generator: str) -> None:
    watched = {_matched_field(r) for r in _updated_rules(kind, generator)}
    assert watched & WRITE_BACKS[kind][generator] == set(), f"{generator} watches its own output, which loops"


@pytest.mark.parametrize("kind", sorted(WATCHED))
def test_every_updated_rule_is_scoped_to_one_field_on_a_branch(kind: str) -> None:
    """A bare `updated` fires on the generator's own write-back."""
    for rule in _updated_rules(kind):
        assert rule["branch_scope"] == "other_branches", rule["name"]
        assert len(rule.get("matches", {}).get("data", [])) == 1, f"{rule['name']} is unscoped"


@pytest.mark.parametrize(("kind", "generator"), PAIRS)
def test_watched_fields_exist_and_are_read_by_the_generator(kind: str, generator: str) -> None:
    read = _query_target_fields(generator)
    schema = _schema_fields(kind)
    for field in WATCHED[kind][generator]:
        assert field in schema, f"{kind} has no field {field!r}"
        assert field in read, f"{generator}'s query never selects {field!r}, so watching it rebuilds nothing"


@pytest.mark.parametrize("kind", sorted(WATCHED))
def test_each_service_kind_still_builds_on_creation(kind: str) -> None:
    assert [
        r
        for r in _rules()
        if r["node_kind"] == kind and r["mutation_action"] == "created" and r["action"] in _actions()
    ]


def test_rule_names_are_unique() -> None:
    names = [r["name"] for r in _rules()]
    assert len(names) == len(set(names))


def test_a_catalogue_pin_is_not_an_input() -> None:
    """The pin is taken once, on creation. Watching either field would re-pin or loop."""
    watched = {_matched_field(r) for r in _updated_rules("ServiceFabricApp")}
    assert "definition" not in watched, "re-pointing an application is an upgrade, not a rebuild"
    assert "definition_pinned" not in watched, "the generator writes it; watching it loops"


def test_no_rule_names_the_catalogue_entry() -> None:
    """An entry is data, not a service: no generator sits beneath it."""
    assert [r["name"] for r in _rules() if r["node_kind"] == "ServiceApplicationDefinition"] == []


def _group_actions() -> dict[str, dict[str, Any]]:
    return {
        action["name"]: action
        for doc in _documents("triggers.yml")
        if doc.get("spec", {}).get("kind") == "CoreGroupAction"
        for action in doc["spec"]["data"]
    }


def _group_rules() -> list[dict[str, Any]]:
    return [
        rule
        for doc in _documents("triggers.yml")
        if doc.get("spec", {}).get("kind") == "CoreGroupTriggerRule"
        for rule in doc["spec"]["data"]
    ]


def _generator_group(generator: str) -> str:
    config = yaml.safe_load((ROOT / ".infrahub.yml").read_text(encoding="utf-8"))
    return next(g for g in config["generator_definitions"] if g["name"] == generator)["targets"]


def test_a_grant_from_any_client_joins_the_generator_group_on_creation() -> None:
    """The portal adds the membership itself; the API, the UI and the MCP server do not.

    Infrahub refuses a generator run against a node outside the target group, so a
    grant without the membership is never built.
    """
    generator = _actions()["run-app-access-generator"]
    group = _generator_group(generator)
    rules = [
        r
        for r in _rules()
        if r["node_kind"] == "ServiceAppAccess"
        and r["mutation_action"] == "created"
        and r["action"] in _group_actions()
    ]
    assert len(rules) == 1
    assert rules[0]["branch_scope"] == "other_branches"
    action = _group_actions()[rules[0]["action"]]
    assert action["member_action"] == "add_member"
    assert action["group"] == group


def test_the_generator_runs_when_a_grant_becomes_a_member_of_its_group() -> None:
    generator = _actions()["run-app-access-generator"]
    group = _generator_group(generator)
    rules = [r for r in _group_rules() if r["group"] == group]
    assert len(rules) == 1
    assert rules[0]["member_update"] == "added"
    assert rules[0]["branch_scope"] == "other_branches"
    assert _actions()[rules[0]["action"]] == generator


def test_group_rules_never_name_a_deployment_or_monitoring_group() -> None:
    """Nothing may generate from Deployment* or Monitoring* state: it closes a loop."""
    for rule in _group_rules():
        assert not rule["group"].startswith(("deployment", "monitoring")), rule["name"]


def test_the_group_membership_write_is_not_watched_by_any_updated_rule() -> None:
    """Membership is not a field of the grant, so the existing field rules cannot see it."""
    assert "member_of_groups" not in {_matched_field(r) for r in _updated_rules("ServiceAppAccess")}


def test_every_rule_name_is_unique_across_node_and_group_rules() -> None:
    names = [r["name"] for r in _rules()] + [r["name"] for r in _group_rules()]
    assert len(names) == len(set(names))

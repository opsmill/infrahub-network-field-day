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
WATCHED: dict[str, set[str]] = {
    "ServiceAppAccess": {
        "status",
        "ports",
        "application",
        "destination_vip",
        "source_site",
        "source_zone",
        "source_address",
    },
    "ServiceNetworkSegment": {
        "status",
        "description",
        "vlan_id",
        "prefix_length",
        "vrf",
        "avd_tags",
        "subnet_pool",
        "vlan_pool",
    },
    "ServiceFabricApp": {"status", "exposed", "vip_block_size", "cluster"},
    "ServiceTenantOnboarding": {"status", "description", "organization", "fabric"},
    "ServiceServerPlacement": {"status", "description", "hostname", "server_role", "rack", "template"},
    "ServiceFabricPeering": {"status", "cluster"},
}

# What each generator WRITES onto its own target, besides `status`. Watching
# any of these turns a run into its own trigger.
WRITE_BACKS: dict[str, set[str]] = {
    "ServiceAppAccess": {"granted_rules", "granted_source_prefixes"},
    "ServiceNetworkSegment": {"subnet", "vlan", "svi"},
    # `allowed_source_prefixes` is written by generate-app-access, not by this
    # kind's generator -- watching it would run generate-fabric-app per grant.
    "ServiceFabricApp": {"vip_block", "vip_block_managed", "allowed_source_prefixes"},
    "ServiceTenantOnboarding": {"evpn_tenant", "mac_vrf_vni_base"},
    "ServiceServerPlacement": {"server"},
    "ServiceFabricPeering": {"peerings"},
}


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


def _updated_rules(kind: str) -> list[dict[str, Any]]:
    return [r for r in _rules() if r["node_kind"] == kind and r["mutation_action"] == "updated"]


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


@pytest.mark.parametrize("kind", sorted(WATCHED))
def test_each_service_kind_watches_exactly_its_inputs(kind: str) -> None:
    assert {_matched_field(r) for r in _updated_rules(kind)} == WATCHED[kind]


@pytest.mark.parametrize("kind", sorted(WATCHED))
def test_status_is_watched_because_it_is_how_a_service_is_withdrawn(kind: str) -> None:
    """The reason these rules exist: `decommissioning` set by hand must fire."""
    assert "status" in {_matched_field(r) for r in _updated_rules(kind)}


@pytest.mark.parametrize("kind", sorted(WATCHED))
def test_no_rule_watches_what_its_generator_writes_back(kind: str) -> None:
    watched = {_matched_field(r) for r in _updated_rules(kind)}
    assert watched & WRITE_BACKS[kind] == set(), f"{kind} watches its own output, which loops"


@pytest.mark.parametrize("kind", sorted(WATCHED))
def test_every_updated_rule_is_scoped_to_one_field_on_a_branch(kind: str) -> None:
    """A bare `updated` fires on the generator's own write-back."""
    for rule in _updated_rules(kind):
        assert rule["branch_scope"] == "other_branches", rule["name"]
        assert len(rule.get("matches", {}).get("data", [])) == 1, f"{rule['name']} is unscoped"


@pytest.mark.parametrize("kind", sorted(WATCHED))
def test_watched_fields_exist_and_are_read_by_the_generator(kind: str) -> None:
    rules = _updated_rules(kind) + [r for r in _rules() if r["node_kind"] == kind and r["mutation_action"] == "created"]
    generators = {_actions()[r["action"]] for r in rules}
    assert len(generators) == 1, f"{kind}'s rules run more than one generator: {generators}"
    (generator,) = generators

    read = _query_target_fields(generator)
    schema = _schema_fields(kind)
    for field in WATCHED[kind]:
        assert field in schema, f"{kind} has no field {field!r}"
        assert field in read, f"{generator}'s query never selects {field!r}, so watching it rebuilds nothing"


@pytest.mark.parametrize("kind", sorted(WATCHED))
def test_each_service_kind_still_builds_on_creation(kind: str) -> None:
    assert [r for r in _rules() if r["node_kind"] == kind and r["mutation_action"] == "created"]


def test_rule_names_are_unique() -> None:
    names = [r["name"] for r in _rules()]
    assert len(names) == len(set(names))

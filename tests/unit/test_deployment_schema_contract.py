"""Contract tests for the deployment state kinds added in cycle 029.

``DeploymentState`` records whether a device matches the configuration Infrahub
renders for it. Three properties of that model are load-bearing, and none of
them fails loudly when broken -- which is why they are pinned here rather than
left to review.

* **Nothing may generate from a deployment kind.** Writing state onto a device
  emits an event, ``triggers.yml`` turns node events into generator runs, a
  generator run regenerates artifacts, and a moved artifact is what the
  reconciler acts on. That loop stays open today only because no trigger happens
  to watch these kinds -- by accident, not by design.
  ``test_nothing_generates_from_a_deployment_kind`` and
  ``test_no_infrahub_yml_entry_targets_a_deployment_kind`` are what turn the
  accident into a rule.

* **``on_delete`` must not appear on the device relationship.** Its only value,
  ``cascade``, deletes the *peer* when this node is deleted -- so on
  ``DeploymentState.device`` it would mean "deleting a deployment record deletes
  the switch". ``infrahubctl schema check`` accepts the line without complaint.

* **The device relationship peers the generic and declares no identifier.** The
  four device kinds are siblings, so a relationship naming ``DcimDevice`` is
  invisible to every fabric switch -- the same failure that hid the cabling
  plan's missing cables for months. And a one-way relationship that declares an
  ``identifier`` is exactly what
  ``test_dcim_schema_contract.py::test_every_identifier_is_two_sided_and_agrees``
  hunts, so declaring none is deliberate, matching ``AvdArtifact.device``.

THE MEASUREMENT BEHIND ``device`` BEING OPTIONAL: an ``human_friendly_id`` or
uniqueness constraint over a relationship requires that relationship to be
mandatory, and a mandatory ``device`` makes any device that has ever held a
record permanently undeletable -- Infrahub keeps refusing the delete *after* the
record is gone, naming a record that no longer exists. Identity therefore comes
from a copied ``name`` attribute and the relationship stays optional.
``test_device_relationship_is_optional_and_identity_does_not_depend_on_it``
pins the pair together, because reverting either half alone silently restores
the trap.

This file reads only ``schemas/deployment.yml``, ``triggers.yml`` and
``.infrahub.yml`` from the repository root. It must never read anything under
``specs/`` -- ``test_unit_test_contracts.py`` walks the AST of every unit test
and fails on it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEPLOYMENT_NAMESPACE = "Deployment"
SCHEMA_PATH = Path("schemas/deployment.yml")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load(relative: str) -> Any:
    return yaml.safe_load((_repo_root() / relative).read_text(encoding="utf-8"))


def _deployment_kinds() -> set[str]:
    schema = _load(str(SCHEMA_PATH))
    return {f"{node['namespace']}{node['name']}" for node in schema["nodes"]}


def _node(name: str) -> dict[str, Any]:
    schema = _load(str(SCHEMA_PATH))
    for node in schema["nodes"]:
        if node["name"] == name:
            return node
    raise AssertionError(f"{name} is not defined in {SCHEMA_PATH}")


def _relationship(node: dict[str, Any], name: str) -> dict[str, Any]:
    for rel in node.get("relationships", []):
        if rel["name"] == name:
            return rel
    raise AssertionError(f"relationship {name} missing from {node['name']}")


def _documents(relative: str) -> list[dict[str, Any]]:
    text = (_repo_root() / relative).read_text(encoding="utf-8")
    return [doc for doc in yaml.safe_load_all(text) if doc]


def test_the_two_kinds_exist_under_the_deployment_namespace() -> None:
    assert _deployment_kinds() == {"DeploymentState", "DeploymentDiffFile"}


def test_nothing_generates_from_a_deployment_kind() -> None:
    """No trigger rule may watch a deployment kind.

    This is the test that fails when someone closes the feedback loop. It names
    the offending rule rather than only reporting a count, because the point is
    to tell the next person which line to remove.
    """
    kinds = _deployment_kinds()
    offenders = [
        f"{rule.get('name')} -> node_kind: {rule.get('node_kind')}"
        for document in _documents("triggers.yml")
        if document.get("spec", {}).get("kind") == "CoreNodeTriggerRule"
        for rule in document["spec"].get("data", [])
        if rule.get("node_kind") in kinds
    ]

    assert offenders == [], (
        f"A trigger rule watches a deployment kind, which closes the loop this model exists to keep open: {offenders}"
    )


def test_no_infrahub_yml_entry_targets_a_deployment_kind() -> None:
    """No generator, artifact definition or check may take a deployment kind."""
    kinds = _deployment_kinds()
    config = _load(".infrahub.yml")
    offenders = [
        f"{section}: {entry.get('name')} references {kind}"
        for section in ("generator_definitions", "artifact_definitions", "check_definitions")
        for entry in config.get(section) or []
        for kind in kinds
        if kind in yaml.safe_dump(entry)
    ]

    assert offenders == [], f"An .infrahub.yml entry targets a deployment kind: {offenders}"


def test_no_on_delete_anywhere_in_the_deployment_schema() -> None:
    """``cascade`` on ``DeploymentState.device`` would delete the switch."""
    schema_text = (_repo_root() / SCHEMA_PATH).read_text(encoding="utf-8")
    keys = [line for line in schema_text.splitlines() if line.strip().startswith("on_delete:")]
    assert keys == [], f"on_delete must not appear in {SCHEMA_PATH}: {keys}"


def test_device_relationship_peers_the_generic_and_declares_no_identifier() -> None:
    device = _relationship(_node("State"), "device")

    assert device["peer"] == "DcimGenericDevice", (
        "The four device kinds are siblings; a relationship naming a concrete kind is invisible to the other three."
    )
    assert device["cardinality"] == "one"
    assert "identifier" not in device, (
        "A one-way relationship that declares an identifier fails "
        "test_dcim_schema_contract.py::test_every_identifier_is_two_sided_and_agrees."
    )


def test_device_relationship_is_optional_and_identity_does_not_depend_on_it() -> None:
    """The two halves of the deletion fix, pinned together.

    Making ``device`` mandatory again, or moving identity back onto it, each
    restores a state where any device holding a record can never be deleted.
    """
    state = _node("State")
    device = _relationship(state, "device")

    assert device.get("optional") is True

    identity_paths = list(state.get("human_friendly_id", [])) + [
        field for constraint in state.get("uniqueness_constraints", []) for field in constraint
    ]
    assert identity_paths, "DeploymentState must still be identifiable"
    assert all(path.startswith("name__value") for path in identity_paths), (
        "Identity must not traverse the device relationship: Infrahub requires a "
        f"relationship used for identity to be mandatory. Found {identity_paths}"
    )


def test_both_kinds_are_branch_agnostic_and_generate_no_profile() -> None:
    """Deployment state is a fact about the physical world, not about a branch.

    Setting this on only one of the two kinds is the failure worth catching: a
    record shared by every branch owning a child visible on one is the worst of
    both.
    """
    for name in ("State", "DiffFile"):
        node = _node(name)
        assert node.get("branch") == "agnostic", f"{name} must be branch agnostic"
        assert node.get("generate_profile") is False, f"{name} must not generate a profile"


def test_the_diff_file_is_a_file_object_owned_by_exactly_one_record() -> None:
    diff = _node("DiffFile")
    state_rel = _relationship(diff, "state")
    last_diff = _relationship(_node("State"), "last_diff")

    assert diff.get("inherit_from") == ["CoreFileObject"]
    assert diff.get("human_friendly_id") == ["state__name__value"], (
        "An HFID path traverses one relationship and then names an attribute. "
        "state__device__name__value is two hops and the server rejects it, which "
        "is why the parent record carries the device name."
    )
    assert diff.get("uniqueness_constraints") == [["state"]]
    assert state_rel["kind"] == "Parent" and state_rel["optional"] is False
    assert last_diff["kind"] == "Component"
    assert state_rel["identifier"] == last_diff["identifier"]


def test_suspend_is_an_instruction_and_status_is_an_observation() -> None:
    """Suspension must not collapse into the status dropdown.

    Status says what the device is doing; suspension says what the operator told
    the reconciler. Merging them loses what the device was doing at the moment
    someone took it out of the loop.
    """
    attributes = {attr["name"]: attr for attr in _node("State")["attributes"]}

    assert attributes["suspend"]["kind"] == "Boolean"
    assert attributes["suspend"]["default_value"] is False
    assert attributes["suspend_reason"]["optional"] is True

    choices = {choice["name"] for choice in attributes["status"]["choices"]}
    assert choices == {"never_deployed", "in_sync", "pending", "drifted", "failed"}
    assert not any("suspend" in choice for choice in choices)


def test_confirmation_and_check_timestamps_are_separate_fields() -> None:
    """A stale confirmation must be distinguishable from a dead reconciler.

    With only ``last_confirmed_at``, "this device is fine" and "the loop stopped
    running a week ago" read identically.
    """
    attributes = {attr["name"]: attr for attr in _node("State")["attributes"]}

    for field in ("last_confirmed_at", "last_checked_at", "last_attempt_at"):
        assert attributes[field]["kind"] == "DateTime"
        assert attributes[field]["optional"] is True

    assert attributes["last_error"]["kind"] == "TextArea", "device errors are multi-line"


def test_the_menu_entry_and_include_in_menu_do_not_both_claim_the_kind() -> None:
    """`menus/menu.yml` states the rule in its own header: a node that appears
    in that file must set ``include_in_menu: false`` on its schema, or it shows
    up in the sidebar twice.

    Cycle 029 shipped ``DeploymentState`` with ``include_in_menu: true`` and no
    curated entry, so the kind was reachable while the menu cycle was still
    outstanding. Cycle 030 added the entry and flipped the flag. This test pins
    the pair together: reverting either half alone produces either a duplicate
    entry or a kind reachable only by UUID.
    """
    menu = yaml.safe_load((_repo_root() / "menus/menu.yml").read_text(encoding="utf-8"))

    def _kinds(items: list[dict[str, Any]]) -> set[str]:
        found: set[str] = set()
        for item in items:
            if item.get("kind"):
                found.add(item["kind"])
            found |= _kinds((item.get("children") or {}).get("data", []))
        return found

    in_menu = _kinds(menu["spec"]["data"])
    assert "DeploymentState" in in_menu, "DeploymentState must have a curated menu entry"
    assert "DeploymentDiffFile" not in in_menu, "the diff file is reached through its parent record"

    assert _node("State").get("include_in_menu") is False
    assert _node("DiffFile").get("include_in_menu") is False

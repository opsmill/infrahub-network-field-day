"""What a reviewer sees in the UI: labels, field order, descriptions, and which checks run.

None of this fails at load time when it regresses. A kind without a
`display_label` loads cleanly and renders every row, relationship picker and
proposed-change diff as `Kind(ID: <uuid>)`; a check that can only skip still
reports green on every proposed change. So the choices are pinned here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parents[2]


def _load(path: str) -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def _load_all(path: str) -> list[dict[str, Any]]:
    return [doc for doc in yaml.safe_load_all((REPO_ROOT / path).read_text(encoding="utf-8")) if doc]


def _node(path: str, namespace: str, name: str, section: str = "nodes") -> dict[str, Any]:
    for node in _load(path).get(section) or []:
        if node.get("namespace") == namespace and node.get("name") == name:
            return node
    raise AssertionError(f"{namespace}{name} not declared in {path}")


def _fields(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["name"]: f for f in [*(node.get("attributes") or []), *(node.get("relationships") or [])]}


# ---------------------------------------------------------------------------
# Display labels
# ---------------------------------------------------------------------------

DISPLAY_LABELS = [
    ("schemas/security_extensions.yml", "Security", "PolicyRule", "{{ name__value }}"),
    ("schemas/objects/objects.yml", "Avd", "HostvarFile", "{{ file_name__value }}"),
    ("schemas/objects/objects.yml", "Avd", "StructuredConfigFile", "{{ file_name__value }}"),
    ("schemas/service/kubernetes_services.yml", "Service", "FabricAppValuesFile", "{{ file_name__value }}"),
]


@pytest.mark.parametrize(("path", "namespace", "name", "label"), DISPLAY_LABELS, ids=str)
def test_kinds_a_reviewer_sees_in_diffs_have_a_display_label(path: str, namespace: str, name: str, label: str) -> None:
    assert _node(path, namespace, name).get("display_label") == label


def test_the_adopted_security_file_does_not_carry_the_labels() -> None:
    """The labels are local additions, so they live in the extensions file.

    `schemas/security/security.yml` is kept byte-identical to the marketplace
    (schemas/MARKETPLACE.md); a label added there would be dropped silently by
    the next re-download.
    """
    upstream_rule = _node("schemas/security/security.yml", "Security", "PolicyRule")

    assert "display_label" not in upstream_rule
    assert upstream_rule.get("description") == "Policy rule"


def test_the_firewall_is_not_redeclared() -> None:
    """Re-declaring SecurityFirewall for a description costs more than it buys.

    It needs a copy of upstream's `inherit_from` (the server refuses the node
    without one), and `infrahubctl protocols` does not merge re-declarations, so
    the generated SecurityFirewall protocol would lose `role` and `policy`.
    """
    local = {(n.get("namespace"), n.get("name")) for n in _load("schemas/security_extensions.yml").get("nodes") or []}

    assert ("Security", "Firewall") not in local


def test_the_policy_rule_redeclaration_adds_only_presentation_and_identity() -> None:
    local = _node("schemas/security_extensions.yml", "Security", "PolicyRule")

    assert set(local) == {"name", "namespace", "description", "display_label", "human_friendly_id"}


# ---------------------------------------------------------------------------
# Field order and descriptions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "namespace", "name", "section"),
    [
        ("schemas/service/service.yml", "Service", "Generic", "generics"),
        ("schemas/monitoring.yml", "Monitoring", "Profile", "nodes"),
        ("schemas/monitoring.yml", "Monitoring", "Collector", "nodes"),
        ("schemas/deployment.yml", "Deployment", "State", "nodes"),
    ],
    ids=str,
)
def test_name_comes_before_every_relationship(path: str, namespace: str, name: str, section: str) -> None:
    """A detail page opens on the name, not on whichever relationship weighs least."""
    node = _node(path, namespace, name, section)
    name_weight = _fields(node)["name"]["order_weight"]

    assert all(name_weight < rel["order_weight"] for rel in node.get("relationships") or [])
    assert name_weight <= 100


def test_the_concrete_service_kinds_keep_their_relationships_above_the_name() -> None:
    """ServiceFabricApp and ServiceAppAccess inherit `name` from ServiceGeneric.

    Their own relationships sit at 9xx, so the generic's name has to weigh less
    than all of them for the name to lead.
    """
    name_weight = _fields(_node("schemas/service/service.yml", "Service", "Generic", "generics"))["name"][
        "order_weight"
    ]
    for path, kind in (
        ("schemas/service/kubernetes_services.yml", "FabricApp"),
        ("schemas/service/access_services.yml", "AppAccess"),
    ):
        node = _node(path, "Service", kind)
        assert all(name_weight < f["order_weight"] for f in _fields(node).values() if "order_weight" in f), kind


@pytest.mark.parametrize(
    ("path", "namespace", "name", "field", "section"),
    [
        ("schemas/service/service.yml", "Service", "Generic", "status", "generics"),
        ("schemas/service/access_services.yml", "Service", "AppAccess", "requester", "nodes"),
        ("schemas/service/access_services.yml", "Service", "AppAccess", "ports", "nodes"),
    ],
    ids=str,
)
def test_fields_a_requester_fills_are_described(path: str, namespace: str, name: str, field: str, section: str) -> None:
    description = _fields(_node(path, namespace, name, section))[field].get("description") or ""

    assert description
    # Infrahub caps a description at 128 characters and refuses the schema otherwise.
    assert len(description) <= 128


def test_the_ports_description_matches_what_the_generator_does() -> None:
    """Empty ports takes the application's advertised services.

    The description used to say an empty list was rejected, which sent a
    requester hunting for port numbers the generator would have derived.
    """
    description = _fields(_node("schemas/service/access_services.yml", "Service", "AppAccess"))["ports"]["description"]

    assert "advertised" in description
    assert "rejected" not in description


def test_the_policy_rule_has_a_real_description() -> None:
    description = _node("schemas/security_extensions.yml", "Security", "PolicyRule")["description"]

    assert len(description) <= 128
    assert description.lower() != "policy rule"


# ---------------------------------------------------------------------------
# CloudVision: not registered in a lab that has none
# ---------------------------------------------------------------------------


def test_cv_config_validation_is_not_registered() -> None:
    """It could only ever log a skip and pass here, which reads as a validation."""
    names = {entry["name"] for entry in _load(".infrahub.yml").get("check_definitions") or []}

    assert "cv-config-validation" not in names
    assert names, "check_definitions must not be empty"


def test_repository_checks_does_not_recreate_it() -> None:
    """`invoke load` would otherwise re-create on every run what the import deletes."""
    for document in _load_all("repository_checks.yml"):
        if document.get("spec", {}).get("kind") == "CoreCheckDefinition":
            assert all(row["name"] != "cv-config-validation" for row in document["spec"]["data"])


def test_the_check_code_is_kept_for_re_enabling() -> None:
    assert (REPO_ROOT / "checks/cv_config_check.py").is_file()
    queries = {entry["name"] for entry in _load(".infrahub.yml").get("queries") or []}
    assert "cv_config_check" in queries


def test_no_check_definition_carries_a_description() -> None:
    """The SDK's check-definition config forbids extra keys; one fails the import."""
    for entry in _load(".infrahub.yml").get("check_definitions") or []:
        assert "description" not in entry, entry["name"]


def test_the_menu_has_no_cloudvision_workspaces_entry() -> None:
    text = (REPO_ROOT / "menus/menu.yml").read_text(encoding="utf-8")

    assert "kind: CloudvisionWorkspace" not in text

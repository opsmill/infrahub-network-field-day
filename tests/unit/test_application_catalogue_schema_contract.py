"""Schema contract for the application catalogue (specs/035-application-catalogue).

`ServiceApplicationDefinition` is a catalogue entry: platform-owned data that a
requested application is pinned from. It is deliberately NOT a service instance,
which is why it lives in `schemas/catalogue/` rather than `schemas/service/`:
the service-layer contract tests iterate `schemas/service/*.yml` and require
every node there to inherit `ServiceGeneric` and `GeneratorTarget`.

What these tests guard is what fails quietly:

- a JSON attribute on the entry, because Infrahub 1.10.6 answers HTTP 500 for a
  JSON key containing a dot or a slash and every Kubernetes label has both;
- `requestable` defaulting to true, which would put an entry in the portal
  picker the moment someone forgot to say otherwise;
- `definition` becoming mandatory, which Infrahub refuses against existing data;
- the chart fields on the application becoming optional, which would let a
  request through with half a chart.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE_SCHEMA = ROOT / "schemas/catalogue/application_catalogue.yml"
APP_SCHEMA = ROOT / "schemas/service/kubernetes_services.yml"
KIND = "ServiceApplicationDefinition"


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _node(path: Path, name: str) -> dict[str, Any]:
    return next(node for node in _load(path)["nodes"] if node["name"] == name)


def _fields(node: dict[str, Any], group: str) -> dict[str, dict[str, Any]]:
    return {field["name"]: field for field in node.get(group, [])}


@pytest.fixture(scope="module")
def definition() -> dict[str, Any]:
    return _node(CATALOGUE_SCHEMA, "ApplicationDefinition")


@pytest.fixture(scope="module")
def app() -> dict[str, Any]:
    return _node(APP_SCHEMA, "FabricApp")


def test_the_kind_lives_in_the_catalogue_directory_not_the_service_directory(definition: dict[str, Any]) -> None:
    assert definition["namespace"] == "Service"
    assert CATALOGUE_SCHEMA.parent.name == "catalogue"
    assert not any(
        "ApplicationDefinition" in path.read_text(encoding="utf-8")
        for path in (ROOT / "schemas/service").glob("*.yml")
        if path != APP_SCHEMA
    )


def test_the_entry_is_not_a_service_instance_or_a_generator_target(definition: dict[str, Any]) -> None:
    inherits = set(definition.get("inherit_from") or [])
    assert not inherits & {"ServiceGeneric", "GeneratorTarget", "CoreArtifactTarget"}, inherits


def test_no_attribute_of_the_entry_is_json(definition: dict[str, Any]) -> None:
    """HTTP 500 on object load for a key with a dot or slash; see objects/36."""
    kinds = {name: field["kind"] for name, field in _fields(definition, "attributes").items()}
    assert "JSON" not in kinds.values(), kinds


def test_default_values_is_text_not_json(definition: dict[str, Any]) -> None:
    attributes = _fields(definition, "attributes")
    assert attributes["default_values"]["kind"] == "TextArea"
    assert attributes["default_values"]["optional"] is True


def test_the_entry_carries_the_decided_attributes(definition: dict[str, Any]) -> None:
    attributes = _fields(definition, "attributes")
    expected = {
        "name",
        "title",
        "description",
        "chart_repository",
        "chart_name",
        "chart_version",
        "default_values",
        "default_vip_block_size",
        "default_service_selector",
        "requestable",
        "status",
    }
    assert expected <= set(attributes), expected - set(attributes)
    for mandatory in ("name", "title", "chart_repository", "chart_name", "chart_version"):
        assert attributes[mandatory]["optional"] is False, mandatory
    assert attributes["default_service_selector"]["kind"] == "List"


def test_an_entry_is_never_requestable_by_accident(definition: dict[str, Any]) -> None:
    requestable = _fields(definition, "attributes")["requestable"]
    assert requestable["kind"] == "Boolean"
    assert requestable["default_value"] is False


def test_status_is_active_or_deprecated_and_defaults_active(definition: dict[str, Any]) -> None:
    status = _fields(definition, "attributes")["status"]
    assert status["kind"] == "Dropdown"
    assert [choice["name"] for choice in status["choices"]] == ["active", "deprecated"]
    assert status["default_value"] == "active"


def test_the_block_size_default_is_bounded_like_the_applications_own(
    definition: dict[str, Any], app: dict[str, Any]
) -> None:
    own = _fields(app, "attributes")["vip_block_size"]["parameters"]
    default = _fields(definition, "attributes")["default_vip_block_size"]
    assert default["kind"] == "Number"
    assert default["parameters"] == own
    assert default["default_value"] == 28


def test_the_entry_is_named_and_displayed_by_what_a_person_reads(definition: dict[str, Any]) -> None:
    attributes = _fields(definition, "attributes")
    assert attributes["name"]["unique"] is True
    assert definition["human_friendly_id"] == ["name__value"]
    assert definition["display_label"] == "{{ title__value }}"
    assert definition["uniqueness_constraints"] == [["name__value"]]


def test_the_entry_is_reached_through_the_menu_only(definition: dict[str, Any]) -> None:
    assert definition["include_in_menu"] is False


def test_the_entrys_defaults_never_cascade(definition: dict[str, Any]) -> None:
    relationships = _fields(definition, "relationships")
    advertised = relationships["default_advertised_services"]
    assert advertised["peer"] == "SecurityService"
    assert advertised["cardinality"] == "many"
    assert advertised["on_delete"] == "no-action"
    assert relationships["applications"]["on_delete"] == "no-action"


def test_the_application_definition_link_is_optional_and_never_cascades(app: dict[str, Any]) -> None:
    link = _fields(app, "relationships")["definition"]
    assert link["peer"] == KIND
    assert link["cardinality"] == "one"
    assert link["optional"] is True, "Infrahub refuses a mandatory relationship against existing data"
    assert link["on_delete"] == "no-action"


def test_the_inverse_names_the_same_identifier(definition: dict[str, Any], app: dict[str, Any]) -> None:
    forward = _fields(app, "relationships")["definition"]
    inverse = _fields(definition, "relationships")["applications"]
    assert inverse["peer"] == "ServiceFabricApp"
    assert inverse["identifier"] == forward["identifier"]


def test_the_pin_marker_is_an_optional_boolean_off_by_default(app: dict[str, Any]) -> None:
    marker = _fields(app, "attributes")["definition_pinned"]
    assert marker["kind"] == "Boolean"
    assert marker["optional"] is True
    assert marker["default_value"] is False


def test_the_chart_fields_stay_mandatory_together(app: dict[str, Any]) -> None:
    attributes = _fields(app, "attributes")
    for name in ("chart_repository", "chart_name", "chart_version"):
        assert attributes[name]["optional"] is False, name


def test_the_catalogue_directory_loads_with_the_rest_of_schemas() -> None:
    """`infrahubctl schema load schemas` recurses; a file outside `schemas/` would not load."""
    assert CATALOGUE_SCHEMA.is_relative_to(ROOT / "schemas")
    assert _load(CATALOGUE_SCHEMA)["version"] == "1.0"

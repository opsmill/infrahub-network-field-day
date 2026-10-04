"""The portal's application picker (specs/035-application-catalogue).

`backstage/catalog/exposed-app-with-access.yaml` used to ask for a chart
repository, name, version, ports, a block size, a selector and a values file.
That is the platform team's decision, so it now asks for ONE entry from the
application catalogue. The failures worth catching are the quiet ones:

- a leftover chart field, which lets a requester override the platform's choice;
- a picker that would offer the lab's infrastructure applications;
- a picker filtering on two tags, which Backstage ORs and so offers too much;
- the entry read without the requestable and active conditions, which turns the
  server-side control back into a convenience;
- a values upload step, which would let the portal write what the generator owns.

None of it can be built or rendered here: the portal build and a real request
are lab-phase checks.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "backstage/catalog/exposed-app-with-access.yaml"
DEV_CONFIG = REPO / "backstage/app-config.yaml"
DOCKER_CONFIG = REPO / "backstage/app-config.docker.yaml"
PROVIDER = REPO / "backstage/plugins/infrahub-backend/src/provider.ts"

REMOVED_FIELDS = (
    "chart_repository",
    "chart_name",
    "chart_version",
    "advertised_services",
    "service_selector",
    "vip_block_size",
    "values_file_content",
)
KEPT_FIELDS = ("app_name", "description", "namespace_name", "cluster", "vrf", "owner")
EDGE = "steps.read_definition.output.data.ServiceApplicationDefinition.edges[0].node"


@pytest.fixture(scope="module")
def template() -> dict[str, Any]:
    return yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _pages(template: dict[str, Any]) -> list[dict[str, Any]]:
    return template["spec"]["parameters"]


def _properties(template: dict[str, Any]) -> dict[str, Any]:
    return {name: prop for page in _pages(template) for name, prop in page["properties"].items()}


def _steps(template: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {step["id"]: step for step in template["spec"]["steps"]}


def test_the_form_no_longer_asks_for_anything_about_the_chart(template: dict[str, Any]) -> None:
    properties = _properties(template)
    leaked = [field for field in REMOVED_FIELDS if field in properties]
    assert not leaked, f"{leaked} would let a requester override the platform's choice"
    required = {name for page in _pages(template) for name in page.get("required", [])}
    assert not required & set(REMOVED_FIELDS)


def test_the_form_keeps_what_is_the_requesters(template: dict[str, Any]) -> None:
    properties = _properties(template)
    for field in (*KEPT_FIELDS, "source_site", "justification", "request_reference"):
        assert field in properties, field
    assert properties["cluster"]["default"] == "otternet"
    assert properties["vrf"]["default"] == "K8S_PROD"
    assert properties["owner"]["default"] == "acme"
    assert properties["source_site"]["default"] == "branch-office"


def test_the_form_asks_for_ten_things_none_of_them_about_charts(template: dict[str, Any]) -> None:
    """SC-001: app name, description, namespace, cluster, VRF, owner, the picker,
    source site, justification, request reference."""
    assert len(_properties(template)) == 10


def test_there_is_one_picker_and_it_is_required(template: dict[str, Any]) -> None:
    properties = _properties(template)
    picker = properties["catalogue_entry"]
    assert picker["ui:field"] == "EntityPicker"
    assert "catalogue_entry" in _pages(template)[0]["required"]
    assert picker["ui:options"]["allowArbitraryValues"] is False
    assert [name for name, prop in properties.items() if prop.get("ui:field") == "EntityPicker"] == ["catalogue_entry"]


def test_the_picker_offers_only_requestable_active_catalogue_entries(template: dict[str, Any]) -> None:
    """ONE tag. Backstage ORs the values of a key, so `active` and `requestable`
    together would offer every active entry and every requestable one."""
    options = _properties(template)["catalogue_entry"]["ui:options"]
    assert options["catalogFilter"] == {
        "kind": "Resource",
        "spec.type": "application-definition",
        "metadata.tags": "requestable",
    }
    assert options["defaultKind"] == "Resource"


def test_the_picker_filter_matches_what_the_portal_ingests_and_tags() -> None:
    """The slug the provider derives, the entity kind the config sets and the tag
    the provider emits must be the three things the filter names."""
    for config in (DEV_CONFIG,):
        document = yaml.safe_load(config.read_text(encoding="utf-8"))
        kinds = {entry["kind"]: entry for entry in document["infrahub"]["catalog"]["kinds"]}
        entry = kinds["ServiceApplicationDefinition"]
        assert entry["entity"] == "Resource"
        assert entry["type"] == "application-definition"
        assert entry["template"] is False, "entries are maintained in Infrahub; a requester only picks"
    provider = PROVIDER.read_text(encoding="utf-8")
    assert "'requestable'" in provider
    assert "live('requestable') === true" in provider
    assert "live('status') === 'active'" in provider


def test_the_slug_of_the_kind_is_the_one_the_filter_names() -> None:
    """Mirrors `slugFor` in infrahub-backend/src/config.ts."""
    kind = "ServiceApplicationDefinition"
    slug = re.sub(r"^Service", "", kind)
    slug = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", slug)
    slug = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", slug).lower()
    assert slug == "application-definition"


def test_the_applications_pin_marker_is_off_the_generated_form() -> None:
    """Typing `definition_pinned` would tell the generator the pin was taken."""
    document = yaml.safe_load(DEV_CONFIG.read_text(encoding="utf-8"))
    kinds = {entry["kind"]: entry for entry in document["infrahub"]["catalog"]["kinds"]}
    assert "definition_pinned" in kinds["ServiceFabricApp"]["formExclude"]
    assert {"vip_block", "vip_block_managed"} <= set(kinds["ServiceFabricApp"]["formExclude"])


def test_the_entry_is_read_again_from_infrahub_as_the_control(template: dict[str, Any]) -> None:
    """The filter is a convenience. This step is what stops a stale form."""
    query = _steps(template)["read_definition"]["input"]["query"]
    assert "requestable__value: true" in query
    assert 'status__value: "active"' in query
    assert "ids: [$id]" in query


def test_the_create_takes_its_chart_from_the_entry_not_the_form(template: dict[str, Any]) -> None:
    create = _steps(template)["create_app"]["input"]
    variables = create["variables"]
    for field in ("chart_repository", "chart_name", "chart_version"):
        assert variables[field].startswith("${{ " + EDGE), field
    assert variables["vip_block_size"].startswith("${{ " + EDGE)
    assert variables["service_selector"].startswith("${{ " + EDGE)
    assert variables["definition"] == "${{ " + EDGE + ".id }}"
    assert "parameters.chart" not in str(variables)
    assert "advertised_services" not in create.get("relatedNodeLists", [])


def test_the_create_names_the_entry_and_keeps_the_chart_variables_required(template: dict[str, Any]) -> None:
    """Required variables are the assertion: with no matching entry they resolve to
    nothing, Infrahub refuses the mutation and no application is created."""
    query = _steps(template)["create_app"]["input"]["query"]
    assert "definition: { id: $definition }" in query
    for variable in ("chart_repository", "chart_name", "chart_version", "definition"):
        assert f"${variable}: String!" in query, variable
    assert "$vip_block_size: BigInt!" in query
    assert "$service_selector: GenericScalar!" in query


def test_the_entry_is_resolved_and_read_before_anything_is_created(template: dict[str, Any]) -> None:
    ids = list(_steps(template))
    assert ids.index("fetch_definition") < ids.index("branch") < ids.index("read_definition")
    assert ids.index("read_definition") < ids.index("create_app")
    fetch = _steps(template)["fetch_definition"]
    assert fetch["action"] == "catalog:fetch"
    assert fetch["input"]["entityRef"] == "${{ parameters.catalogue_entry }}"
    assert "infrahub.opsmill.com/id" in _steps(template)["read_definition"]["input"]["variables"]["id"]


def test_the_portal_uploads_no_values(template: dict[str, Any]) -> None:
    """The generator owns the values attachment, produced from the entry."""
    assert "values" not in _steps(template)
    assert not [step for step in _steps(template).values() if step["action"] == "infrahub:file:upload"]


def test_the_steps_after_the_application_are_as_before(template: dict[str, Any]) -> None:
    ids = list(_steps(template))
    tail = [
        "create_app",
        "await_app",
        "read_app",
        "assert_vip",
        "create_grant",
        "await_grant",
        "lookup_avd",
        "run_avd_hostvars",
        "run_avd_structured_config",
    ]
    positions = [ids.index(step) for step in tail]
    assert positions == sorted(positions)
    assert "proposed_change" in ids


def test_the_grant_is_still_created_with_the_same_inputs(text: str) -> None:
    for field in ("application: { id: $application }", "source_site: { hfid: [$source_site] }"):
        assert field in text


def test_the_two_configs_register_the_template_and_only_the_dev_config_names_kinds() -> None:
    """`app-config.docker.yaml` layers over the dev config and restates only the
    catalogue LOCATIONS, so the kind entry belongs in the dev config alone."""
    docker = yaml.safe_load(DOCKER_CONFIG.read_text(encoding="utf-8"))
    assert "kinds" not in (docker.get("infrahub") or {}).get("catalog", {})
    assert any(
        "exposed-app-with-access.yaml" in str(location.get("target")) for location in docker["catalog"]["locations"]
    )

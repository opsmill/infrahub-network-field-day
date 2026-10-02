"""The hand-written revoke template must pick from the entities the provider emits.

`backstage/catalog/revoke-access.yaml` offers grants through an `EntityPicker`
filtered on `spec.type`. That value is not chosen in the template: the catalog
provider stamps every `ServiceAppAccess` entity with the type configured for the
kind in `app-config.yaml`, or, when none is configured, with `slugFor(kind)` --
`Service` dropped and the rest kebab-cased, so `app-access`.

The template said `serviceappaccess`, which no entity carries. Nothing errors on
that path: the picker renders, offers nothing, and the form cannot be submitted,
so withdrawing a grant through the portal was impossible while every other part
of the revocation worked. This holds the filter to the provider's rule.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "backstage/catalog/revoke-access.yaml"
DEV_CONFIG = REPO / "backstage/app-config.yaml"
DOCKER_CONFIG = REPO / "backstage/app-config.docker.yaml"

KIND = "ServiceAppAccess"


def _slug_for(kind: str) -> str:
    """Mirror `slugFor` in backstage/plugins/infrahub-backend/src/config.ts."""
    slug = re.sub(r"^Service", "", kind)
    slug = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", slug)
    slug = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", slug)
    return slug.lower()


def _entity_type(kind: str) -> str:
    config = yaml.safe_load(DEV_CONFIG.read_text())
    for entry in config["infrahub"]["catalog"]["kinds"]:
        if entry["kind"] == kind:
            return entry.get("type") or _slug_for(kind)
    return _slug_for(kind)


def _grant_picker() -> dict:
    template = yaml.safe_load(TEMPLATE.read_text())
    return template["spec"]["parameters"][0]["properties"]["grant"]


def test_slug_mirrors_the_provider() -> None:
    # The cases config.ts's own comments name, so a drift in either is visible.
    assert _slug_for("ServiceAppAccess") == "app-access"
    assert _slug_for("ServiceFabricApp") == "fabric-app"
    assert _slug_for("ServiceL3vpn") == "l3vpn"


def test_revoke_picker_filters_on_the_type_grants_carry() -> None:
    picker = _grant_picker()
    assert picker["ui:field"] == "EntityPicker"
    catalog_filter = picker["ui:options"]["catalogFilter"]
    assert catalog_filter["kind"] == "Component"
    assert catalog_filter["spec.type"] == _entity_type(KIND), (
        "the revoke picker filters on a spec.type no ServiceAppAccess entity carries, so it offers no grant to revoke"
    )


def test_revoke_template_is_registered_where_the_lab_reads_it() -> None:
    for path in (DEV_CONFIG, DOCKER_CONFIG):
        targets = [location.get("target", "") for location in yaml.safe_load(path.read_text())["catalog"]["locations"]]
        assert any(target.endswith("catalog/revoke-access.yaml") for target in targets), path.name

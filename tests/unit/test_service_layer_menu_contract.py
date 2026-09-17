"""Menu contract tests for the service and technical layers (FR-065).

The two assertions that matter are the ones a human reading the YAML would not
catch: a menu entry naming a kind that does not exist, and a kind that is
menu-visible in its schema but reachable from nowhere in the menu. Infrahub
does not fail a menu load for either -- the first gives a dead entry, the
second an invisible node.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

MENU_PATH = Path("menus/menu.yml")
SCHEMA_DIR = Path("schemas")

# The domains cycle 010 introduced, each of which FR-065 requires to be
# reachable from the menu.
EXPECTED_SECTIONS = {
    ("Service", "ServiceMenu"),
    ("Security", "SecurityMenu"),
    ("Cluster", "ClusterMenu"),
    ("Wan", "WanMenu"),
    ("Organization", "TenancyMenu"),
}

# Every concrete service kind. FR-065 puts them under one grouping, because
# they are ordered intent rather than device fact.
# Raised deliberately whenever a service kind is added, never loosened to a
# subset check -- the same discipline the security extensions file keeps, so
# that growing the service layer is a visible decision rather than a test
# quietly accommodating it.
SERVICE_KINDS = {
    "ServiceFabricPeering",
    "ServiceFabricApp",
    "ServiceAppAccess",
    "ServiceNetworkSegment",
    "ServiceL3vpn",
    "ServiceInternetAccess",
    "ServiceTenantCloud",
    # Onboarding, added when the portal's tenant and server forms were put
    # behind the service layer.
    "ServiceTenantOnboarding",
    "ServiceServerPlacement",
}


def _menu() -> dict[str, Any]:
    return yaml.safe_load(MENU_PATH.read_text(encoding="utf-8"))


def _flatten(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        out.append(item)
        out.extend(_flatten(item.get("children", {}).get("data", [])))
    return out


def _all_items() -> list[dict[str, Any]]:
    return _flatten(_menu()["spec"]["data"])


def _section(namespace: str, name: str) -> dict[str, Any]:
    for item in _menu()["spec"]["data"]:
        if item["namespace"] == namespace and item["name"] == name:
            return item
    pytest.fail(f"no top-level menu section {namespace}{name}")


def _schema_kinds() -> set[str]:
    kinds: set[str] = set()
    for path in SCHEMA_DIR.rglob("*.yml"):
        schema = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for section in ("nodes", "generics"):
            kinds.update(f"{n['namespace']}{n['name']}" for n in schema.get(section) or [])
    return kinds


def _menu_visible_kinds() -> set[str]:
    """Kinds whose schema does not opt out of the menu."""
    kinds: set[str] = set()
    for path in SCHEMA_DIR.rglob("*.yml"):
        schema = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for node in schema.get("nodes") or []:
            if node.get("include_in_menu") is not False:
                kinds.add(f"{node['namespace']}{node['name']}")
    return kinds


# ---------------------------------------------------------------------------
# The assertions a human would not catch
# ---------------------------------------------------------------------------


def test_every_menu_kind_exists_in_the_schema() -> None:
    """A menu entry naming a kind that does not exist is a dead entry, and
    Infrahub does not fail the load for it."""
    kinds = _schema_kinds()
    unknown = sorted({item["kind"] for item in _all_items() if item.get("kind")} - kinds)

    assert not unknown, f"menu references kinds that do not exist: {unknown}"


def test_every_menu_visible_kind_is_reachable() -> None:
    """A kind that is menu-visible but in no menu section is invisible in the
    UI -- the failure this cycle exists to fix, so it must not come back.

    Originally scoped to the four namespaces that cycle introduced, which left
    the same fault free to appear anywhere else -- and it had: `LocationSite`
    and `RoutingAsn` were menu-visible, carried six and nine objects, and
    appeared in no section, so neither could be browsed. Widened to every
    namespace once those two were listed.
    """
    in_menu = {item["kind"] for item in _all_items() if item.get("kind")}
    unreachable = sorted(kind for kind in _menu_visible_kinds() if kind not in in_menu)

    assert not unreachable, f"menu-visible kinds unreachable from the menu: {unreachable}"


# ---------------------------------------------------------------------------
# FR-065 -- the two-layer split is visible
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("namespace", "name"), sorted(EXPECTED_SECTIONS))
def test_expected_top_level_sections_exist(namespace: str, name: str) -> None:
    section = _section(namespace, name)

    assert section.get("label")
    assert section.get("icon")
    assert section.get("children", {}).get("data")


def test_every_service_kind_sits_under_the_service_section() -> None:
    """FR-065. Services are ordered intent and belong together, separately
    from the technical objects that realize them."""
    service_section = _section("Service", "ServiceMenu")
    kinds = {item["kind"] for item in _flatten(service_section["children"]["data"]) if item.get("kind")}

    assert kinds == SERVICE_KINDS


def test_no_service_kind_appears_outside_the_service_section() -> None:
    """The split is only legible if a service appears in exactly one place."""
    # Compared by (namespace, name) rather than object identity: the helpers
    # each re-parse the YAML, so the dicts are different instances.
    service_section = _section("Service", "ServiceMenu")
    inside = {(i["namespace"], i["name"]) for i in _flatten(service_section["children"]["data"])}
    strays = sorted(
        item["kind"]
        for item in _all_items()
        if item.get("kind") in SERVICE_KINDS and (item["namespace"], item["name"]) not in inside
    )

    assert not strays, f"service kinds outside the Services section: {strays}"


def test_menu_entries_are_uniquely_named() -> None:
    """Duplicate namespace+name pairs make a menu entry ambiguous to address."""
    seen = [(i["namespace"], i["name"]) for i in _all_items()]

    assert len(seen) == len(set(seen))


def test_every_leaf_entry_has_a_label_and_an_icon() -> None:
    """A leaf with no label renders as its kind name, which is not what a
    reader of the sidebar expects."""
    missing = [
        f"{i['namespace']}{i['name']}"
        for i in _all_items()
        if i.get("kind") and (not i.get("label") or not i.get("icon"))
    ]

    assert not missing, f"menu leaves missing a label or icon: {missing}"

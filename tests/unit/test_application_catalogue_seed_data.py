"""Seed data for the application catalogue (specs/035-application-catalogue).

The failures worth catching here are the silent ones:

- a seeded application whose pinned chart differs from the entry it points at,
  so the catalogue says one thing and the cluster runs another;
- an entry that sorts AFTER the application naming it, which loads on a running
  instance (the entry is already there) and fails on a fresh one;
- an infrastructure entry that is requestable, which would put the lab's own
  Grafana in the portal picker;
- `whoami`'s values missing the exposure block, which deploys cleanly, goes
  Ready and answers nothing.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE_FILE = ROOT / "objects/35a_otternet_app_catalogue.yml"
APPS_FILE = ROOT / "objects/36_otternet_app_services.yml"
PAYLOAD_DIR = ROOT / "payloads"

# Application -> the entry it describes.
SEEDED = {
    "otternet-demo": "lab-whoami",
    "otternet-metrics": "lab-metrics",
    "otternet-telemetry": "lab-telemetry",
    "otternet-dns": "lab-dns",
}


def _data(path: Path, kind: str) -> list[dict[str, Any]]:
    for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if doc and doc.get("spec", {}).get("kind") == kind:
            return doc["spec"]["data"]
    pytest.fail(f"no {kind} block in {path}")


def _entries() -> dict[str, dict[str, Any]]:
    return {entry["name"]: entry for entry in _data(CATALOGUE_FILE, "ServiceApplicationDefinition")}


def _apps() -> dict[str, dict[str, Any]]:
    return {app["name"]: app for app in _data(APPS_FILE, "ServiceFabricApp")}


def _seed_script() -> Any:
    spec = importlib.util.spec_from_file_location("seed_app_payloads", ROOT / "scripts/seed_app_payloads.py")
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REQUESTABLE = {"whoami", "podinfo", "grafana", "argo-cd", "otternet-shop", "otternet-wiki"}

# Where each requestable chart keeps its LoadBalancer Service's values, and the key under
# which the Service takes the label the selector matches on.
SERVICE_PATH = {
    "whoami": "service",
    "podinfo": "service",
    "grafana": "service",
    "argo-cd": "server.service",
    "otternet-shop": "service.main",
    "otternet-wiki": "service.main",
}
LABEL_KEY = {"whoami": "commonLabels", "podinfo": "service.additionalLabels", "grafana": "service.labels"}
LABEL_KEY["argo-cd"] = "server.service.labels"
LABEL_KEY["otternet-shop"] = "service.main.labels"
LABEL_KEY["otternet-wiki"] = "service.main.labels"


def test_the_catalogue_has_the_requestable_entries_and_one_per_seeded_application() -> None:
    entries = _entries()
    assert set(entries) == {*REQUESTABLE, *SEEDED.values()}
    requestable = {name for name, entry in entries.items() if entry["requestable"] is True}
    assert requestable == REQUESTABLE


def test_infrastructure_entries_are_never_requestable() -> None:
    """They must never appear in the portal picker."""
    entries = _entries()
    for entry in SEEDED.values():
        assert entries[entry]["requestable"] is False, entry


def test_every_entry_is_active_and_titled() -> None:
    for name, entry in _entries().items():
        assert entry["status"] == "active", name
        assert entry["title"].strip(), name


def test_whoami_is_titled_for_a_requester() -> None:
    assert _entries()["whoami"]["title"] == "Who am I"


def test_the_catalogue_loads_before_the_applications_that_name_it() -> None:
    assert CATALOGUE_FILE.name < APPS_FILE.name
    objects = sorted(path.name for path in (ROOT / "objects").glob("*.yml"))
    assert objects.index(CATALOGUE_FILE.name) < objects.index(APPS_FILE.name)


def test_the_entries_name_a_service_the_firewall_already_declares() -> None:
    declared = {
        entry["name"]
        for doc in yaml.safe_load_all((ROOT / "objects/32_otternet_security.yml").read_text(encoding="utf-8"))
        if doc and doc.get("spec", {}).get("kind") == "SecurityService"
        for entry in doc["spec"]["data"]
    }
    for name, entry in _entries().items():
        assert set(entry.get("default_advertised_services", [])) <= declared, name


@pytest.mark.parametrize(("app", "entry"), sorted(SEEDED.items()))
def test_a_seeded_application_points_at_its_entry_and_is_already_pinned(app: str, entry: str) -> None:
    seeded = _apps()[app]
    assert seeded["definition"] == entry
    assert seeded["definition_pinned"] is True, (
        "seeded applications are created on main where no event rule fires, so the seed carries the pin"
    )


@pytest.mark.parametrize(("app", "entry"), sorted(SEEDED.items()))
def test_a_seeded_applications_chart_is_its_entrys(app: str, entry: str) -> None:
    """The catalogue and the cluster must say the same thing."""
    seeded, described = _apps()[app], _entries()[entry]
    for field in ("chart_repository", "chart_name", "chart_version"):
        assert seeded[field] == described[field], f"{app}.{field}"


@pytest.mark.parametrize(("app", "entry"), sorted(SEEDED.items()))
def test_a_seeded_applications_exposure_defaults_are_its_entrys(app: str, entry: str) -> None:
    seeded, described = _apps()[app], _entries()[entry]
    assert seeded.get("service_selector", []) == described.get("default_service_selector", [])
    if seeded["exposed"]:
        assert seeded["advertised_services"] == described["default_advertised_services"]


def test_the_seeded_demo_applications_block_and_exposure_did_not_move() -> None:
    """Identical rendered output depends on no other field having moved."""
    demo = _apps()["otternet-demo"]
    assert demo["exposed"] is True
    assert demo["vip_block"] == ["10.112.240.0/28", "default"]


def test_whoami_values_are_valid_yaml_that_makes_the_application_reachable() -> None:
    entry = _entries()["whoami"]
    values = yaml.safe_load(entry["default_values"])

    assert values["service"]["type"] == "LoadBalancer"
    assert values["service"]["externalTrafficPolicy"] == "Local"
    assert values["service"]["ports"]["http"] == 80

    selectors = dict(item.split("=", 1) for item in entry["default_service_selector"])
    labels = {str(key): str(value) for key, value in values["commonLabels"].items()}
    assert selectors == labels, "commonLabels must carry every label the selector matches on"
    # A key with a dot and a slash survived: it is text, not JSON.
    assert "otternet.lab/advertise" in labels


@pytest.mark.parametrize("name", sorted(REQUESTABLE))
def test_every_requestable_entry_is_reachable_and_labelled(name: str) -> None:
    entry = _entries()[name]
    values = yaml.safe_load(entry["default_values"])

    service: Any = values
    for part in SERVICE_PATH[name].split("."):
        service = service[part]
    assert service["type"] == "LoadBalancer"
    assert service["externalTrafficPolicy"] == "Local"

    labels: Any = values
    for part in LABEL_KEY[name].split("."):
        labels = labels[part]
    selectors = dict(item.split("=", 1) for item in entry["default_service_selector"])
    assert selectors == {str(key): str(value) for key, value in labels.items()}
    assert entry["default_advertised_services"] == ["junos-http"]


@pytest.mark.parametrize("name", sorted(REQUESTABLE))
def test_requestable_values_render_through_the_transform_unchanged(name: str) -> None:
    from transforms.crossplane_fabric_app import apply_local_traffic

    entry = _entries()[name]
    values = yaml.safe_load(entry["default_values"])
    assert apply_local_traffic(exposed=True, chart=entry["chart_name"], values=values, name="x") == values


def test_whoami_values_render_through_the_transform_unchanged() -> None:
    """The transform enforces Local traffic; the entry must already say it."""
    from transforms.crossplane_fabric_app import apply_local_traffic

    entry = _entries()["whoami"]
    values = yaml.safe_load(entry["default_values"])
    rendered = apply_local_traffic(exposed=True, chart=entry["chart_name"], values=values, name="x")
    assert rendered == values


def test_the_block_size_defaults_are_inside_the_applications_bounds() -> None:
    for name, entry in _entries().items():
        assert 24 <= entry["default_vip_block_size"] <= 30, name


# ---- scripts/seed_app_payloads.py ------------------------------------------


def test_each_infrastructure_entry_takes_its_values_from_the_applications_payload() -> None:
    module = _seed_script()
    assert set(module.DEFINITION_PAYLOADS) == set(SEEDED.values())
    for entry, app in module.DEFINITION_PAYLOADS.items():
        assert SEEDED[app] == entry
        text = module.definition_default_values(entry)
        assert text == (PAYLOAD_DIR / module.PAYLOADS[app][0]).read_text(encoding="utf-8")
        assert yaml.safe_load(text) is not None


def test_the_entry_does_not_carry_the_dashboards() -> None:
    """220 KB of JSON would be read by every catalogue refresh."""
    module = _seed_script()
    assert len(module.definition_default_values("lab-metrics")) < 50_000


def test_seeding_the_entries_is_idempotent() -> None:
    import asyncio

    module = _seed_script()
    saves: list[str] = []

    @dataclass
    class _Value:
        value: str | None

    class _Node:
        def __init__(self, name: str, current: str | None) -> None:
            self.name = name
            self.default_values = _Value(current)

        async def save(self, **_: Any) -> None:
            saves.append(self.name)

    nodes: dict[str, _Node] = {}

    class _Client:
        async def get(self, *, kind: str, branch: str, name__value: str) -> _Node:
            assert kind == "ServiceApplicationDefinition"
            return nodes.setdefault(name__value, _Node(name__value, None))

    first = asyncio.run(module.seed_definitions(_Client(), "main"))
    assert first == len(SEEDED)
    assert sorted(saves) == sorted(SEEDED.values())

    saves.clear()
    second = asyncio.run(module.seed_definitions(_Client(), "main"))
    assert second == 0
    assert saves == []

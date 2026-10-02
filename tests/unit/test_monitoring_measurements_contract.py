"""The measurement catalogue and the renderer agree, in both directions (cycle 034).

A monitoring profile names measurements by NAME, and the collector renderer
dispatches on (name, device kind). Two drifts are silent without this:

* a seeded measurement the renderer has no entry for -- the profile loads, the
  proposed change merges, and nothing is collected;
* a renderer entry for a kind the table below does not list -- a family is
  collected that the design never said it would be, or the reverse.

The table is the design's statement of which family each measurement applies
to. Changing what a family can report is a change here first.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from transforms.telemetry_collector_config import DISPATCH, FIREWALL, ROUTER, SERVER, SWITCH
from transforms.telemetry_services import (
    APP_ACCESS,
    FABRIC_APP,
    INTERNET,
    L3VPN,
    ONBOARDING,
    PEERING,
    PLACEMENT,
    SEGMENT,
    SERVICE_DISPATCH,
    SERVICE_GENERIC,
    SERVICE_KINDS,
    TENANT_CLOUD,
)

# measurement -> the device kinds it is rendered for. The WAN routers gained
# `interface-counters` and `system-resources` when they moved to SR Linux: FRR's
# exporter reported routing state only, and SR Linux streams all three over gNMI
# through the same OpenConfig paths as the switches.
CONTRACT: dict[str, set[str]] = {
    "interface-counters": {SWITCH, ROUTER, FIREWALL},
    "bgp-neighbor-state": {SWITCH, ROUTER},
    "evpn-routes": {SWITCH},
    "system-resources": {SWITCH, ROUTER, FIREWALL},
    "security-sessions": {FIREWALL},
    "node-resources": {SERVER},
}

# Cycle 035: measurements on SERVICES, and the service kinds each is rendered
# for. The same two-way agreement as the device table: a seeded measurement no
# renderer knows is a test failure, and so is a renderer entry the design never
# named.
SERVICE_CONTRACT: dict[str, set[str]] = {
    "service-lifecycle": set(SERVICE_KINDS),
    "service-delivery": {FABRIC_APP},
    "service-reachability": {FABRIC_APP},
    "service-access": {APP_ACCESS},
    "service-routing": {L3VPN, INTERNET, TENANT_CLOUD, ONBOARDING, SEGMENT, PEERING},
    "service-cabling": {PLACEMENT},
}

SEED = Path("objects/40_otternet_monitoring.yml")


def _seeded(kind: str) -> list[dict]:
    for document in yaml.safe_load_all(SEED.read_text(encoding="utf-8")):
        if document and document.get("spec", {}).get("kind") == kind:
            return document["spec"]["data"]
    return []


def test_the_renderer_dispatch_equals_the_contract() -> None:
    assert {measurement: set(kinds) for measurement, kinds in DISPATCH.items()} == CONTRACT


def test_the_service_dispatch_equals_the_contract() -> None:
    assert {measurement: set(kinds) for measurement, kinds in SERVICE_DISPATCH.items()} == SERVICE_CONTRACT


def test_no_measurement_is_both_a_device_and_a_service_measurement() -> None:
    assert not set(DISPATCH) & set(SERVICE_DISPATCH)


def test_every_seeded_measurement_has_a_renderer_for_some_family() -> None:
    names = {entry["name"] for entry in _seeded("MonitoringMeasurement")}
    both = set(CONTRACT) | set(SERVICE_CONTRACT)
    assert names == both, f"catalogue and renderer disagree: {sorted(names ^ both)}"
    assert all({**CONTRACT, **SERVICE_CONTRACT}[name] for name in names)


def _device_profiles() -> list[dict]:
    return [p for p in _seeded("MonitoringProfile") if not p.get("service_kind")]


def _service_profiles() -> list[dict]:
    return [p for p in _seeded("MonitoringProfile") if p.get("service_kind")]


def test_every_seeded_service_profile_names_a_known_kind_and_only_service_measurements() -> None:
    profiles = _service_profiles()
    assert profiles
    for profile in profiles:
        kind = profile["service_kind"]
        assert kind == SERVICE_GENERIC or kind in SERVICE_KINDS, profile["name"]
        assert not profile.get("device_groups"), f"{profile['name']}: a service profile names no device group"
        kinds = set(SERVICE_KINDS) if kind == SERVICE_GENERIC else {kind}
        for measurement in profile["measurements"]:
            assert measurement in SERVICE_CONTRACT, f"{profile['name']}: {measurement!r} is not a service measurement"
            assert SERVICE_CONTRACT[measurement] & kinds, (
                f"{profile['name']}: {measurement!r} applies to no kind it watches"
            )


def test_the_seeded_service_profiles_watch_every_service_kind_for_its_lifecycle() -> None:
    """The point of the feature: a new request of ANY kind shows up, with nobody adding monitoring."""
    lifecycle = [p for p in _service_profiles() if "service-lifecycle" in p["measurements"]]
    assert any(p["service_kind"] == SERVICE_GENERIC for p in lifecycle)
    watched = {measurement for p in _service_profiles() for measurement in p["measurements"]}
    assert watched == set(SERVICE_CONTRACT), f"seeded but never watched: {sorted(set(SERVICE_CONTRACT) - watched)}"


def test_every_seeded_profile_names_only_known_measurements_and_reaches_its_family() -> None:
    family_of_group = {
        "avd_devices": SWITCH,
        "srl_routers": ROUTER,
        "junos_firewalls": FIREWALL,
        "kubernetes_nodes": SERVER,
    }
    for profile in _device_profiles():
        for measurement in profile["measurements"]:
            assert measurement in CONTRACT, f"{profile['name']}: unknown measurement {measurement!r}"
            reachable = {family_of_group[g] for g in profile["device_groups"]}
            assert CONTRACT[measurement] & reachable, (
                f"{profile['name']}: {measurement!r} applies to none of the families its groups contain"
            )


def test_the_seeded_profiles_reach_all_four_families() -> None:
    groups = {g for profile in _device_profiles() for g in profile["device_groups"]}
    assert groups >= {"avd_devices", "srl_routers", "junos_firewalls", "kubernetes_nodes"}

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

SEED = Path("objects/40_otternet_monitoring.yml")


def _seeded(kind: str) -> list[dict]:
    for document in yaml.safe_load_all(SEED.read_text(encoding="utf-8")):
        if document and document.get("spec", {}).get("kind") == kind:
            return document["spec"]["data"]
    return []


def test_the_renderer_dispatch_equals_the_contract() -> None:
    assert {measurement: set(kinds) for measurement, kinds in DISPATCH.items()} == CONTRACT


def test_every_seeded_measurement_has_a_renderer_for_some_family() -> None:
    names = {entry["name"] for entry in _seeded("MonitoringMeasurement")}
    assert names == set(CONTRACT), f"catalogue and renderer disagree: {sorted(names ^ set(CONTRACT))}"
    assert all(CONTRACT[name] for name in names)


def test_every_seeded_profile_names_only_known_measurements_and_reaches_its_family() -> None:
    family_of_group = {
        "avd_devices": SWITCH,
        "srl_routers": ROUTER,
        "junos_firewalls": FIREWALL,
        "kubernetes_nodes": SERVER,
    }
    for profile in _seeded("MonitoringProfile"):
        for measurement in profile["measurements"]:
            assert measurement in CONTRACT, f"{profile['name']}: unknown measurement {measurement!r}"
            reachable = {family_of_group[g] for g in profile["device_groups"]}
            assert CONTRACT[measurement] & reachable, (
                f"{profile['name']}: {measurement!r} applies to none of the families its groups contain"
            )


def test_the_seeded_profiles_reach_all_four_families() -> None:
    groups = {g for profile in _seeded("MonitoringProfile") for g in profile["device_groups"]}
    assert groups >= {"avd_devices", "srl_routers", "junos_firewalls", "kubernetes_nodes"}

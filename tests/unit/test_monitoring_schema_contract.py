"""Contract tests for the ``Monitoring`` namespace (cycle 034).

Monitoring intent is the input the telemetry collector's configuration is
rendered from, the same way design intent is the input to a device's. Three
properties of the model are load bearing and none of them fails at load time:

* **A profile selects devices by group or services by kind** (cycle 035). A
  service is in a group only when a generator sits beneath its kind, so a
  group-based selection would miss every WAN service. ``device_groups`` became
  optional for that reason; it was mandatory so Backstage's form builder (which
  admits *mandatory* cardinality-many only) would offer it, and no Monitoring
  kind is in the portal's catalogue -- which a test below now holds, so the
  trade is re-examined the day one is added. ``measurements`` stays mandatory.
* **A profile peers groups, not a device kind.** The four device kinds are
  siblings under ``DcimGenericDevice``; a relationship to ``DcimDevice`` would
  reach the FRR routers and miss the fabric, and nothing would report it.
* **The collector is an artifact target.** Without ``CoreArtifactTarget`` the
  artifact definition loads and renders nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

SCHEMA = Path(__file__).parents[2] / "schemas" / "monitoring.yml"


def _nodes() -> dict[str, dict[str, Any]]:
    loaded = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    return {f"{n['namespace']}{n['name']}": n for n in loaded.get("nodes", [])}


def _attribute(node: dict[str, Any], name: str) -> dict[str, Any]:
    return next(a for a in node.get("attributes", []) if a["name"] == name)


def _relationship(node: dict[str, Any], name: str) -> dict[str, Any]:
    return next(r for r in node.get("relationships", []) if r["name"] == name)


def test_the_three_kinds_exist_under_the_monitoring_namespace() -> None:
    assert set(_nodes()) == {"MonitoringCollector", "MonitoringProfile", "MonitoringMeasurement"}


def test_every_kind_is_identified_by_its_name() -> None:
    for kind, node in _nodes().items():
        assert node.get("human_friendly_id") == ["name__value"], kind
        assert node.get("uniqueness_constraints") == [["name__value"]], kind
        assert _attribute(node, "name").get("unique") is True, kind


def test_the_collector_is_an_artifact_target() -> None:
    assert "CoreArtifactTarget" in _nodes()["MonitoringCollector"].get("inherit_from", [])


def test_profile_selection_reaches_every_device_kind_and_every_service_kind() -> None:
    profile = _nodes()["MonitoringProfile"]
    measurements = _relationship(profile, "measurements")
    assert measurements["peer"] == "MonitoringMeasurement"
    assert measurements.get("cardinality") == "many"
    assert measurements.get("optional") is False
    assert measurements.get("min_count") == 1
    groups = _relationship(profile, "device_groups")
    assert groups["peer"] == "CoreStandardGroup", "groups, not a device kind: the four device kinds are siblings"
    assert groups.get("cardinality") == "many"
    assert groups.get("optional") is True, "a service profile names no group"
    kind = _attribute(profile, "service_kind")
    assert kind["kind"] == "Text", "Text, so a new service kind needs no schema change"
    assert kind.get("optional") is True
    assert kind["parameters"]["regex"].startswith("^Service")
    timeout = _attribute(profile, "timeout_seconds")
    assert timeout.get("optional") is True
    assert timeout.get("default_value") == 5


def test_no_monitoring_kind_is_in_the_portal_catalogue() -> None:
    """The reason device_groups could become optional. If a Monitoring kind is ever
    offered by the portal, its form builder drops optional many-relationships, and
    a profile requested there could name no group -- re-examine before adding one."""
    portal = Path(__file__).parents[2] / "backstage"
    for config in ("app-config.yaml", "app-config.docker.yaml"):
        path = portal / config
        if path.exists():
            assert "Monitoring" not in path.read_text(encoding="utf-8"), config


def test_interval_is_bounded() -> None:
    interval = _attribute(_nodes()["MonitoringProfile"], "interval_seconds")
    assert interval["kind"] == "Number"
    assert interval.get("default_value") == 30
    assert interval.get("parameters", {}).get("min_value") == 10
    assert interval.get("parameters", {}).get("max_value") == 3600


def test_no_relationship_shadows_a_builtin() -> None:
    """`profiles` is every node's built-in relationship to CoreProfile.

    Declaring a schema relationship with that name loads cleanly and then makes
    a query for it resolve against CoreProfile, which has none of the fields a
    monitoring profile carries.
    """
    builtin = {"profiles", "member_of_groups", "subscriber_of_groups"}
    for kind, node in _nodes().items():
        shadowed = builtin & {rel["name"] for rel in node.get("relationships", [])}
        assert not shadowed, f"{kind} shadows built-in relationships {sorted(shadowed)}"


def test_collector_and_profiles_are_one_relationship_seen_from_both_ends() -> None:
    nodes = _nodes()
    forward = _relationship(nodes["MonitoringCollector"], "monitoring_profiles")
    reverse = _relationship(nodes["MonitoringProfile"], "collector")
    assert forward["peer"] == "MonitoringProfile"
    assert reverse["peer"] == "MonitoringCollector"
    assert forward["identifier"] == reverse["identifier"]
    assert reverse.get("cardinality") == "one"
    assert reverse.get("optional") is False


def test_no_monitoring_kind_is_branch_agnostic() -> None:
    """Monitoring intent is reviewed on a branch like any other intent."""
    for kind, node in _nodes().items():
        assert node.get("branch", "aware") == "aware", kind

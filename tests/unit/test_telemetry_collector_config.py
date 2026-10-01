"""Unit tests for the Telemetry Collector Configuration transform (cycle 034).

The fixture is the real query response for `otternet-telegraf`, captured from a
branch carrying the seeded monitoring intent -- so the device set, the groups
and the cabling are the lab's own. The structured-config downloads behind the
intended BGP sessions are the transform's one piece of IO, and are served by a
fake client returning a small, known structured config.
"""

from __future__ import annotations

import asyncio
import copy
import json
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

from transforms.telemetry_collector_config import (
    INTENDED_FILE,
    TelemetryCollectorConfig,
    TelemetryCollectorConfigError,
)

FIXTURE = Path("tests/unit/fixtures/monitoring/otternet-telegraf.json")

STRUCTURED = {
    "router_bgp": {
        "neighbors": [
            {"ip_address": "10.41.1.0", "description": "spine-otternet-pod1-1_Ethernet1"},
            {"ip_address": "192.0.2.1", "description": "outside-the-model"},
        ],
        "vrfs": [{"name": "K8S_PROD", "neighbors": [{"ip_address": "10.110.0.11", "description": "k8s-node1"}]}],
    }
}


class _File:
    async def download_file(self) -> bytes:
        return json.dumps(STRUCTURED).encode()


class _Client:
    def __init__(self) -> None:
        self.downloads = 0

    async def get(self, *_args: Any, **_kwargs: Any) -> _File:
        self.downloads += 1
        return _File()


def _data() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _render(data: dict[str, Any] | None = None) -> tuple[dict[str, Any], _Client]:
    transform = TelemetryCollectorConfig.__new__(TelemetryCollectorConfig)
    client = _Client()
    transform._init_client = client
    text = asyncio.run(transform.transform(data or _data()))
    return {"text": text, "manifest": yaml.safe_load(text)}, client


def _profiles(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [e["node"] for e in data["MonitoringCollector"]["edges"][0]["node"]["monitoring_profiles"]["edges"]]


def _conf(out: dict[str, Any]) -> dict[str, Any]:
    return tomllib.loads(out["manifest"]["data"]["telegraf.conf"])


def _kinds(conf: dict[str, Any]) -> Counter[str]:
    return Counter(
        block["tags"]["kind"] for plugin in ("gnmi", "prometheus", "snmp") for block in conf["inputs"].get(plugin, [])
    )


# ---------------------------------------------------------------------------
# Invariants 1-5 (contracts/telemetry-collector-artifact.md)
# ---------------------------------------------------------------------------


def test_one_configmap_with_exactly_the_two_keys() -> None:
    out, _ = _render()
    assert out["text"].count("\n---") == 0
    manifest = out["manifest"]
    assert manifest["kind"] == "ConfigMap"
    assert manifest["metadata"] == {
        "name": "telegraf-intent",
        "namespace": "otternet-telemetry",
        "labels": {"app.kubernetes.io/managed-by": "infrahub", "otternet.lab/collector": "otternet-telegraf"},
    }
    assert set(manifest["data"]) == {"telegraf.conf", "intended.prom"}


def test_the_configuration_parses_and_an_empty_one_is_refused() -> None:
    out, _ = _render()
    conf = _conf(out)
    assert conf["outputs"]["prometheus_client"][0]["listen"] == ":9273"
    assert conf["inputs"]["file"][0]["files"] == [INTENDED_FILE]

    data = _data()
    for profile in _profiles(data):
        profile["enabled"]["value"] = False
    with pytest.raises(TelemetryCollectorConfigError, match="select no device"):
        _render(data)


def test_two_renders_are_byte_identical() -> None:
    assert _render()[0]["text"] == _render()[0]["text"]


def test_every_family_is_collected_exactly_as_modelled() -> None:
    """7 switches, 6 SR Linux routers, the firewall and 3 k3s nodes -- and no collector."""
    assert _kinds(_conf(_render()[0])) == Counter(
        {"DcimFabricSwitch": 7, "DcimDevice": 6, "SecurityFirewall": 1, "ComputePhysicalServer": 3}
    )


def test_a_device_with_no_address_is_skipped_and_said_so() -> None:
    data = _data()
    for profile in _profiles(data):
        for group in profile["device_groups"]["edges"]:
            for member in group["node"]["members"]["edges"]:
                node = member["node"]
                if node.get("__typename") == "DcimDevice" and node["name"]["value"] == "branch-rtr":
                    node["telemetry_address"] = {"node": None}
    out, _ = _render(data)
    conf_text = out["manifest"]["data"]["telegraf.conf"]
    assert "# skipped: branch-rtr (DcimDevice) has no address to collect from" in conf_text
    assert "branch-rtr" not in {b["tags"]["device"] for b in _conf(out)["inputs"]["gnmi"]}


# ---------------------------------------------------------------------------
# Intent shapes the render
# ---------------------------------------------------------------------------


def test_device_role_narrows_a_profile_to_the_leaves() -> None:
    conf = _conf(_render()[0])
    evpn = {
        block["tags"]["device"]
        for block in conf["inputs"]["gnmi"]
        if "bgp_afi_safi" in [s["name"] for s in block["subscription"]]
    }
    assert evpn
    assert all(name.startswith("leaf-") for name in evpn)


def test_a_disabled_profile_renders_nothing_and_says_so() -> None:
    data = _data()
    for profile in _profiles(data):
        if profile["name"]["value"] == "cluster-nodes":
            profile["enabled"]["value"] = False
    out, _ = _render(data)
    assert "# disabled: profile cluster-nodes renders nothing" in out["manifest"]["data"]["telegraf.conf"]
    assert "ComputePhysicalServer" not in _kinds(_conf(out))


def test_a_measurement_a_family_cannot_report_is_skipped_visibly() -> None:
    data = _data()
    for profile in _profiles(data):
        if profile["name"]["value"] == "wan-routing":
            profile["measurements"]["edges"].append({"node": {"name": {"value": "evpn-routes"}}})
    text = _render(data)[0]["manifest"]["data"]["telegraf.conf"]
    assert "# skipped: wan-routing/evpn-routes on isp-pe1 (DcimDevice)" in text


def test_an_unknown_measurement_is_refused() -> None:
    data = _data()
    _profiles(data)[0]["measurements"]["edges"].append({"node": {"name": {"value": "made-up"}}})
    with pytest.raises(TelemetryCollectorConfigError, match="made-up"):
        _render(data)


def test_credentials_are_references_and_tags_come_from_the_graph() -> None:
    conf = _conf(_render()[0])
    switch = next(b for b in conf["inputs"]["gnmi"] if b["tags"]["kind"] == "DcimFabricSwitch")
    assert switch["username"] == "${GNMI_USERNAME}"
    assert switch["password"] == "${GNMI_PASSWORD}"  # noqa: S105 -- a reference, not a password
    assert set(switch["tags"]) >= {"collector", "device", "kind", "profile", "role", "rack", "pod"}
    assert switch["addresses"][0].endswith(":6030")
    assert conf["inputs"]["snmp"][0]["agents"] == ["udp://172.20.41.31:161"]
    routers = {b["tags"]["device"]: b for b in conf["inputs"]["gnmi"] if b["tags"]["kind"] == "DcimDevice"}
    assert routers["isp-pe1"]["addresses"] == ["172.20.41.61:57400"]
    assert routers["isp-pe1"]["username"] == "${GNMI_USERNAME}"
    assert routers["isp-pe1"]["password"] == "${GNMI_PASSWORD}"  # noqa: S105 -- a reference, not a password
    assert routers["isp-pe1"]["tls_enable"] is True
    assert "tls_enable" not in switch, "EOS gNMI is plaintext on 6030; only SR Linux's server is TLS"
    assert not any(b["tags"]["kind"] == "DcimDevice" for b in conf["inputs"].get("prometheus", []))


def test_routers_subscribe_to_the_same_openconfig_paths_as_switches() -> None:
    """Same paths, same series names: the fabric dashboards cover the WAN unchanged.

    Measured with Telegraf 1.40 against SR Linux 26.7: all four answered, and
    `bgp_neighbor_session_state_code` carried `neighbor_address` and the network
    instance as `name`, as EOS does.
    """
    conf = _conf(_render()[0])
    paths: dict[str, set[str]] = {}
    for block in conf["inputs"]["gnmi"]:
        paths.setdefault(block["tags"]["kind"], set()).update(
            (s["name"], s["origin"], s["path"]) for s in block["subscription"]
        )
    assert paths["DcimDevice"] == paths["DcimFabricSwitch"] - {
        sub for sub in paths["DcimFabricSwitch"] if sub[0] == "bgp_afi_safi"
    }


# ---------------------------------------------------------------------------
# intended.prom
# ---------------------------------------------------------------------------


def test_intended_series_carry_the_contracted_names_and_labels() -> None:
    out, client = _render()
    lines = [line for line in out["manifest"]["data"]["intended.prom"].splitlines() if not line.startswith("#")]
    metrics = Counter(line.split("{", 1)[0] for line in lines)
    assert set(metrics) == {
        "otternet_intended_bgp_neighbor",
        "otternet_intended_link",
        "otternet_intended_interface_up",
    }
    # Each switch watched for BGP had its stored structured config read once.
    assert client.downloads == 7
    # A neighbour whose description names a watched device is attributed to it;
    # one that names nothing in the model is not.
    assert any('peer_device="spine-otternet-pod1-1"' in line for line in lines)
    assert not any('peer_address="192.0.2.1"' in line and "peer_device" in line for line in lines)
    assert any('vrf="K8S_PROD"' in line for line in lines)


def test_links_are_only_emitted_for_devices_watched_for_interfaces() -> None:
    data = copy.deepcopy(_data())
    for profile in _profiles(data):
        profile["measurements"]["edges"] = [
            m for m in profile["measurements"]["edges"] if m["node"]["name"]["value"] != "interface-counters"
        ]
    out, _ = _render(data)
    assert "otternet_intended_link{" not in out["manifest"]["data"]["intended.prom"]


def test_bgp_state_is_mapped_to_a_number_prometheus_can_keep() -> None:
    conf = _conf(_render()[0])
    enum = conf["processors"]["enum"][0]
    assert enum["namepass"] == ["bgp_neighbor"]
    assert enum["mapping"][0]["value_mappings"]["ESTABLISHED"] == 6
    # `fields`, not `field`: Telegraf 1.40 refuses the old option and exits.
    assert enum["mapping"][0]["fields"] == ["session_state"]


def test_options_telegraf_1_40_refuses_are_not_rendered() -> None:
    """Both of these passed a TOML parse and killed the real collector at load.

    `translator` inside [[inputs.snmp]] (agent-wide since 1.40) and
    `processors.enum.mapping.field` (removed in 1.40). Measured against
    telegraf:1.40-alpine, which exited on each in turn.
    """
    conf = _conf(_render()[0])
    assert conf["agent"]["snmp_translator"] == "gosmi"
    assert all("translator" not in block for block in conf["inputs"]["snmp"])
    assert all("field" not in m for e in conf["processors"]["enum"] for m in e["mapping"])


def test_node_exporter_series_get_the_infrahub_device_name_back() -> None:
    """node-exporter's own `device` label is the interface, and Telegraf never
    overwrites a label a metric already has -- measured as 29 "devices" from
    three nodes. Each node gets a rename (device -> interface) ordered before
    an override (device = its Infrahub name), matched on its scrape URL."""
    conf = _conf(_render()[0])
    renames = conf["processors"]["rename"]
    overrides = conf["processors"]["override"]
    assert len(renames) == len(overrides) == 3
    for rename, override in zip(renames, overrides, strict=True):
        assert rename["order"] < override["order"]
        assert rename["tagpass"]["url"] == override["tagpass"]["url"]
        assert rename["replace"][0] == {"tag": "device", "dest": "interface"}
    assert sorted(o["tags"]["device"] for o in overrides) == ["k8s-node1", "k8s-node2", "k8s-node3"]

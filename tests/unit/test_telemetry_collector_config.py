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
        self.kinds: Counter[str] = Counter()

    async def get(self, *args: Any, **kwargs: Any) -> _File:
        self.downloads += 1
        kind = kwargs.get("kind", args[0] if args else None)
        self.kinds[str(getattr(kind, "__name__", kind))] += 1
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
    """Device inputs by kind. Service inputs carry no device `kind` tag."""
    return Counter(
        block["tags"]["kind"]
        for plugin in ("gnmi", "prometheus", "snmp")
        for block in conf["inputs"].get(plugin, [])
        if "kind" in block["tags"]
    )


def _device_lines(out: dict[str, Any]) -> list[str]:
    """intended.prom's samples about devices, without the services' half (cycle 035)."""
    return [
        line
        for line in out["manifest"]["data"]["intended.prom"].splitlines()
        if not line.startswith("#") and not line.startswith("otternet_intended_service")
    ]


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
        if "fabric-leaf-evpn" in block["tags"]["profile"].split(",")
    }
    assert evpn
    assert all(name.startswith("leaf-") for name in evpn)


def test_a_subscription_two_measurements_share_is_rendered_once() -> None:
    """evpn-routes and bgp-neighbor-state both subscribe to the per-AFI prefixes;
    a leaf asked for both must not report every prefix series twice."""
    conf = _conf(_render()[0])
    for block in conf["inputs"]["gnmi"]:
        names = [s["name"] for s in block["subscription"]]
        assert len(names) == len(set(names)), (block["tags"]["device"], names)
        assert "bgp_afi_safi" in names, block["tags"]["device"]


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
    assert not any(b["tags"].get("kind") == "DcimDevice" for b in conf["inputs"].get("prometheus", []))


def test_routers_subscribe_to_the_same_openconfig_paths_as_switches() -> None:
    """Same paths, same series names: the fabric dashboards cover the WAN unchanged.

    Measured with Telegraf 1.40 against SR Linux 26.7: every one answered, and
    `bgp_neighbor_session_state_code` carried `neighbor_address` and the network
    instance as `name`, as EOS does. Oper-status and the per-AFI prefixes were
    measured the same way against both families before they were added.
    """
    conf = _conf(_render()[0])
    paths: dict[str, set[str]] = {}
    for block in conf["inputs"]["gnmi"]:
        paths.setdefault(block["tags"]["kind"], set()).update(
            (s["name"], s["origin"], s["path"]) for s in block["subscription"]
        )
    assert paths["DcimDevice"] == paths["DcimFabricSwitch"]
    assert {sub[0] for sub in paths["DcimDevice"]} == {
        "bgp_neighbor",
        "bgp_afi_safi",
        "interface_counters",
        "interface_status",
        "cpu",
        "memory",
    }


# ---------------------------------------------------------------------------
# intended.prom
# ---------------------------------------------------------------------------


def test_intended_series_carry_the_contracted_names_and_labels() -> None:
    out, client = _render()
    lines = _device_lines(out)
    metrics = Counter(line.split("{", 1)[0] for line in lines)
    assert set(metrics) == {
        "otternet_intended_bgp_neighbor",
        "otternet_intended_link",
        "otternet_intended_interface_up",
    }
    # Each switch watched for BGP had its stored structured config read once --
    # and each probed application its values file, for the address it pins.
    assert client.kinds["AvdStructuredConfigFile"] == 7
    assert client.kinds["ServiceFabricAppValuesFile"] == 2
    assert client.downloads == 9
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


def test_interface_oper_status_is_mapped_onto_if_mib_numbers() -> None:
    """The gNMI families report oper-status as a string, which Prometheus would
    drop; the codes are IF-MIB's, so `== 1` means up for the firewall's SNMP
    `ifOperStatus` and for every gNMI interface alike."""
    conf = _conf(_render()[0])
    enum = next(e for e in conf["processors"]["enum"] if e["namepass"] == ["interface_status"])
    mapping = enum["mapping"][0]
    assert mapping["fields"] == ["oper_status"]
    assert mapping["dest"] == "oper_status_code"
    assert mapping["value_mappings"]["UP"] == 1
    assert mapping["value_mappings"]["DOWN"] == 2
    snmp_fields = {f["name"] for t in conf["inputs"]["snmp"][0]["table"] for f in t["field"]}
    assert {"ifOperStatus", "ifAlias"} <= snmp_fields


def test_intended_series_carry_the_kind_and_routers_claim_no_vrf() -> None:
    """Intent is scoped by `kind` the way observed series are, so a silent
    device's sessions still count as intended-but-down. A router's neighbours
    carry no network instance in the model, so they name no VRF rather than
    claiming `default` for a session that lives in a customer's."""
    out, _ = _render()
    lines = _device_lines(out)
    assert lines
    assert all('kind="' in line for line in lines)
    bgp = [line for line in lines if line.startswith("otternet_intended_bgp_neighbor")]
    routers = [line for line in bgp if 'kind="DcimDevice"' in line]
    switches = [line for line in bgp if 'kind="DcimFabricSwitch"' in line]
    assert routers
    assert switches
    assert not any("vrf=" in line for line in routers)
    assert all("vrf=" in line for line in switches)


# ---------------------------------------------------------------------------
# Services (cycle 035)
# ---------------------------------------------------------------------------


def _services(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [e["node"] for e in data["ServiceGeneric"]["edges"]]


def _service(data: dict[str, Any], name: str) -> dict[str, Any]:
    return next(s for s in _services(data) if s["name"]["value"] == name)


def _profile(data: dict[str, Any], name: str) -> dict[str, Any]:
    return next(p for p in _profiles(data) if p["name"]["value"] == name)


def _intended(out: dict[str, Any], metric: str) -> list[str]:
    return [line for line in out["manifest"]["data"]["intended.prom"].splitlines() if line.startswith(metric + "{")]


def test_without_service_profiles_the_device_render_is_unchanged() -> None:
    """The services half only ADDS: every line the device profiles render is still
    there, in the same order, once the service profiles are added."""
    data = _data()
    devices_only = copy.deepcopy(data)
    edges = devices_only["MonitoringCollector"]["edges"][0]["node"]["monitoring_profiles"]["edges"]
    edges[:] = [e for e in edges if not e["node"]["service_kind"]["value"]]
    before = _render(devices_only)[0]["text"].splitlines()
    after = iter(_render(data)[0]["text"].splitlines())
    assert all(line in after for line in before), "a device line moved or vanished when services were added"
    assert "otternet_intended_service" not in "\n".join(before)


def test_every_live_service_is_watched_and_none_is_named() -> None:
    out, _ = _render()
    watched = {line.split('service="', 1)[1].split('"', 1)[0] for line in _intended(out, "otternet_intended_service")}
    live = {
        s["name"]["value"]
        for s in _services(_data())
        if s["status"]["value"] not in {"decommissioning", "decommissioned"}
    }
    assert watched == live
    seeded = yaml.safe_load_all(Path("objects/40_otternet_monitoring.yml").read_text(encoding="utf-8"))
    profiles = next(d["spec"]["data"] for d in seeded if d["spec"]["kind"] == "MonitoringProfile")
    assert not live & set(json.dumps(profiles).replace('"', " ").split()), "a profile names a service"


@pytest.mark.parametrize("status", ["decommissioning", "decommissioned"])
def test_a_withdrawn_service_is_no_longer_watched(status: str) -> None:
    data = _data()
    _service(data, "acme-l3vpn")["status"]["value"] = status
    out, _ = _render(data)
    assert not any('service="acme-l3vpn"' in line for line in out["manifest"]["data"]["intended.prom"].splitlines())
    assert any('service="globex-l3vpn"' in line for line in _intended(out, "otternet_intended_service_bgp"))


def test_wan_services_are_checked_against_the_sessions_their_sites_and_peerings_record() -> None:
    out, _ = _render()
    bgp = _intended(out, "otternet_intended_service_bgp")
    l3vpn = sorted(line for line in bgp if 'service="acme-l3vpn"' in line)
    assert len(l3vpn) == 2
    assert any('device="isp-pe1"' in line and 'peer_address="10.51.10.2"' in line for line in l3vpn)
    assert any('device="cust-acme-ce"' in line and 'peer_address="10.51.10.1"' in line for line in l3vpn)
    assert all('kind="DcimDevice"' in line for line in l3vpn)


def test_vrf_bound_services_take_the_fabric_sessions_in_their_vrf() -> None:
    """A tenant cloud and a peering name a VRF, not sessions: they are checked
    against the sessions the fabric's structured configs place in that VRF --
    on the peering's own leaves only, for a peering."""
    out, _ = _render()
    bgp = _intended(out, "otternet_intended_service_bgp")
    peering = [line for line in bgp if 'service="otternet-fabric-peering"' in line]
    assert peering
    assert all('vrf="K8S_PROD"' in line for line in peering)
    assert {line.split('device="', 1)[1].split('"', 1)[0] for line in peering} == {
        "leaf-otternet-pod1-1-1",
        "leaf-otternet-pod1-1-2",
    }


def test_an_application_is_checked_for_its_workload_and_its_vip() -> None:
    out, _ = _render()
    workloads = _intended(out, "otternet_intended_service_workload")
    assert any('namespace="otternet-demo"' in line for line in workloads)
    vips = _intended(out, "otternet_intended_service_vip")
    assert any('vip_block="10.112.240.0/28"' in line for line in vips)
    assert not any('service="otternet-telemetry"' in line for line in vips), "an unexposed app has no VIP to check"


def test_a_gated_application_is_probed_because_its_fabricapp_admits_the_collector() -> None:
    """Cycle 036. Both seeded exposed applications are gated -- otternet-demo by
    default deny, Grafana by its allow-ingress -- and `services-apps` asks for
    `service-reachability`, so each FabricApp admits otternet-telemetry and the
    collector probes each VIP on its advertised port."""
    out, _ = _render()
    probes = _conf(out)["inputs"]["net_response"]
    assert sorted((p["tags"]["service"], p["address"]) for p in probes) == [
        ("otternet-demo", "10.112.240.0:80"),
        ("otternet-metrics", "10.112.240.80:80"),
    ]
    assert all(p["protocol"] == "tcp" for p in probes)
    text = out["manifest"]["data"]["telegraf.conf"]
    assert "pod gate does not admit" not in text
    assert "# not probed: otternet-telemetry is not exposed, so it has no VIP" in text


def test_turning_reachability_off_withdraws_every_probe() -> None:
    """The same edit closes the gate in the FabricApp, so nothing is left probing
    a path that no longer exists."""
    data = _data()
    profile = _profile(data, "services-apps")
    profile["measurements"]["edges"] = [
        m for m in profile["measurements"]["edges"] if m["node"]["name"]["value"] != "service-reachability"
    ]
    out, _ = _render(data)
    assert "net_response" not in _conf(out)["inputs"]
    assert _intended(out, "otternet_intended_service_probe") == []
    assert _intended(out, "otternet_intended_service_workload"), "delivery is still watched"


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda app: app["policy_allow_ports"].update(value=None),
            "declares no TCP policy_allow_ports",
        ),
        (
            lambda app: app["policy_allow_ports"].update(value=[{"port": "80", "protocol": "UDP"}]),
            "declares no TCP policy_allow_ports",
        ),
    ],
)
def test_a_gated_application_the_fabricapp_cannot_admit_is_not_probed_and_says_why(mutate: Any, reason: str) -> None:
    """A gate is never widened to admit a probe: no TCP pod port, no admission,
    so no probe -- which would otherwise report a healthy application down."""
    data = _data()
    mutate(_service(data, "otternet-demo"))
    out, _ = _render(data)
    services = [p["tags"]["service"] for p in _conf(out)["inputs"]["net_response"]]
    assert services == ["otternet-metrics"]
    text = out["manifest"]["data"]["telegraf.conf"]
    assert (
        f"# not probed: otternet-demo's pod gate does not admit this collector: otternet-demo's pod gate is closed and it {reason}"
        in text
    )


class _ValuesClient(_Client):
    def __init__(self, values: str) -> None:
        super().__init__()
        self.values = values

    async def get(self, *_args: Any, **kwargs: Any) -> Any:
        if kwargs.get("kind") == "ServiceFabricAppValuesFile":
            values = self.values

            class _Values:
                async def download_file(self) -> bytes:
                    return values.encode()

            return _Values()
        return await super().get(*_args, **kwargs)


def _render_with(data: dict[str, Any], client: _Client) -> dict[str, Any]:
    transform = TelemetryCollectorConfig.__new__(TelemetryCollectorConfig)
    transform._init_client = client
    text = asyncio.run(transform.transform(data))
    return {"text": text, "manifest": yaml.safe_load(text)}


def test_an_ungated_application_is_probed_on_each_advertised_tcp_port_at_its_pinned_address() -> None:
    data = _data()
    app = _service(data, "otternet-metrics")
    app["policy_default_deny"]["value"] = False
    app["allowed_source_prefixes"]["count"] = 0
    profile = _profile(data, "services-apps")
    profile["timeout_seconds"]["value"] = 3
    out = _render_with(
        data, _ValuesClient('grafana:\n  service:\n    annotations:\n      lbipam.cilium.io/ips: "10.112.240.81"\n')
    )
    probes = [p for p in _conf(out)["inputs"]["net_response"] if p["tags"]["service"] == "otternet-metrics"]
    assert [p["address"] for p in probes] == ["10.112.240.81:80"]
    assert probes[0]["protocol"] == "tcp"
    assert probes[0]["timeout"] == "3s", "the timeout is the profile's"
    assert probes[0]["interval"] == "30s", "and so is the interval"
    assert probes[0]["tags"]["service"] == "otternet-metrics"
    assert [line for line in _intended(out, "otternet_intended_service_probe") if "otternet-metrics" in line] == [
        'otternet_intended_service_probe{address="10.112.240.81",port="80",service="otternet-metrics",'
        'service_kind="ServiceFabricApp"} 1'
    ]
    # Unpinned, the first address of its own block: Cilium hands an app's first
    # Service the first address of the pool the composition gives it alone.
    unpinned = _render_with(data, _ValuesClient("replicaCount: 1\n"))
    assert [
        p["address"] for p in _conf(unpinned)["inputs"]["net_response"] if p["tags"]["service"] == "otternet-metrics"
    ] == ["10.112.240.80:80"]


def test_the_lifecycle_scrape_asks_for_exactly_the_kinds_the_profiles_name() -> None:
    out, _ = _render()
    scrape = [b for b in _conf(out)["inputs"]["prometheus"] if "kind" not in b["tags"]]
    assert scrape == [
        {
            "urls": ["http://172.20.41.1:8003/metrics?kinds=ServiceGeneric"],
            "metric_version": 2,
            "interval": "30s",
            "timeout": "10s",
            "tags": {"collector": "otternet-telegraf", "profile": "services-lifecycle"},
        }
    ]
    data = _data()
    _profile(data, "services-lifecycle")["service_kind"]["value"] = "ServiceAppAccess"
    narrowed = [b for b in _conf(_render(data)[0])["inputs"]["prometheus"] if "kind" not in b["tags"]]
    assert narrowed[0]["urls"] == ["http://172.20.41.1:8003/metrics?kinds=ServiceAppAccess"]
    _profile(data, "services-lifecycle")["enabled"]["value"] = False
    assert not [b for b in _conf(_render(data)[0])["inputs"]["prometheus"] if "kind" not in b["tags"]]


def test_a_disabled_service_profile_withdraws_exactly_its_series() -> None:
    data = _data()
    _profile(data, "services-routing")["enabled"]["value"] = False
    out, _ = _render(data)
    assert not _intended(out, "otternet_intended_service_bgp")
    assert _intended(out, "otternet_intended_service_workload"), "the apps profile is untouched"
    assert "# disabled: profile services-routing renders nothing" in out["manifest"]["data"]["telegraf.conf"]


def test_the_lifecycle_exporter_port_is_the_one_compose_publishes() -> None:
    from transforms.telemetry_services import LIFECYCLE_EXPORTER

    compose = yaml.safe_load(Path("docker-compose.override.yml").read_text(encoding="utf-8"))
    service = compose["services"]["service-lifecycle-exporter"]
    port = LIFECYCLE_EXPORTER.rsplit(":", 1)[1].split("/", 1)[0]
    assert f"{port}:{port}" in service["ports"]
    token = service["environment"]["INFRAHUB_API_TOKEN"]
    assert token == "${INFRAHUB_EXPORTER_TOKEN:-}", "view-only, never admin"  # noqa: S105 - a reference
    assert "metrics" in service["profiles"]


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda p: p["service_kind"].update(value="ServiceMadeUp"), "no renderer knows"),
        (
            lambda p: p["measurements"]["edges"].append({"node": {"name": {"value": "bgp-neighbor-state"}}}),
            "no service renderer",
        ),
        (
            lambda p: p["device_groups"]["edges"].append(
                {"node": {"name": {"value": "avd_devices"}, "members": {"edges": []}}}
            ),
            "one or the other",
        ),
    ],
)
def test_a_service_profile_that_cannot_render_is_refused(mutate: Any, match: str) -> None:
    data = _data()
    mutate(_profile(data, "services-routing"))
    with pytest.raises(TelemetryCollectorConfigError, match=match):
        _render(data)


def test_a_device_profile_with_no_group_is_refused() -> None:
    """device_groups is optional in the schema since a service profile names none;
    a DEVICE profile without one would render nothing, so it is refused."""
    data = _data()
    _profile(data, "cluster-nodes")["device_groups"]["edges"] = []
    with pytest.raises(TelemetryCollectorConfigError, match="names no device group"):
        _render(data)


def test_a_service_measurement_on_a_device_profile_says_what_is_missing() -> None:
    data = _data()
    _profile(data, "cluster-nodes")["measurements"]["edges"].append({"node": {"name": {"value": "service-routing"}}})
    with pytest.raises(TelemetryCollectorConfigError, match="service_kind"):
        _render(data)

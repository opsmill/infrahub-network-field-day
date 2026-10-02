"""A probe and the gate it passes through cannot disagree (cycle 036).

Two artifacts describe one path. The Telemetry Collector Configuration renders
a TCP probe of an application's VIP; the application's FabricApp renders, as
``spec.monitoring``, the collector namespaces its pod gate admits -- which the
composition turns into the ``allow-collector`` CiliumNetworkPolicy. A probe the
gate drops reports a healthy application down forever, and an admission no
probe uses is a hole in the gate with nothing to show for it.

So both are rendered here from the SAME intent -- the real collector fixture,
converted into the FabricApp query's shape -- across every change that should
move them, and held to each other:

* every gated application the collector probes has a FabricApp admitting the
  collector's namespace, on the pod ports external sources are confined to;
* every FabricApp admitting the collector is one the collector probes;
* an application whose gate is open is probed and admits nothing, because
  nothing selects its pods and an admission policy would close them.

The composition itself cannot run here; its half is held statically below, and
by the live validation recorded in the PR.
"""

from __future__ import annotations

import asyncio
import copy
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.unit.test_telemetry_collector_config import _data, _render
from transforms.crossplane_fabric_app import CrossplaneFabricAppTransform
from transforms.telemetry_services import gate_closed, pod_ports

COMPOSITION = Path("lab/crossplane/apps/01-composition-fabric-app.yaml")
XRD = Path("lab/crossplane/apps/00-xrd-fabric-app.yaml")

Mutation = Callable[[dict[str, Any]], None]


def _collector(data: dict[str, Any]) -> dict[str, Any]:
    return data["MonitoringCollector"]["edges"][0]["node"]


def _apps(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [e["node"] for e in data["ServiceGeneric"]["edges"] if e["node"]["__typename"] == "ServiceFabricApp"]


def _app(data: dict[str, Any], name: str) -> dict[str, Any]:
    return next(a for a in _apps(data) if a["name"]["value"] == name)


def _profile(data: dict[str, Any], name: str) -> dict[str, Any]:
    return next(
        e["node"] for e in _collector(data)["monitoring_profiles"]["edges"] if e["node"]["name"]["value"] == name
    )


def _fabricapp_query(app: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """The FabricApp query's response for ``app``, from the collector fixture.

    The fields the admission reads are copied; the rest are the neutral values
    a seeded application carries, so the manifest renders.
    """
    collector = _collector(data)
    namespace = collector["namespace_name"]["value"]
    name = app["name"]["value"]
    block = (app.get("vip_block") or {}).get("node")
    sources = int((app.get("allowed_source_prefixes") or {}).get("count") or 0)
    node = {
        "id": f"app-{name}",
        "name": app["name"],
        "status": app["status"],
        "namespace_name": app["namespace_name"],
        "exposed": app["exposed"],
        "sso_provider": {"value": "none"},
        "chart_repository": {"value": "https://cowboysysop.github.io/charts/"},
        "chart_name": {"value": "whoami"},
        "chart_version": {"value": "6.0.0"},
        "chart_values": {"value": None},
        "service_selector": {"value": ["otternet.lab/advertise=true"]},
        "communities": {"value": None},
        "workload_selector": {"value": None},
        "policy_default_deny": app["policy_default_deny"],
        "policy_allow_dns": {"value": False},
        "policy_allow_intra_namespace": {"value": False},
        "policy_allow_egress_api_server": {"value": False},
        "policy_allow_egress_internet": {"value": False},
        "policy_allow_ports": app["policy_allow_ports"],
        "vrf": {"node": None},
        "vip_block": {"node": {"id": f"block-{name}", "prefix": block["prefix"]} if block else None},
        "allowed_source_prefixes": {
            "edges": [{"node": {"id": f"src-{i}", "prefix": {"value": f"10.250.{i}.0/24"}}} for i in range(sources)]
        },
        "advertised_services": {
            "edges": [
                {
                    "node": {
                        "id": f"svc-{i}",
                        "port": e["node"]["port"],
                        "ip_protocol": {
                            "node": {"id": f"proto-{i}", "name": e["node"]["ip_protocol"]["node"]["name"]}
                            if e["node"]["ip_protocol"]["node"]
                            else None
                        },
                    }
                }
                for i, e in enumerate(app["advertised_services"]["edges"])
            ]
        },
        "values_file": {"node": None},
    }
    profiles = [
        {
            "id": f"profile-{p['name']['value']}",
            "name": p["name"],
            "enabled": p["enabled"],
            "service_kind": p["service_kind"],
            "measurements": {
                "edges": [
                    {"node": {"id": f"m-{m['node']['name']['value']}", "name": m["node"]["name"]}}
                    for m in p["measurements"]["edges"]
                ]
            },
            "collector": {"node": {"id": "collector", "namespace_name": {"value": namespace}}},
        }
        for p in (e["node"] for e in collector["monitoring_profiles"]["edges"])
    ]
    return {"target": {"edges": [{"node": node}]}, "MonitoringProfile": {"edges": [{"node": p} for p in profiles]}}


def _fabricapp(app: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    transform = CrossplaneFabricAppTransform.__new__(CrossplaneFabricAppTransform)
    return yaml.safe_load(asyncio.run(transform.transform(_fabricapp_query(app, data))))


def _probed(data: dict[str, Any]) -> dict[str, set[int]]:
    out, _ = _render(data)
    conf = tomllib.loads(out["manifest"]["data"]["telegraf.conf"])
    probed: dict[str, set[int]] = {}
    for probe in conf["inputs"].get("net_response", []):
        probed.setdefault(probe["tags"]["service"], set()).add(int(probe["address"].rsplit(":", 1)[1]))
    return probed


def _drop_reachability(data: dict[str, Any]) -> None:
    profile = _profile(data, "services-apps")
    profile["measurements"]["edges"] = [
        m for m in profile["measurements"]["edges"] if m["node"]["name"]["value"] != "service-reachability"
    ]


def _open_grafanas_gate(data: dict[str, Any]) -> None:
    _app(data, "otternet-metrics")["allowed_source_prefixes"]["count"] = 0


MUTATIONS: dict[str, Mutation] = {
    "seeded": lambda _data: None,
    "reachability-off": _drop_reachability,
    "profile-disabled": lambda d: _profile(d, "services-apps")["enabled"].update(value=False),
    "watch-every-kind": lambda d: _profile(d, "services-apps")["service_kind"].update(value="ServiceGeneric"),
    "demo-withdrawn": lambda d: _app(d, "otternet-demo")["status"].update(value="decommissioning"),
    "demo-no-pod-port": lambda d: _app(d, "otternet-demo")["policy_allow_ports"].update(value=None),
    "demo-advertises-nothing": lambda d: _app(d, "otternet-demo")["advertised_services"].update(edges=[]),
    "grafana-gate-open": _open_grafanas_gate,
}


@pytest.mark.parametrize("mutation", list(MUTATIONS.values()), ids=list(MUTATIONS))
def test_every_probe_passes_a_gate_that_admits_it_and_no_admission_goes_unused(mutation: Mutation) -> None:
    data = copy.deepcopy(_data())
    mutation(data)
    namespace = _collector(data)["namespace_name"]["value"]
    probed = _probed(data)

    for app in _apps(data):
        name = app["name"]["value"]
        spec = _fabricapp(app, data)["spec"]
        admitted = namespace in spec.get("monitoring", {}).get("collectorNamespaces", [])
        if gate_closed(_Node(app)):
            assert (name in probed) == admitted, f"{name}: probed={name in probed} but admitted={admitted}"
        else:
            assert not admitted, f"{name}'s gate is open, so an admission policy would close it to everyone else"
        if admitted:
            assert spec["monitoring"]["ports"] == [
                {"port": port, "protocol": protocol} for port, protocol in pod_ports(_Node(app))
            ], f"{name} admits the collector on ports other than the ones external sources are confined to"


def test_the_seed_probes_both_exposed_applications_through_their_gates() -> None:
    """The point of the cycle: the Services dashboard's probe panels get data."""
    data = _data()
    assert _probed(data) == {"otternet-demo": {80}, "otternet-metrics": {80}}
    demo = _fabricapp(_app(data, "otternet-demo"), data)["spec"]["monitoring"]
    grafana = _fabricapp(_app(data, "otternet-metrics"), data)["spec"]["monitoring"]
    assert demo == {"collectorNamespaces": ["otternet-telemetry"], "ports": [{"port": "80", "protocol": "TCP"}]}
    # Grafana's VIP answers on 80 and its pod on 3000: the admission is the pod's.
    assert grafana == {"collectorNamespaces": ["otternet-telemetry"], "ports": [{"port": "3000", "protocol": "TCP"}]}
    assert "monitoring" not in _fabricapp(_app(data, "otternet-telemetry"), data)["spec"]


class _Node:
    """The fixture's plain dicts, read through the attribute access the shared
    helpers use on generated query models."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def __getattr__(self, name: str) -> Any:
        if not isinstance(self._raw, dict) or name not in self._raw:
            return None
        value = self._raw[name]
        if name == "value":
            return value  # an attribute's value is data, e.g. policy_allow_ports' list of dicts
        if isinstance(value, list):
            return [_Node(item) for item in value]
        return _Node(value) if isinstance(value, dict) else value


# ---------------------------------------------------------------------------
# The composition's half, held statically
# ---------------------------------------------------------------------------


def _template() -> str:
    composition = yaml.safe_load(COMPOSITION.read_text(encoding="utf-8"))
    return composition["spec"]["pipeline"][0]["input"]["inline"]["template"]


def _collector_block() -> str:
    template = _template()
    start = template.index("{{- if and $monitoring.collectorNamespaces")
    block = template[start : template.index("{{- end }}\n\n---", start)]
    # The comments explain fromCIDR; the assertions are about what renders.
    return "\n".join(line for line in block.splitlines() if not line.lstrip().startswith("#"))


def test_the_composition_admits_the_collector_only_where_the_gate_is_already_closed() -> None:
    """Measured on the live cluster: with neither default deny nor allowFrom, a
    policy selecting the pods made their ingress deny-by-default for every
    other source. The guard is what keeps such an application unchanged."""
    block = _collector_block()
    assert block.startswith(
        "{{- if and $monitoring.collectorNamespaces $monitoring.ports (or $policy.defaultDeny $policy.allowFrom) }}"
    )


def test_the_admission_names_the_namespace_label_and_the_listed_ports_only() -> None:
    block = _collector_block()
    assert "composition-resource-name: cnp-allow-collector" in block
    assert "io.kubernetes.pod.namespace: {{ . }}" in block
    assert "{{- range $monitoring.collectorNamespaces }}" in block
    assert "{{- range $monitoring.ports }}" in block
    assert "toPorts:" in block
    assert "fromCIDR" not in block
    assert "fromEntities" not in block, "the collector rule must not widen to node entities"
    # The same endpoints allow-ingress protects, not the whole namespace.
    assert "toYaml ($policy.workloadSelector | default dict)" in block


def test_the_xrd_field_is_optional_and_has_no_default() -> None:
    """A default would add the field to every existing FabricApp; optional and
    defaultless is what keeps every unmonitored claim exactly as it was."""
    xrd = yaml.safe_load(XRD.read_text(encoding="utf-8"))
    spec = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]
    monitoring = spec["properties"]["monitoring"]
    assert "monitoring" not in spec.get("required", [])
    assert "default" not in monitoring
    assert monitoring["required"] == ["collectorNamespaces", "ports"]
    assert monitoring["properties"]["ports"]["items"]["properties"]["port"]["type"] == "string"

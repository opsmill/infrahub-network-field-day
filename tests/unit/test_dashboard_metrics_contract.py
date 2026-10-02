"""Every Grafana panel queries a series something in this lab actually produces.

A dashboard is reviewed as JSON and rendered by Grafana, and neither step knows
what Prometheus holds. A panel naming a metric no collector produces does not
fail anywhere: it reads "No data", indistinguishable from a quiet network. A
family re-platformed underneath its dashboard (FRR to SR Linux, frr_exporter to
gNMI) is exactly that change, and nothing but this file would notice.

So the produced set is DERIVED, not listed:

* **The collector's series** come from rendering the real collector intent (the
  same fixture test_telemetry_collector_config uses): every gNMI subscription,
  SNMP table and node-exporter metric the artifact asks Telegraf for, named the
  way Telegraf's prometheus_client output names them, and per device kind. A
  panel may only filter `kind="X"` for a kind that really reports the series.
* **gNMI field names** cannot be derived from a path, so ``GNMI_FIELDS`` is the
  one measured catalogue here: what Telegraf 1.40 reported for each subscription
  against EOS and SR Linux on the live lab. Its keys must equal the
  subscriptions the transform renders, so a new subscription forces an entry.
* **The exporter's series** come from metrics/exporter.yml.
* **The service-lifecycle exporter's series** (cycle 035) come from the module
  that produces them, and count only if the rendered artifact scrapes it.
* **Probe series** come from a render in which one application admits the
  collector at its pod gate, because the seeded ones all refuse it -- so the
  probe panel is held to a series a probe WOULD produce, not to nothing.
* **Cluster series** (Hubble, the kubelet, kube-state-metrics) are a short list,
  each tied to the scrape job in the otternet-metrics values that produces it.

Annotations are queries too, and are held to the same rule.

This file needs no running lab.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

from solution_arista_avd.service_lifecycle import HELP as LIFECYCLE_SERIES
from tests.unit.test_telemetry_collector_config import _data, _render
from transforms.telemetry_services import LIFECYCLE_EXPORTER

REPO = Path(__file__).resolve().parents[2]
DASHBOARDS = sorted((REPO / "payloads" / "dashboards").glob("*.json"))
VALUES = REPO / "payloads" / "otternet-metrics-values.yaml"

# subscription name -> numeric fields Telegraf emits for it (string fields are
# dropped by the prometheus output, which is why session_state and oper_status
# are absent and their enum codes are added from the rendered processors).
# Measured with telegraf:1.40-alpine against cEOS and SR Linux 26.7.
GNMI_FIELDS: dict[str, set[str]] = {
    "interface_counters": {
        "in_octets",
        "out_octets",
        "in_pkts",
        "out_pkts",
        "in_unicast_pkts",
        "out_unicast_pkts",
        "in_broadcast_pkts",
        "out_broadcast_pkts",
        "in_multicast_pkts",
        "out_multicast_pkts",
        "in_errors",
        "out_errors",
        "in_discards",
        "out_discards",
        "in_fcs_errors",
        "carrier_transitions",
        "interface_transitions",
        "link_transitions",
        "last_update",
    },
    "interface_status": set(),
    "bgp_neighbor": {
        "enabled",
        "established_transitions",
        "last_established",
        "last_prefix_limit_exceeded",
        "local_as",
        "peer_as",
        "neighbor_port",
        "next_hop_self",
        "messages_received_UPDATE",
        "messages_received_NOTIFICATION",
        "messages_received_last_notification_time",
        "messages_sent_UPDATE",
        "messages_sent_NOTIFICATION",
        "queues_input",
        "queues_output",
    },
    "bgp_afi_safi": {"received", "received_pre_policy", "sent", "installed", "best_paths", "best_ecmp_paths"},
    "cpu": {"instant", "avg", "min", "max", "interval", "min_time", "max_time"},
    "memory": {"available", "utilized"},
}

# Series scraped from the cluster rather than through the collector, and the
# scrape job each comes from. `kubelet` is the chart's own ServiceMonitor.
CLUSTER_SERIES: dict[str, str] = {
    "hubble_flows_processed_total": "hubble",
    "hubble_drop_total": "hubble",
    "container_cpu_usage_seconds_total": "kubelet",
    "container_memory_working_set_bytes": "kubelet",
    # The application checks on the Services dashboard (cycle 035): pods ready
    # and the LoadBalancer address assigned, joined to intent by namespace.
    "kube_deployment_status_replicas_available": "kube-state-metrics",
    "kube_deployment_status_replicas_unavailable": "kube-state-metrics",
    "kube_service_status_load_balancer_ingress": "kube-state-metrics",
    "up": "",
}

# Telegraf's net_response fields that survive the prometheus output (result_type
# is a string and is dropped).
NET_RESPONSE_FIELDS = {"response_time", "result_code"}

_KEYWORDS = {"by", "without", "on", "ignoring", "group_left", "group_right", "and", "or", "unless", "bool", "offset"}


def _metrics_in(expr: str) -> set[str]:
    """Metric names in a PromQL expression: identifiers that are not functions,
    keywords, label names or string contents."""
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', expr)
    text = re.sub(r"\{[^{}]*\}", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\b(?:by|without|on|ignoring|group_left|group_right)\s*\([^)]*\)", " ", text)
    names = set()
    for match in re.finditer(r"(?<![\w$.])([A-Za-z_:][\w:]*)(\s*\()?", text):
        name, call = match.group(1), match.group(2)
        if call or name in _KEYWORDS:
            continue
        names.add(name)
    return names


def _selectors(expr: str) -> list[tuple[str, str]]:
    """(metric, selector body) for every `metric{...}` in the expression."""
    return re.findall(r"([A-Za-z_:][\w:]*)\{([^{}]*)\}", expr)


def _panels(board: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for panel in board["panels"]:
        out.append(panel)
        out.extend(panel.get("panels", []))
    return out


def _targets() -> list[tuple[str, str, str]]:
    found = []
    for path in DASHBOARDS:
        board = json.loads(path.read_text(encoding="utf-8"))
        found.extend(
            (path.stem, panel["title"], target["expr"])
            for panel in _panels(board)
            for target in panel.get("targets", [])
        )
        found.extend(
            (path.stem, f"annotation: {a['name']}", a["expr"])
            for a in board.get("annotations", {}).get("list", [])
            if a.get("expr")
        )
    return found


def _probe_render() -> dict[str, Any]:
    """The collector's render with Grafana's pod gate open, so a probe is rendered."""
    data = _data()
    for edge in data["ServiceGeneric"]["edges"]:
        if edge["node"]["name"]["value"] == "otternet-metrics":
            edge["node"]["policy_default_deny"]["value"] = False
            edge["node"]["allowed_source_prefixes"]["count"] = 0
    return _render(data)[0]


def _collector_series() -> dict[str, set[str]]:  # noqa: C901 - one artifact, every kind of input it renders
    """Metric name -> the device kinds whose inputs produce it, from the rendered artifact."""
    out, _ = _render()
    conf = tomllib.loads(out["manifest"]["data"]["telegraf.conf"])
    produced: dict[str, set[str]] = {}
    probes = tomllib.loads(_probe_render()["manifest"]["data"]["telegraf.conf"])["inputs"].get("net_response", [])
    assert probes, "the probe render rendered no probe"
    for field in NET_RESPONSE_FIELDS:
        produced.setdefault(f"net_response_{field}", set())

    def add(name: str, kind: str) -> None:
        produced.setdefault(name, set()).add(kind)

    subscriptions: dict[str, set[str]] = {}
    for block in conf["inputs"].get("gnmi", []):
        kind = block["tags"]["kind"]
        for sub in block["subscription"]:
            subscriptions.setdefault(sub["name"], set()).add(kind)
            for field in GNMI_FIELDS.get(sub["name"], set()):
                add(f"{sub['name']}_{field}", kind)
    for enum in conf["processors"].get("enum", []):
        for measurement in enum["namepass"]:
            for mapping in enum["mapping"]:
                for kind in subscriptions.get(measurement, set()):
                    add(f"{measurement}_{mapping['dest']}", kind)
    for block in conf["inputs"].get("snmp", []):
        for table in block.get("table", []):
            for field in table["field"]:
                if not field.get("is_tag"):
                    add(f"{table['name']}_{field['name']}", block["tags"]["kind"])
    for block in conf["inputs"].get("prometheus", []):
        if any(url.startswith(LIFECYCLE_EXPORTER) for url in block["urls"]):
            for name in LIFECYCLE_SERIES:
                produced.setdefault(name, set())
            continue
        for name in block["fieldinclude"]:
            add(name, block["tags"]["kind"])
    for line in out["manifest"]["data"]["intended.prom"].splitlines():
        if line.startswith("# TYPE "):
            produced.setdefault(line.split()[2], set())
    return produced


def _exporter_series() -> set[str]:
    config = yaml.safe_load((REPO / "metrics" / "exporter.yml").read_text(encoding="utf-8"))
    return {f"infrahub_{entry['kind'].lower()}_info" for entry in config["metrics"]["kind"]}


def _values() -> dict[str, Any]:
    return yaml.safe_load(VALUES.read_text(encoding="utf-8"))


def test_the_gnmi_catalogue_covers_exactly_the_rendered_subscriptions() -> None:
    out, _ = _render()
    conf = tomllib.loads(out["manifest"]["data"]["telegraf.conf"])
    rendered = {sub["name"] for block in conf["inputs"]["gnmi"] for sub in block["subscription"]}
    assert rendered == set(GNMI_FIELDS), f"measure and catalogue: {sorted(rendered ^ set(GNMI_FIELDS))}"


def test_every_cluster_series_has_the_scrape_job_that_produces_it() -> None:
    values = _values()
    jobs = {job["job_name"] for job in values["prometheus"]["prometheusSpec"]["additionalScrapeConfigs"]}
    jobs.add("kubelet")  # the chart's kubelet ServiceMonitor, left enabled
    assert values.get("kubelet", {}).get("enabled", True) is not False
    jobs.add("kube-state-metrics")  # the chart's own, left enabled
    assert values.get("kubeStateMetrics", {}).get("enabled", True) is not False
    for metric, job in CLUSTER_SERIES.items():
        assert not job or job in jobs, f"{metric} needs the {job!r} scrape job"


@pytest.mark.parametrize(("board", "title", "expr"), _targets())
def test_every_panel_queries_a_series_that_is_produced(board: str, title: str, expr: str) -> None:
    produced = _collector_series()
    known = set(produced) | _exporter_series() | set(CLUSTER_SERIES)
    missing = sorted(_metrics_in(expr) - known)
    assert not missing, f"{board} / {title!r} queries {missing}, which nothing in the lab produces"
    for metric, body in _selectors(expr):
        kind = re.search(r'\bkind="([^"]+)"', body)
        if kind and metric in produced and produced[metric]:
            assert kind.group(1) in produced[metric], (
                f"{board} / {title!r}: {metric} is never reported with kind={kind.group(1)} "
                f"(only {sorted(produced[metric])})"
            )


def test_the_extractor_finds_metrics_and_ignores_everything_else() -> None:
    expr = (
        'count(otternet_intended_bgp_neighbor{kind="DcimDevice", device=~"$device"} unless on (device, peer_address) '
        '(label_replace(bgp_neighbor_session_state_code{kind="DcimDevice"}, "peer_address", "$1", "neighbor_address", '
        '"(.*)") == 6)) or vector(0) + sum by (x) (rate(made_up_total[$__rate_interval]))'
    )
    assert _metrics_in(expr) == {"otternet_intended_bgp_neighbor", "bgp_neighbor_session_state_code", "made_up_total"}
    # A metric no collector produces is what the contract test exists to catch.
    known = set(_collector_series()) | _exporter_series() | set(CLUSTER_SERIES)
    assert "made_up_total" not in known
    assert "frr_bgp_peer_state" not in known


def test_every_dashboard_is_consistent() -> None:
    """Refresh 1m (a k3s node is one CPU), one datasource, the shared links, and
    a description and a unit wherever a reader needs one."""
    for path in DASHBOARDS:
        board = json.loads(path.read_text(encoding="utf-8"))
        assert board["refresh"] == "1m", path.name
        assert "otternet" in board["tags"], path.name
        assert board.get("description"), path.name
        assert any(
            link.get("type") == "dashboards" and "otternet" in link.get("tags", []) for link in board["links"]
        ), f"{path.name} has no link to the other OTTERNET dashboards"
        for panel in _panels(board):
            if panel["type"] == "row":
                continue
            assert panel.get("description"), f"{path.name} / {panel['title']} has no description"
            assert panel["datasource"] == {"type": "prometheus", "uid": "prometheus"}, panel["title"]
            for target in panel["targets"]:
                assert target["datasource"]["uid"] == "prometheus", panel["title"]
            if panel["type"] == "timeseries":
                assert panel["fieldConfig"]["defaults"].get("unit"), f"{path.name} / {panel['title']} has no unit"
        for variable in board.get("templating", {}).get("list", []):
            uses = f"${variable['name']}"
            assert any(uses in t["expr"] for p in _panels(board) for t in p.get("targets", [])), (
                f"{path.name}: variable {variable['name']} is declared and never used"
            )


def test_grafana_can_query_and_offers_no_dead_datasource() -> None:
    """Without `preinstall_disabled` Grafana 13 unregisters its own Prometheus
    plugin on a read-only root and every panel reads "No data" (measured)."""
    grafana = _values()["grafana"]
    assert grafana["grafana.ini"]["plugins"]["preinstall_disabled"] is True
    assert _values()["alertmanager"]["enabled"] is False
    assert grafana["sidecar"]["datasources"]["alertmanager"]["enabled"] is False


def test_the_kubelet_is_scraped_through_one_fixed_service() -> None:
    """A generated release name left a second kubelet Service behind and every
    kubelet series was scraped twice (measured). A fixed name is reused."""
    assert _values()["prometheusOperator"]["kubeletService"]["name"] == "otternet-metrics-kubelet"


def test_the_services_dashboard_names_no_service_and_no_kind() -> None:
    """It needs no edit when a service or a kind appears: every panel is driven by
    labels and the $kind/$owner/$service variables, never by a literal (cycle 035)."""
    board = json.loads((REPO / "payloads" / "dashboards" / "services.json").read_text(encoding="utf-8"))
    assert board["uid"] == "otternet-services"
    assert board["title"] == "OTTERNET / Services"
    exprs = [t["expr"] for p in _panels(board) for t in p.get("targets", [])]
    exprs += [a["expr"] for a in board["annotations"]["list"]]
    for expr in exprs:
        assert not re.search(r'\bservice(_kind)?="[^"$]', expr), expr
        assert "Service" not in re.sub(r'"[^"]*"', "", expr), f"a kind is named outside a label value: {expr}"
    assert {v["name"] for v in board["templating"]["list"]} == {"kind", "owner", "service"}
    assert {a["name"] for a in board["annotations"]["list"]} == {"Service events", "Proposed changes merged"}


def test_the_organisation_home_leads_to_the_services_dashboard() -> None:
    board = json.loads((REPO / "payloads" / "dashboards" / "organisation.json").read_text(encoding="utf-8"))
    tiles = [p for p in board["panels"] if p["type"] == "stat" and p["gridPos"]["y"] == 1]
    assert sum(p["gridPos"]["w"] for p in tiles) == 24, "the health row is one full row of tiles"
    linked = [p["title"] for p in tiles if any(link["url"] == "/d/otternet-services" for link in p.get("links", []))]
    assert linked == ["Service requests stalled", "Services failing a check"]

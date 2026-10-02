"""Seed-data tests for the chart-only fabric application (objects/36).

Cycle 033 made a Helm chart the only way to express an application. The
assertions worth having here are the ones that catch a seeded application which
loads cleanly and then does nothing useful -- because every failure this file
guards against is silent:

  * an incomplete chart is refused by the schema, so it needs no test here;
  * a chart whose Service port disagrees with the SecurityService the
    application names produces a firewall rule permitting the wrong port, which
    renders, merges, pushes and confirms while reaching nothing;
  * a selector naming a label the chart does not emit matches no endpoint, and a
    CiliumNetworkPolicy that matches nothing protects nothing and reports no
    fault.

The chart's own defaults are the oracle for the last two. They are recorded as
constants rather than refetched, because a test that reaches the network is a
test that fails when the network does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

OBJECT_FILE = Path("objects/36_otternet_app_services.yml")
PAYLOAD_DIR = Path("payloads")
VALUES_FILE = PAYLOAD_DIR / "otternet-demo-values.yaml"

# cowboysysop/whoami, verified against the repository's own index.yaml and
# templates at the time this was pinned:
#   chart 6.0.0 -> appVersion 1.11.0 -> traefik/whoami:v1.11.0
#   service.ports.http: 80, containerPorts.http: 80
#   whoami.selectorLabels emits app.kubernetes.io/{name,instance,component}
CHART_REPOSITORY = "https://cowboysysop.github.io/charts/"
CHART_NAME = "whoami"
CHART_VERSION = "6.0.0"
CHART_SERVICE_PORT = 80
CHART_STABLE_POD_LABEL = "app.kubernetes.io/name"


def _docs() -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(OBJECT_FILE.read_text(encoding="utf-8")) if d]


def _data(kind: str) -> list[dict[str, Any]]:
    for doc in _docs():
        if doc.get("spec", {}).get("kind") == kind:
            return doc["spec"]["data"]
    pytest.fail(f"no {kind} block in {OBJECT_FILE}")


def _demo() -> dict[str, Any]:
    for entry in _data("ServiceFabricApp"):
        if entry.get("name") == "otternet-demo":
            return entry
    pytest.fail("otternet-demo is not in the seed data")


def _values() -> dict[str, Any]:
    return yaml.safe_load(VALUES_FILE.read_text(encoding="utf-8"))


def test_the_seeded_application_names_a_complete_chart() -> None:
    """033 FR-010 to FR-012, SC-006. All three, or the cluster rejects it."""
    demo = _demo()

    assert demo["chart_repository"] == CHART_REPOSITORY
    assert demo["chart_name"] == CHART_NAME
    assert demo["chart_version"] == CHART_VERSION


def test_no_manifests_payload_survives() -> None:
    """033 FR-042, SC-003. The escape hatch is gone, including its file.

    `scripts/seed_app_payloads.py` would raise `SchemaNotFoundError` on the
    withdrawn kind rather than quietly skipping, but a leftover payload file
    with no uploader is the kind of thing that sits in a tree for a year.
    """
    demo = _demo()

    assert "manifests" not in demo
    assert "manifests_file" not in demo

    leftovers = sorted(p.name for p in PAYLOAD_DIR.glob("*manifests*"))
    assert leftovers == [], f"manifests payloads still present: {leftovers}"


def test_the_application_names_the_service_its_vip_answers_on() -> None:
    """033 FR-024, SC-008. The relationship a grant reads instead of manifests.

    `junos-http` rather than a new object, because the firewall already declares
    it -- which is what keeps the rendered Junos artifact byte-identical.
    """
    demo = _demo()

    assert demo["advertised_services"] == ["junos-http"]


def test_the_named_service_agrees_with_the_charts_port() -> None:
    """The failure this whole file exists for.

    `junos-http` is 80/tcp. If the chart's Service answered on anything else,
    every generated rule would permit a port the VIP does not serve -- and
    nothing downstream reports that: the rule renders, the proposed change
    merges, the reconciler pushes it and confirms the firewall in sync, and the
    only symptom is a healthy application nobody can reach.
    """
    values = _values()
    service_port = values["service"]["ports"]["http"]

    assert service_port == CHART_SERVICE_PORT

    # junos-http's port, from the seed data that declares it rather than from a
    # number repeated here.
    security = list(yaml.safe_load_all(Path("objects/32_otternet_security.yml").read_text(encoding="utf-8")))
    services = [
        entry
        for doc in security
        if doc and doc.get("spec", {}).get("kind") == "SecurityService"
        for entry in doc["spec"]["data"]
    ]
    junos_http = next(entry for entry in services if entry["name"] == "junos-http")

    assert junos_http["port"] == service_port
    assert junos_http["ip_protocol"] == "tcp"


def test_the_service_is_labelled_so_it_is_actually_advertised() -> None:
    """A LoadBalancer Service is not exposed to the fabric merely by being one.

    The XRD's `expose.serviceSelector` decides which Services get a VIP, and the
    application's `service_selector` is what it is set from. If the chart does
    not put that label on the Service, the Service is created, gets no VIP, and
    the application is unreachable off-cluster with nothing reporting a fault.
    """
    demo = _demo()
    values = _values()

    assert values["service"]["type"] == "LoadBalancer"

    selectors = {entry.split("=", 1)[0]: entry.split("=", 1)[1] for entry in demo["service_selector"]}
    labels = {str(key): str(value) for key, value in values["commonLabels"].items()}

    assert selectors == labels, "commonLabels must carry every label service_selector matches on"


def test_the_workload_selector_names_a_label_the_chart_emits() -> None:
    """A policy selecting nothing protects nothing, silently.

    `app=frontend` was set by the hand-written Deployment the chart replaced.
    `app.kubernetes.io/name` is chart-derived and stable;
    `app.kubernetes.io/instance` follows the release name and is not.
    """
    demo = _demo()

    keys = [entry.split("=", 1)[0] for entry in demo["workload_selector"]]

    assert keys == [CHART_STABLE_POD_LABEL]
    assert "app" not in keys


def test_the_pod_policy_port_matches_the_container_port() -> None:
    """`policy_allow_ports` is applied to the PODS, not to the VIP.

    These are two different questions and were two different numbers under the
    old manifests, whose Service mapped 80 to targetPort 8080. The chart's
    `containerPorts.http` is 80, so they now agree -- but the reason they agree
    is arithmetic about this chart, not a rule, which is why it is asserted.
    """
    demo = _demo()
    ports = {int(entry["port"]) for entry in demo["policy_allow_ports"]}

    assert ports == {CHART_SERVICE_PORT}


# ---------------------------------------------------------------------------
# Cycle 034: the observability applications.
#
# Grafana and Prometheus (`otternet-metrics`) and Telegraf
# (`otternet-telemetry`) are ordinary seeded applications delivered by Vidra.
# The lab's own `otternet-observability` claim is what they replace, and the
# new names differ from it on purpose: Vidra refuses to adopt a resource it did
# not create, so a shared name would leave whichever writer got there first in
# charge.
# ---------------------------------------------------------------------------

GRAFANA_BLOCK = "10.112.240.80/28"
GRAFANA_VIP = "10.112.240.81"
OBSERVABILITY_APPS = ("otternet-metrics", "otternet-telemetry")


def _app(name: str) -> dict[str, Any]:
    for entry in _data("ServiceFabricApp"):
        if entry.get("name") == name:
            return entry
    pytest.fail(f"{name} is not in the seed data")


def test_the_observability_applications_are_complete_charts_with_payloads() -> None:
    for name in OBSERVABILITY_APPS:
        app = _app(name)
        for field in ("chart_repository", "chart_name", "chart_version"):
            assert app.get(field), f"{name} is missing {field}"
        assert (PAYLOAD_DIR / f"{name}-values.yaml").is_file(), name
        assert "service_fabric_apps" in app.get("member_of_groups", []), name
        assert name != "otternet-observability", "that name is the lab's claim, which the handover deletes"


def test_grafana_is_exposed_on_a_seeded_block_and_answers_on_junos_http() -> None:
    metrics = _app("otternet-metrics")
    assert metrics["exposed"] is True
    assert metrics["vip_block"] == [GRAFANA_BLOCK, "default"]
    assert metrics["advertised_services"] == ["junos-http"]
    assert metrics["sso_provider"] == "dex"

    values = yaml.safe_load((PAYLOAD_DIR / "otternet-metrics-values.yaml").read_text(encoding="utf-8"))
    service = values["grafana"]["service"]
    assert service["type"] == "LoadBalancer"
    assert service["port"] == CHART_SERVICE_PORT, "the VIP must answer on junos-http's port"
    # The address Dex's redirect URI names. Allocated rather than pinned, it
    # would be whichever address Cilium chose first and could differ between
    # rebuilds, and Dex is configured before anything here exists.
    assert service["annotations"]["lbipam.cilium.io/ips"] == GRAFANA_VIP


def test_grafanas_pod_gate_exists_before_any_grant() -> None:
    """The third gate must hold from the start, not appear with the first grant.

    The composition renders `allow-ingress` only when `allowFrom` is non-empty,
    and with default deny off that policy is the only thing narrowing Grafana's
    ingress. Seeding the cluster's own pod prefix makes it exist from the first
    render, so a branch packet that got past the firewall is still dropped at
    the pod until a grant names its source.
    """
    metrics = _app("otternet-metrics")
    assert metrics["policy_default_deny"] is False
    assert ["10.111.0.0/16", "default"] in metrics["allowed_source_prefixes"]
    assert ["10.70.0.0/24", "default"] not in metrics["allowed_source_prefixes"], (
        "the branch is what a grant adds; seeding it would make the request meaningless"
    )
    assert metrics["workload_selector"] == ["app.kubernetes.io/name=grafana"]
    assert metrics["policy_allow_ports"] == [{"port": "3000", "protocol": "TCP"}]


def test_telemetry_is_cluster_internal() -> None:
    telemetry = _app("otternet-telemetry")
    assert telemetry["exposed"] is False
    assert "vip_block" not in telemetry


def test_the_grafana_block_is_seeded_inside_the_pool_and_overlaps_nothing() -> None:
    """Seeded, so OTTERNET-VIP-Pool skips it.

    The lab's own Grafana block was picked by hand with no IpamPrefix behind it,
    and the allocator -- which decides what is free by reading its own records --
    handed the same block to a portal request. Recording it is the fix.
    """
    import ipaddress

    prefixes = [
        entry
        for doc in yaml.safe_load_all(Path("objects/29_otternet_offfabric_prefixes.yml").read_text(encoding="utf-8"))
        if doc and doc.get("spec", {}).get("kind") == "IpamPrefix"
        for entry in doc["spec"]["data"]
    ]
    block = ipaddress.ip_network(GRAFANA_BLOCK)
    pool = ipaddress.ip_network("10.112.240.0/24")
    assert any(p["prefix"] == GRAFANA_BLOCK and p.get("role") == "vip_pool" for p in prefixes)
    assert block.subnet_of(pool)
    others = [
        ipaddress.ip_network(p["prefix"])
        for p in prefixes
        if p.get("role") == "vip_pool" and p["prefix"] not in (GRAFANA_BLOCK, str(pool))
    ]
    assert not [o for o in others if o.overlaps(block)]


def test_every_dashboard_parses_and_has_a_unique_uid() -> None:
    import json

    uids = []
    for board in sorted((PAYLOAD_DIR / "dashboards").glob("*.json")):
        loaded = json.loads(board.read_text(encoding="utf-8"))
        assert loaded.get("uid"), board.name
        assert loaded.get("panels"), f"{board.name} has no panels"
        uids.append(loaded["uid"])
    assert uids, "no dashboards found"
    assert len(uids) == len(set(uids)), uids


def test_dashboards_are_folded_into_the_metrics_payload_deterministically() -> None:
    """The attachment is assembled; an unchanged tree must give unchanged bytes,
    or every `invoke load` re-uploads and moves the artifact's checksum."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("seed_app_payloads", Path("scripts/seed_app_payloads.py"))
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    path = PAYLOAD_DIR / "otternet-metrics-values.yaml"
    first = module.assemble_payload("otternet-metrics", path)
    assert first == module.assemble_payload("otternet-metrics", path)
    values = yaml.safe_load(first)
    boards = values["grafana"]["dashboards"]["otternet"]
    assert set(boards) == {p.stem for p in (PAYLOAD_DIR / "dashboards").glob("*.json")}
    provider = values["grafana"]["dashboardProviders"]["dashboardproviders.yaml"]["providers"][0]
    assert provider["options"]["path"] == "/var/lib/grafana/dashboards/otternet"
    # Every other application's payload is attached exactly as committed.
    demo = PAYLOAD_DIR / "otternet-demo-values.yaml"
    assert module.assemble_payload("otternet-demo", demo) == demo.read_bytes()


def test_the_observability_apps_render_no_policy_but_grafanas_gate() -> None:
    """With default deny off, every `allow-*` flag must be off too.

    The composition renders a CiliumNetworkPolicy per true flag, and any policy
    selecting a pod makes that direction deny-by-default for it. `allow-dns`
    on otternet-metrics made Prometheus's egress default-deny, and
    `allow-intra-namespace` on otternet-telemetry refused Prometheus's scrape
    from the other namespace -- measured with Telegraf, most kubelets, Cilium,
    Hubble and CoreDNS all down. Grafana's gate is `allowed_source_prefixes`,
    which renders `allow-ingress` on its pods only.
    """
    for name in OBSERVABILITY_APPS:
        app = _app(name)
        assert app["policy_default_deny"] is False, name
        flags = {k: v for k, v in app.items() if k.startswith("policy_allow_") and k != "policy_allow_ports"}
        assert flags, name
        assert not any(flags.values()), f"{name}: {flags}"
    assert _app("otternet-metrics")["allowed_source_prefixes"], "Grafana's pod gate must still exist"


def test_every_exposed_seeded_application_keeps_the_client_address() -> None:
    """`externalTrafficPolicy: Local` on every exposed application's Service.

    With the charts' default, `Cluster`, a request landing on a node whose chosen
    backend is elsewhere is SNATed to that node's address. Measured on
    otternet-demo: 4 of 6 requests from host-a reached whoami as 10.110.0.x, so
    the pod policy admitted them as `remote-node` rather than on their source
    prefix, and `allowed_source_prefixes` decided nothing for most of them.

    Asserted on the payload AND on what the transform renders from it: the
    payload states it so it reads truthfully, and the transform is what holds
    every application to it, including ones the portal creates.
    """
    from transforms.crossplane_fabric_app import apply_local_traffic

    exposed = [app for app in _data("ServiceFabricApp") if app.get("exposed")]
    assert {app["name"] for app in exposed} == {"otternet-demo", "otternet-metrics"}

    service_path = {"whoami": ("service",), "kube-prometheus-stack": ("grafana", "service")}
    for app in exposed:
        values = yaml.safe_load((PAYLOAD_DIR / f"{app['name']}-values.yaml").read_text(encoding="utf-8"))
        rendered = apply_local_traffic(exposed=True, chart=app["chart_name"], values=values, name=app["name"])
        for label, tree in (("payload", values), ("rendered", rendered)):
            service = tree
            for key in service_path[app["chart_name"]]:
                service = service[key]
            assert service["type"] == "LoadBalancer", f"{app['name']} {label}"
            assert service["externalTrafficPolicy"] == "Local", f"{app['name']} {label}"
        # The payload already says it, so enforcing it changes nothing -- which
        # is what keeps the rendered manifest a one-line diff for the demo and
        # byte-identical for Grafana.
        assert rendered == values, app["name"]

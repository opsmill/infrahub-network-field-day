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

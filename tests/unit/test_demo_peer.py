"""`invoke demo-break-peer`: choosing a node that is safe to break, and reading the leaves."""

from __future__ import annotations

from typing import Any

from solution_arista_avd import demo_peer as dp


def _service(namespace: str, name: str, kind: str = "LoadBalancer") -> dict[str, Any]:
    return {"metadata": {"namespace": namespace, "name": name}, "spec": {"type": kind}}


def _slice(namespace: str, service: str, *nodes: str, ready: bool = True) -> dict[str, Any]:
    return {
        "metadata": {"namespace": namespace, "labels": {"kubernetes.io/service-name": service}},
        "endpoints": [{"nodeName": node, "conditions": {"ready": ready}} for node in nodes],
    }


# The lab as measured on 2026-10-19: the demo application on every node, DNS and Grafana on k8s-node2 only.
SERVICES = {
    "items": [
        _service("otternet-demo", "whoami"),
        _service("otternet-dns", "lab-dns"),
        _service("otternet-metrics", "grafana"),
        _service("kube-system", "kube-dns", kind="ClusterIP"),
    ]
}
SLICES = {
    "items": [
        _slice("otternet-demo", "whoami", "k8s-node1", "k8s-node2", "k8s-node3"),
        _slice("otternet-dns", "lab-dns", "k8s-node2"),
        _slice("otternet-metrics", "grafana", "k8s-node2"),
        _slice("kube-system", "kube-dns", "k8s-node3"),
    ]
}


def test_the_default_node_backs_no_service_alone() -> None:
    assert dp.sole_backed_services(SERVICES, SLICES, dp.DEFAULT_NODE) == []


def test_breaking_the_dns_node_is_refused() -> None:
    assert dp.sole_backed_services(SERVICES, SLICES, "k8s-node2") == [
        "otternet-dns/lab-dns",
        "otternet-metrics/grafana",
    ]


def test_a_cluster_ip_service_never_counts() -> None:
    # kube-dns is on k8s-node3 only, but it has no address announced into the fabric.
    assert "kube-system/kube-dns" not in dp.sole_backed_services(SERVICES, SLICES, "k8s-node3")


def test_an_endpoint_that_is_not_ready_is_ignored() -> None:
    slices = {"items": [_slice("otternet-metrics", "grafana", "k8s-node2", ready=False)]}
    assert dp.sole_backed_services(SERVICES, slices, "k8s-node2") == []


SUMMARY = {
    "vrfs": {
        "K8S_PROD": {
            "peers": {
                "10.110.0.12": {"asn": "65401", "peerState": "Established"},
                "10.110.0.13": {"asn": "64501", "peerState": "Active"},
            }
        }
    }
}


def test_leaf_peer_reads_the_expected_as_and_state() -> None:
    assert dp.leaf_peer(SUMMARY, "10.110.0.13") == (64501, "Active")
    assert dp.leaf_peer(SUMMARY, "10.110.0.99") == (None, "missing")


def test_breaking_is_done_once_the_leaf_runs_the_wrong_as() -> None:
    assert dp.leaf_reached(64501, "Active", dp.WRONG_ASN, broken=True)
    assert not dp.leaf_reached(65401, "Established", dp.WRONG_ASN, broken=True)


def test_fixing_is_done_only_once_the_session_is_up() -> None:
    assert not dp.leaf_reached(65401, "OpenSent", 65401, broken=False)
    assert dp.leaf_reached(65401, "Established", 65401, broken=False)

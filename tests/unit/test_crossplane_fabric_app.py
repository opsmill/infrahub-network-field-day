"""Unit tests for the Crossplane FabricApp manifest transform.

Fixtures rather than a live server: several validation paths are unreachable
against a live instance because the schema forbids the shapes, and the pure
functions below need no client.

The transform's IO -- downloading an attachment -- is deliberately not exercised
here. It is covered by the live render recorded in acceptance-evidence.md, where
the whole payload round-trips and is compared with the hand-written manifest.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from transforms.crossplane_fabric_app import (
    CrossplaneFabricAppTransform,
    build_expose,
    build_policy,
    parse_selector,
)
from transforms.crossplane_fabric_app_query import CrossplaneFabricAppQuery

VIP_BLOCK = "10.112.240.0/28"
ALLOW_FROM = ["10.210.0.0/24", "10.60.0.0/16", "10.70.0.0/24"]


def _data(
    *,
    exposed: bool = True,
    vip_block: str | None = VIP_BLOCK,
    service_selector: list[str] | None = None,
    workload_selector: list[str] | None = None,
    allowed: list[str] | None = None,
    ports: list[dict[str, Any]] | None = None,
    namespace: str | None = "nfd41-demo",
    vrf: str | None = "K8S_PROD",
    intra: bool = True,
) -> CrossplaneFabricAppQuery:
    if service_selector is None:
        service_selector = ["nfd41.lab/advertise=true"]
    if workload_selector is None:
        workload_selector = ["app=frontend"]
    if allowed is None:
        allowed = ALLOW_FROM
    if ports is None:
        ports = [{"port": "8080", "protocol": "TCP"}]
    return CrossplaneFabricAppQuery(
        target={
            "edges": [
                {
                    "node": {
                        "id": "app-1",
                        "name": {"value": "nfd41-demo"},
                        "namespace_name": ({"value": namespace} if namespace else None),
                        "exposed": {"value": exposed},
                        "chart_repository": None,
                        "chart_name": None,
                        "chart_version": None,
                        "chart_values": None,
                        "service_selector": {"value": service_selector},
                        "communities": None,
                        "workload_selector": {"value": workload_selector},
                        "policy_default_deny": {"value": True},
                        "policy_allow_dns": {"value": True},
                        "policy_allow_intra_namespace": {"value": intra},
                        "policy_allow_egress_api_server": {"value": False},
                        "policy_allow_egress_internet": {"value": False},
                        "policy_allow_ports": {"value": ports},
                        "vrf": ({"node": {"id": "vrf-1", "name": {"value": vrf}}} if vrf else {"node": None}),
                        "vip_block": (
                            {"node": {"id": "pfx-1", "prefix": {"value": vip_block}}} if vip_block else {"node": None}
                        ),
                        "allowed_source_prefixes": {
                            "edges": [{"node": {"id": f"p-{p}", "prefix": {"value": p}}} for p in allowed]
                        },
                        "values_file": {"node": None},
                    }
                }
            ]
        }
    )


def _app(**kwargs: Any) -> Any:
    return _data(**kwargs).target.edges[0].node


# ---------------------------------------------------------------------------
# Selectors and type discipline
# ---------------------------------------------------------------------------


def test_selector_becomes_a_label_map() -> None:
    """Stored as key=value strings because Infrahub 1.10.6 returns a 500 for a
    JSON key containing a dot or a slash, and every label selector has both."""
    assert parse_selector(["nfd41.lab/advertise=true"], field="s") == {"nfd41.lab/advertise": "true"}


def test_selector_value_may_contain_an_equals_sign() -> None:
    """Split on the FIRST = only."""
    assert parse_selector(["k=a=b"], field="s") == {"k": "a=b"}


def test_malformed_selector_raises_naming_the_entry() -> None:
    """Dropping it silently would leave a selector matching more than intended,
    which for a workload selector means a policy applying to workloads nobody
    chose."""
    with pytest.raises(ValueError, match="no-equals"):
        parse_selector(["no-equals"], field="workload_selector")


def test_label_values_stay_strings() -> None:
    """A Kubernetes label map is map[string]string; an unquoted true would come
    back a boolean and the API would reject it."""
    expose = build_expose(_app())

    assert expose["serviceSelector"]["nfd41.lab/advertise"] == "true"
    assert isinstance(expose["serviceSelector"]["nfd41.lab/advertise"], str)


def test_ports_render_as_strings() -> None:
    """The XRD types allowFromPorts[].port as a string, not an integer."""
    policy = build_policy(_app(ports=[{"port": 8080, "protocol": "TCP"}]))

    assert policy["allowFromPorts"] == [{"port": "8080", "protocol": "TCP"}]


def test_port_protocol_defaults_to_tcp() -> None:
    policy = build_policy(_app(ports=[{"port": "80"}]))

    assert policy["allowFromPorts"][0]["protocol"] == "TCP"


# ---------------------------------------------------------------------------
# Policy -- the security-relevant field
# ---------------------------------------------------------------------------


def test_allow_from_lists_every_prefix() -> None:
    """SC-005. These are the networks permitted to reach the application: the
    third of three independent gates, and the field where a silent change is
    most damaging."""
    policy = build_policy(_app())

    assert policy["allowFrom"] == sorted(ALLOW_FROM)


def test_allow_from_is_sorted_for_determinism() -> None:
    policy = build_policy(_app(allowed=list(reversed(ALLOW_FROM))))

    assert policy["allowFrom"] == sorted(ALLOW_FROM)


def test_every_policy_flag_is_rendered() -> None:
    """All five are required on the node, so all five always appear."""
    policy = build_policy(_app())

    assert set(policy) >= {
        "defaultDeny",
        "allowDNS",
        "allowIntraNamespace",
        "allowEgressToAPIServer",
        "allowEgressToInternet",
    }


# ---------------------------------------------------------------------------
# Exposure
# ---------------------------------------------------------------------------


def test_unexposed_app_has_no_expose_block() -> None:
    """Emitting expose with a null vipBlock would override an XRD default."""
    assert build_expose(_app(exposed=False)) == {}


def test_exposed_without_a_vip_block_raises() -> None:
    """The XRD requires vipBlock under expose, so this state is incoherent."""
    with pytest.raises(ValueError, match="vip_block"):
        build_expose(_app(vip_block=None))


def test_vip_block_comes_from_the_prefix() -> None:
    assert build_expose(_app())["vipBlock"] == VIP_BLOCK


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render(**kwargs: Any) -> dict[str, Any]:
    transform = CrossplaneFabricAppTransform.__new__(CrossplaneFabricAppTransform)
    spec: dict[str, Any] = {"namespace": "nfd41-demo", "tenant": "k8s-prod"}
    app = _app(**kwargs)
    # THE CHART, where the manifests used to be. Cycle 033 made a chart the
    # whole workload source, and these three tests are about the DUMPER rather
    # than about manifests -- they need a nested mapping, a sequence and a
    # dotted key, which the chart's values and the policy's allowFrom supply
    # exactly as the manifests did.
    spec["chart"] = {
        "name": "whoami",
        "repository": "https://cowboysysop.github.io/charts/",
        "version": "6.0.0",
        "values": {"service": {"type": "LoadBalancer", "ports": {"http": 80}}},
    }
    spec["expose"] = build_expose(app)
    spec["policy"] = build_policy(app)
    manifest = {
        "apiVersion": "nfd41.lab/v1alpha1",
        "kind": "FabricApp",
        "metadata": {"name": "nfd41-demo"},
        "spec": spec,
    }
    return {"text": transform._dump(manifest), "parsed": yaml.safe_load(transform._dump(manifest))}


def test_render_round_trips_with_types_intact() -> None:
    """The dumper decides quoting from the value's type; assert what it decided."""
    out = _render()
    spec = out["parsed"]["spec"]

    assert isinstance(spec["expose"]["serviceSelector"]["nfd41.lab/advertise"], str)
    assert isinstance(spec["policy"]["allowFromPorts"][0]["port"], str)
    assert "'true'" in out["text"]


def test_rendering_is_byte_identical_for_an_unchanged_model() -> None:
    """SC-004."""
    assert _render()["text"] == _render()["text"]


def test_sequences_are_indented_under_their_parent() -> None:
    """Matches the lab's hand-written manifests, so a diff between the two reads
    as a field comparison rather than a reindent.

    Asserted as a PROPERTY rather than a literal indent, because the depth is
    incidental: it moved from four spaces to six when the workload source became
    a chart, and a test pinned to the old number would have read as the dumper
    regressing. What matters is that a list item is never flush with its key,
    which is the reindent this exists to catch.
    """
    text = _render()["text"]
    lines = text.splitlines()
    sequences = 0

    for index, line in enumerate(lines):
        item = line.lstrip()
        if not item.startswith("- "):
            continue
        sequences += 1
        key = next(candidate for candidate in reversed(lines[:index]) if not candidate.lstrip().startswith("- "))
        item_indent = len(line) - len(item)
        key_indent = len(key) - len(key.lstrip())
        assert item_indent > key_indent, f"{line!r} is not indented under {key!r}"

    assert sequences, "nothing rendered a sequence, so this asserted nothing"

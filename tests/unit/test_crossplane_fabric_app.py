"""Unit tests for the Crossplane FabricApp manifest transform.

Fixtures rather than a live server: several validation paths are unreachable
against a live instance because the schema forbids the shapes, and the pure
functions below need no client.

The transform's IO -- downloading an attachment -- is deliberately not exercised
here. It is covered by the live render recorded in acceptance-evidence.md, where
the whole payload round-trips and is compared with the hand-written manifest.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from transforms.crossplane_fabric_app import (
    DEX_BACK_CHANNEL,
    DEX_ISSUER,
    CrossplaneFabricAppTransform,
    apply_local_traffic,
    apply_sso,
    build_chart,
    build_expose,
    build_monitoring,
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
    namespace: str | None = "otternet-demo",
    vrf: str | None = "K8S_PROD",
    intra: bool = True,
    sso: str | None = "none",
    status: str = "active",
    advertised: list[tuple[int, str]] | None = None,
    profiles: list[dict[str, Any]] | None = None,
) -> CrossplaneFabricAppQuery:
    if service_selector is None:
        service_selector = ["otternet.lab/advertise=true"]
    if workload_selector is None:
        workload_selector = ["app=frontend"]
    if allowed is None:
        allowed = ALLOW_FROM
    if ports is None:
        ports = [{"port": "8080", "protocol": "TCP"}]
    if advertised is None:
        advertised = [(80, "tcp")]
    return CrossplaneFabricAppQuery(
        MonitoringProfile={"edges": [{"node": p} for p in (profiles or [])]},
        target={
            "edges": [
                {
                    "node": {
                        "id": "app-1",
                        "name": {"value": "otternet-demo"},
                        "status": {"value": status},
                        "namespace_name": ({"value": namespace} if namespace else None),
                        "exposed": {"value": exposed},
                        "sso_provider": ({"value": sso} if sso else None),
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
                        "advertised_services": {
                            "edges": [
                                {
                                    "node": {
                                        "id": f"svc-{port}",
                                        "port": {"value": port},
                                        "ip_protocol": {"node": {"id": f"proto-{proto}", "name": {"value": proto}}},
                                    }
                                }
                                for port, proto in advertised
                            ]
                        },
                        "values_file": {"node": None},
                    }
                }
            ]
        },
    )


def _app(**kwargs: Any) -> Any:
    return _data(**kwargs).target.edges[0].node


# ---------------------------------------------------------------------------
# Selectors and type discipline
# ---------------------------------------------------------------------------


def test_selector_becomes_a_label_map() -> None:
    """Stored as key=value strings because Infrahub 1.10.6 returns a 500 for a
    JSON key containing a dot or a slash, and every label selector has both."""
    assert parse_selector(["otternet.lab/advertise=true"], field="s") == {"otternet.lab/advertise": "true"}


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

    assert expose["serviceSelector"]["otternet.lab/advertise"] == "true"
    assert isinstance(expose["serviceSelector"]["otternet.lab/advertise"], str)


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
    spec: dict[str, Any] = {"namespace": "otternet-demo", "tenant": "k8s-prod"}
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
        "apiVersion": "otternet.lab/v1alpha1",
        "kind": "FabricApp",
        "metadata": {"name": "otternet-demo"},
        "spec": spec,
    }
    return {"text": transform._dump(manifest), "parsed": yaml.safe_load(transform._dump(manifest))}


def test_render_round_trips_with_types_intact() -> None:
    """The dumper decides quoting from the value's type; assert what it decided."""
    out = _render()
    spec = out["parsed"]["spec"]

    assert isinstance(spec["expose"]["serviceSelector"]["otternet.lab/advertise"], str)
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


# ---------------------------------------------------------------------------
# Sign-in through Dex (cycle 034)
# ---------------------------------------------------------------------------

GRAFANA_VIP = "10.112.240.81"


def _kps_values() -> dict[str, Any]:
    return {
        "crds": {"enabled": True},
        "grafana": {
            "service": {"type": "LoadBalancer", "port": 80, "annotations": {"lbipam.cilium.io/ips": GRAFANA_VIP}},
            "grafana.ini": {"server": {"domain": "kept"}},
        },
    }


def test_none_leaves_values_exactly_as_they_were() -> None:
    """Every application that predates the field renders byte-identically."""
    values = _kps_values()
    assert apply_sso("none", chart="kube-prometheus-stack", values=values, name="a") == _kps_values()
    assert apply_sso(None, chart="whoami", values=None, name="a") is None


def test_dex_merges_the_sign_in_block_under_grafana() -> None:
    values = apply_sso("dex", chart="kube-prometheus-stack", values=_kps_values(), name="otternet-metrics")
    grafana = values["grafana"]
    ini = grafana["grafana.ini"]
    oauth = ini["auth.generic_oauth"]

    # Browser-facing on the issuer; server-to-server over the management network.
    assert oauth["auth_url"] == f"{DEX_ISSUER}/auth"
    assert oauth["token_url"] == f"{DEX_BACK_CHANNEL}/token"
    assert oauth["api_url"] == f"{DEX_BACK_CHANNEL}/userinfo"
    assert oauth["client_id"] == "grafana"
    # Everybody Viewer, nobody Admin through sign-in, and no password form.
    # The role is the org default, not a JMESPath literal: Grafana's ini parser
    # strips the quotes off `'Viewer'` and strict mode then refused every login.
    assert ini["users"]["auto_assign_org_role"] == "Viewer"
    assert "role_attribute_path" not in oauth
    assert oauth["role_attribute_strict"] is False
    assert oauth["allow_assign_grafana_admin"] is False
    assert ini["auth"]["disable_login_form"] is True
    # root_url is derived from the pinned address, because the redirect URI
    # registered with Dex is <root_url>login/generic_oauth.
    assert ini["server"]["root_url"] == f"http://{GRAFANA_VIP}/"
    # Tuning in the values file survives the merge.
    assert ini["server"]["domain"] == "kept"
    assert grafana["service"]["port"] == 80


def test_dex_takes_its_secrets_from_kubernetes_never_from_values() -> None:
    values = apply_sso("dex", chart="kube-prometheus-stack", values=_kps_values(), name="otternet-metrics")
    grafana = values["grafana"]
    ref = grafana["envValueFrom"]["GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET"]["secretKeyRef"]
    assert ref == {"name": "grafana-oidc", "key": "client-secret"}
    assert grafana["admin"]["existingSecret"] == "grafana-admin"
    assert "client_secret" not in grafana["grafana.ini"]["auth.generic_oauth"]
    assert "adminPassword" not in grafana


def test_dex_on_a_chart_with_no_renderer_raises() -> None:
    """A sign-in block written to a key the chart ignores deploys, answers, and
    lets nobody in -- with nothing logged. Refusing is the only safe answer."""
    with pytest.raises(ValueError, match="whoami"):
        apply_sso("dex", chart="whoami", values={}, name="otternet-demo")


def test_dex_without_a_pinned_address_raises() -> None:
    """The redirect URI names an address. An allocated one is unknown when Dex
    is configured and can differ between rebuilds."""
    values = _kps_values()
    del values["grafana"]["service"]["annotations"]
    with pytest.raises(ValueError, match=r"lbipam\.cilium\.io/ips"):
        apply_sso("dex", chart="kube-prometheus-stack", values=values, name="otternet-metrics")


def test_dex_render_is_deterministic() -> None:
    first = apply_sso("dex", chart="kube-prometheus-stack", values=_kps_values(), name="m")
    second = apply_sso("dex", chart="kube-prometheus-stack", values=_kps_values(), name="m")
    assert first == second


# ---------------------------------------------------------------------------
# externalTrafficPolicy: Local on every exposed application
# ---------------------------------------------------------------------------


def _whoami_values(**service: Any) -> dict[str, Any]:
    return {"replicaCount": 1, "service": {"type": "LoadBalancer", "ports": {"http": 80}, **service}}


def test_an_exposed_known_chart_gets_local_even_when_its_values_omit_it() -> None:
    """The portal's own prefill used to omit it, and the chart defaults to Cluster."""
    values = apply_local_traffic(exposed=True, chart="whoami", values=_whoami_values(), name="a")
    assert values["service"]["externalTrafficPolicy"] == "Local"
    assert values["service"]["ports"] == {"http": 80}, "the rest of the Service values survive"


def test_local_overrides_an_explicit_cluster_on_a_known_chart() -> None:
    """Intent wins over tuning: `Cluster` is the setting that defeats the pod gate."""
    values = apply_local_traffic(
        exposed=True, chart="whoami", values=_whoami_values(externalTrafficPolicy="Cluster"), name="a"
    )
    assert values["service"]["externalTrafficPolicy"] == "Local"


def test_grafana_inside_kube_prometheus_stack_is_the_service_enforced() -> None:
    values = apply_local_traffic(exposed=True, chart="kube-prometheus-stack", values=_kps_values(), name="m")
    assert values["grafana"]["service"]["externalTrafficPolicy"] == "Local"
    assert "service" not in values


def test_an_unexposed_application_is_left_exactly_as_it_was() -> None:
    """No VIP, nothing reaches it from outside -- and telegraf has no Service path."""
    values = {"service": {"enabled": False}}
    assert apply_local_traffic(exposed=False, chart="telegraf", values=values, name="t") is values


def test_enforcing_is_a_no_op_when_the_values_already_say_local() -> None:
    """What keeps an application that already states it byte-identical."""
    values = _whoami_values(externalTrafficPolicy="Local")
    assert apply_local_traffic(exposed=True, chart="whoami", values=values, name="a") == _whoami_values(
        externalTrafficPolicy="Local"
    )


def test_an_unknown_chart_passes_only_when_its_values_say_local() -> None:
    values = {"controller": {"service": {"type": "LoadBalancer", "externalTrafficPolicy": "Local"}}}
    assert apply_local_traffic(exposed=True, chart="ingress-nginx", values=values, name="a") is values


@pytest.mark.parametrize(
    "values",
    [
        None,
        {"service": {"type": "LoadBalancer"}},
        {"service": {"type": "LoadBalancer", "externalTrafficPolicy": "Cluster"}},
        {"a": {"externalTrafficPolicy": "Local"}, "b": {"externalTrafficPolicy": "Cluster"}},
    ],
)
def test_an_unknown_chart_without_local_raises_rather_than_guessing(values: Any) -> None:
    """A guessed key would be ignored by the chart, and the SNAT would come back."""
    with pytest.raises(ValueError, match="externalTrafficPolicy: Local"):
        apply_local_traffic(exposed=True, chart="nginx", values=values, name="shop")


def test_the_portal_prefill_states_local() -> None:
    """What a requester who changes nothing gets must already be the right shape.

    The curated template used to PREFILL the values; since specs/035 the requester
    picks a catalogue entry and the entry's `default_values` are what the application
    runs. Same claim, moved with the values: they must already say `Local`, so the
    shape is right for another chart that follows the same `service.*` convention.
    """
    template = yaml.safe_load(Path("backstage/catalog/exposed-app-with-access.yaml").read_text(encoding="utf-8"))
    fields = {
        name: spec for page in template["spec"]["parameters"] for name, spec in page.get("properties", {}).items()
    }
    assert "values_file_content" not in fields, "the requester no longer supplies values"
    catalogue = next(yaml.safe_load_all(Path("objects/35a_otternet_app_catalogue.yml").read_text(encoding="utf-8")))
    whoami = next(entry for entry in catalogue["spec"]["data"] if entry["requestable"])
    prefill = yaml.safe_load(whoami["default_values"])
    assert prefill["service"]["externalTrafficPolicy"] == "Local"


# ---------------------------------------------------------------------------
# spec.monitoring: the collector's admission (cycle 036)
# ---------------------------------------------------------------------------


def _profile(
    *,
    name: str = "services-apps",
    kind: str | None = "ServiceFabricApp",
    measurements: tuple[str, ...] = ("service-delivery", "service-reachability"),
    enabled: bool = True,
    namespace: str | None = "otternet-telemetry",
) -> dict[str, Any]:
    return {
        "id": f"profile-{name}",
        "name": {"value": name},
        "enabled": {"value": enabled},
        "service_kind": {"value": kind},
        "measurements": {"edges": [{"node": {"id": f"m-{m}", "name": {"value": m}}} for m in measurements]},
        "collector": {"node": {"id": f"c-{namespace}", "namespace_name": {"value": namespace}}},
    }


def _admission(parsed: CrossplaneFabricAppQuery) -> dict[str, Any]:
    profiles = [edge.node for edge in parsed.monitoring_profile.edges if edge.node is not None]
    return build_monitoring(parsed.target.edges[0].node, profiles)


def _monitoring(**kwargs: Any) -> dict[str, Any]:
    return _admission(_data(**kwargs))


def _with(node_fields: dict[str, Any], **kwargs: Any) -> CrossplaneFabricAppQuery:
    """`_data`, with node fields the helper does not parameterise overridden."""
    parsed = _data(**kwargs).model_dump(by_alias=True)
    parsed["target"]["edges"][0]["node"].update(node_fields)
    return CrossplaneFabricAppQuery(**parsed)


def _manifest(**kwargs: Any) -> str:
    """The whole transform's output, with a chart so it renders."""
    parsed = _with(
        {
            "chart_repository": {"value": "https://cowboysysop.github.io/charts/"},
            "chart_name": {"value": "whoami"},
            "chart_version": {"value": "6.0.0"},
        },
        **kwargs,
    ).model_dump(by_alias=True)
    transform = CrossplaneFabricAppTransform.__new__(CrossplaneFabricAppTransform)
    return asyncio.run(transform.transform(parsed))


def test_a_probing_profile_admits_its_collector_on_the_pod_ports() -> None:
    """The pod port (8080), not the advertised one (80): Cilium enforces after
    service translation, so a rule naming the VIP's port would admit nothing."""
    assert _monitoring(profiles=[_profile()]) == {
        "collectorNamespaces": ["otternet-telemetry"],
        "ports": [{"port": "8080", "protocol": "TCP"}],
    }


def test_service_generic_watches_applications_too() -> None:
    assert _monitoring(profiles=[_profile(kind="ServiceGeneric")])["collectorNamespaces"] == ["otternet-telemetry"]


def test_every_probing_collector_is_admitted_once_and_in_order() -> None:
    profiles = [_profile(name="b", namespace="zz-collector"), _profile(name="a"), _profile(name="c")]
    assert _monitoring(profiles=profiles)["collectorNamespaces"] == ["otternet-telemetry", "zz-collector"]


@pytest.mark.parametrize(
    "profile",
    [
        _profile(measurements=("service-delivery",)),
        _profile(enabled=False),
        _profile(kind="ServiceAppAccess"),
        _profile(kind=None, measurements=("interface-counters",)),
        _profile(namespace=None),
    ],
    ids=["no-reachability", "disabled", "other-kind", "device-profile", "no-namespace"],
)
def test_a_profile_that_does_not_probe_applications_admits_nothing(profile: dict[str, Any]) -> None:
    """Turning reachability off in Infrahub is what closes the collector's path."""
    assert _monitoring(profiles=[profile]) == {}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "decommissioning"},
        {"status": "decommissioned"},
        {"exposed": False},
        {"advertised": []},
        {"advertised": [(53, "udp")]},
        {"ports": [{"port": "53", "protocol": "UDP"}]},
    ],
    ids=["decommissioning", "decommissioned", "unexposed", "advertises-nothing", "advertises-udp", "udp-pod-port"],
)
def test_an_application_nothing_probes_is_admitted_nowhere(kwargs: dict[str, Any]) -> None:
    assert _monitoring(profiles=[_profile()], **kwargs) == {}


def test_no_pod_port_means_no_admission_rather_than_every_port() -> None:
    """External sources are confined to policy_allow_ports; with none declared
    the collector would be admitted on every port, wider than any grant, so it
    is not admitted at all."""
    assert _admission(_with({"policy_allow_ports": {"value": None}}, profiles=[_profile()])) == {}


def test_an_open_gate_needs_no_admission() -> None:
    """Nothing selects the pods, so the collector is admitted already -- and an
    admission policy would make their ingress deny-by-default for everyone else."""
    assert _admission(_with({"policy_default_deny": {"value": False}}, profiles=[_profile()], allowed=[])) == {}


def test_a_source_prefix_alone_closes_the_gate_and_so_needs_admission() -> None:
    """Grafana's shape: default deny off, but allow-ingress selects the pods."""
    parsed = _with({"policy_default_deny": {"value": False}}, profiles=[_profile()], allowed=["10.111.0.0/16"])
    assert _admission(parsed)["collectorNamespaces"] == ["otternet-telemetry"]


def test_monitoring_follows_policy_in_the_manifest() -> None:
    spec = yaml.safe_load(_manifest(profiles=[_profile()]))["spec"]
    assert list(spec)[-2:] == ["policy", "monitoring"]
    assert spec["monitoring"]["ports"][0]["port"] == "8080", "a port is a string, as the XRD types it"


@pytest.mark.parametrize(
    "profiles",
    [[], [_profile(measurements=("service-delivery",))], [_profile(enabled=False)]],
    ids=["no-profile", "delivery-only", "disabled"],
)
def test_an_application_monitoring_does_not_probe_renders_byte_identically(profiles: list[dict[str, Any]]) -> None:
    """No `monitoring` key at all, so the manifest is the one rendered before
    the field existed and Vidra delivers no change."""
    text = _manifest(profiles=profiles)
    assert "monitoring" not in text
    assert text == _manifest(profiles=[])


# ---------------------------------------------------------------------------
# specs/035-application-catalogue: a chart is all three fields, and the
# artifact reads the application's own pin, never the catalogue entry.
# ---------------------------------------------------------------------------


def _chart_app(**fields: str | None) -> Any:
    app = _app()
    update = {key: (SimpleNamespace(value=value) if value is not None else None) for key, value in fields.items()}
    return app.model_copy(update=update)


def test_a_complete_chart_builds_as_it_always_did() -> None:
    app = _chart_app(
        chart_repository="https://cowboysysop.github.io/charts/", chart_name="whoami", chart_version="6.0.0"
    )

    assert build_chart(app, {"replicaCount": 3}) == {
        "name": "whoami",
        "repository": "https://cowboysysop.github.io/charts/",
        "version": "6.0.0",
        "values": {"replicaCount": 3},
    }


@pytest.mark.parametrize(
    ("fields", "missing"),
    [
        ({"chart_repository": "https://x/", "chart_name": "whoami", "chart_version": None}, "version"),
        ({"chart_repository": None, "chart_name": "whoami", "chart_version": "6.0.0"}, "repository"),
        ({"chart_repository": None, "chart_name": "whoami", "chart_version": None}, "repository or version"),
    ],
)
def test_a_half_pinned_chart_is_refused_where_it_names_itself(fields: dict[str, str | None], missing: str) -> None:
    """The XRD requires all three; the cluster would reject it, quietly, after delivery."""
    with pytest.raises(ValueError, match=f"no {missing}"):
        build_chart(_chart_app(**fields), None)


def test_no_chart_name_still_means_no_chart() -> None:
    assert build_chart(_chart_app(chart_name=None), None) == {}


def test_the_artifact_reads_the_applications_pin_and_never_the_catalogue_entry() -> None:
    """FR-016. A catalogue edit must not reach a running application's artifact, and
    the only way to guarantee it is for the query never to select the entry."""
    query = Path("transforms/crossplane_fabric_app.gql").read_text(encoding="utf-8")
    assert "definition" not in query
    assert (
        "definition"
        not in CrossplaneFabricAppQuery.model_json_schema()["$defs"]["CrossplaneFabricAppQueryTargetEdgesNode"][
            "properties"
        ]
    )

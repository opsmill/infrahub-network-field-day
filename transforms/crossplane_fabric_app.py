"""Crossplane FabricApp manifest transform.

Renders the ``FabricApp`` resource the lab's Crossplane composition consumes
from a ``ServiceFabricApp``. The counterpart to
``crossplane_fabric_peering``: that one renders the cluster's BGP session, this
one renders an application deployed on top of it.

**Async, unlike the peering transform.** The payload -- the Kubernetes manifests
and any Helm values -- is stored as a ``CoreFileObject`` attachment rather than
a JSON attribute, so its content is fetched with ``download_file()`` rather than
arriving in the query response. ``avd_anta_catalog`` is the async precedent.

The payload is an attachment because a JSON attribute cannot be seeded: Infrahub
1.10.6's object-load path returns HTTP 500 for a JSON key containing a dot or a
slash, and every Kubernetes payload is full of them --
``app.kubernetes.io/name``, ``kubernetes.io/hostname``, ``otternet.lab/advertise``.
Cycle 013 added the attachments for exactly this.

Precedence, per cycle 013: **the attachment wins** over the inline attribute,
which remains an escape hatch for payloads small enough not to need a file.

Everything the XRD types as a string stays a string. ``true`` is a label value,
``8080`` is a port, and both would be rejected by the Kubernetes API if they
arrived as a boolean or an integer -- so the dumper decides quoting from the
value's type, and a colon-bearing scalar is force-quoted.
"""

from __future__ import annotations

import copy
from typing import Any

import yaml
from infrahub_sdk.transforms import InfrahubTransform

from .crossplane_fabric_app_query import (
    CrossplaneFabricAppQuery,
    CrossplaneFabricAppQueryTargetEdgesNode,
)
from .telemetry_services import collector_admission

AppNode = CrossplaneFabricAppQueryTargetEdgesNode

API_VERSION = "otternet.lab/v1alpha1"
KIND = "FabricApp"

# Wide enough that PyYAML never folds a scalar, so a one-field change stays a
# one-line diff.
_MAX_WIDTH = 4096


class _ManifestDumper(yaml.SafeDumper):
    """Indents sequences under the key that owns them, matching the lab's own
    hand-written manifests so a diff between the two reads as a field
    comparison rather than a reindent."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        del indentless  # PyYAML passes it by keyword; overriding it is the point.
        super().increase_indent(flow, False)


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    """Quote any string containing a colon; leave the rest to the resolver.

    A colon inside a plain scalar is the one construct YAML parsers have
    historically disagreed about, and this manifest is read by a Go parser.
    Everything else -- ``true`` becoming ``'true'``, digits staying unquoted --
    is the resolver's call, which is the reason for dumping rather than laying
    out lines by hand.
    """
    style = "'" if ":" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_ManifestDumper.add_representer(str, _represent_str)


def _value(field: Any) -> Any:
    return field.value if field is not None else None


def _node_of(relationship: Any) -> Any:
    return relationship.node if relationship is not None else None


def _edges_of(relationship: Any) -> list[Any]:
    if relationship is None:
        return []
    return [edge.node for edge in relationship.edges if edge.node is not None]


def parse_selector(entries: list[str] | None, *, field: str) -> dict[str, str]:
    """Turn ``["k=v", ...]`` into a label map.

    Splits on the FIRST ``=`` only -- a label value may legitimately contain
    one. Keys are inserted sorted so the rendered map is deterministic.

    Raises:
        ValueError: if an entry has no ``=``. Dropping it silently would leave
            a selector matching more than intended, which for a workload
            selector means a policy applying to workloads nobody chose.
    """
    if not entries:
        return {}

    pairs: list[tuple[str, str]] = []
    for entry in entries:
        if "=" not in entry:
            msg = f"{field} entry {entry!r} has no '=' and cannot become a label"
            raise ValueError(msg)
        key, value = entry.split("=", 1)
        pairs.append((key, value))
    return dict(sorted(pairs))


def build_expose(app: AppNode) -> dict[str, Any]:
    """``spec.expose``, or an empty dict when the app is not exposed.

    Raises:
        ValueError: if the app is exposed with no VIP block. The XRD requires
            ``vipBlock`` under ``expose``, so that state is incoherent.
    """
    if not _value(app.exposed):
        return {}

    name = _value(app.name)
    block = _node_of(app.vip_block)
    if block is None:
        msg = f"application {name!r} is exposed but has no vip_block; the XRD requires expose.vipBlock"
        raise ValueError(msg)

    expose: dict[str, Any] = {"vipBlock": _value(block.prefix)}
    selector = parse_selector(_value(app.service_selector), field="service_selector")
    if selector:
        expose["serviceSelector"] = selector
    communities = _value(app.communities)
    if communities:
        expose["communities"] = list(communities)
    return expose


def build_policy(app: AppNode) -> dict[str, Any]:
    """``spec.policy``.

    ``allowFrom`` is the field where an error is most costly: it names the
    networks permitted to reach the application, and is the third of three
    independent gates alongside the route and the firewall.
    """
    policy: dict[str, Any] = {
        "defaultDeny": _value(app.policy_default_deny),
        "allowDNS": _value(app.policy_allow_dns),
        "allowIntraNamespace": _value(app.policy_allow_intra_namespace),
        "allowEgressToAPIServer": _value(app.policy_allow_egress_api_server),
        "allowEgressToInternet": _value(app.policy_allow_egress_internet),
    }

    allow_from = sorted(
        _value(prefix.prefix) for prefix in _edges_of(app.allowed_source_prefixes) if _value(prefix.prefix)
    )
    if allow_from:
        policy["allowFrom"] = allow_from

    ports = _value(app.policy_allow_ports)
    if ports:
        policy["allowFromPorts"] = [
            {"port": str(entry.get("port")), "protocol": entry.get("protocol", "TCP")} for entry in ports
        ]

    workload = parse_selector(_value(app.workload_selector), field="workload_selector")
    if workload:
        policy["workloadSelector"] = workload

    return policy


def build_monitoring(app: AppNode, profiles: list[Any]) -> dict[str, Any]:
    """``spec.monitoring``: the collectors this application's pod gate admits.

    THE FOURTH GATE OPENING, and the only one opened by monitoring rather than
    by a grant. ``allowFrom`` is CIDR-only and Cilium never matches a pod
    against a CIDR rule, so an in-cluster collector cannot reach a gated
    application through it at all. The composition admits the namespaces named
    here, on the ports named here, to the endpoints ``allow-ingress`` protects
    -- and nothing else.

    Derived by ``collector_admission``, the function the Telemetry Collector
    Configuration uses to decide which applications it probes, from every
    service profile and its collector's namespace. So enabling
    ``service-reachability`` for applications is what opens the path, and
    disabling it closes it in the same proposed change that removes the probe.

    An empty dict -- and so a manifest byte-identical to one rendered before
    this field existed -- for every application no profile probes, and for one
    whose gate is open, which admits the collector already.
    """
    watchers = [(profile, _value(getattr(_node_of(profile.collector), "namespace_name", None))) for profile in profiles]
    admission = collector_admission(app, watchers)
    if not admission.namespaces:
        return {}
    return {
        "collectorNamespaces": list(admission.namespaces),
        "ports": [{"port": port, "protocol": protocol} for port, protocol in admission.ports],
    }


# ---------------------------------------------------------------------------
# Sign-in through the lab's identity provider (cycle 034)
# ---------------------------------------------------------------------------

# THE ONE ISSUER. Browser-facing URLs use it, because a branch user's browser is
# what follows them. AGENTS.md records why there is exactly one and why moving it
# is a test-every-browser change.
DEX_ISSUER = "http://10.90.0.11:32556/dex"

# Server-to-server URLs use the tool node's management address instead. A pod
# reaching 10.90.0.11 would cross the fabric to fw1, which has no k8s-prod ->
# tooling rule; 172.20.41.101 is reached out of the node's management interface,
# masqueraded, which is the path Vidra already uses to reach Infrahub. Grafana's
# generic OAuth reads claims from the userinfo response and does not insist that
# the token's issuer matches the host it was fetched from.
DEX_BACK_CHANNEL = "http://172.20.41.101:32556/dex"

DEX_CLIENT_ID = "grafana"

# The Secrets `invoke cluster` creates once the namespace exists. Names only;
# the values never reach the graph or this artifact.
OIDC_SECRET = "grafana-oidc"  # noqa: S105 -- a Secret NAME, not its value
ADMIN_SECRET = "grafana-admin"  # noqa: S105 -- a Secret NAME, not its value

# Where a chart keeps Grafana's values, by chart name. A chart missing from this
# map has no renderer, and `dex` on it raises rather than writing a block the
# chart would ignore.
_GRAFANA_VALUES_PATH: dict[str, tuple[str, ...]] = {
    "kube-prometheus-stack": ("grafana",),
    "grafana": (),
}

_PINNED_ADDRESS = "lbipam.cilium.io/ips"


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """``overlay`` over ``base``, recursing into mappings. Intent wins over tuning."""
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _grafana_sign_in(address: str) -> dict[str, Any]:
    """Grafana's half of the contract: everybody Viewer, nobody Admin, no form."""
    return {
        "envValueFrom": {
            "GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET": {"secretKeyRef": {"name": OIDC_SECRET, "key": "client-secret"}},
        },
        "admin": {"existingSecret": ADMIN_SECRET, "userKey": "admin-user", "passwordKey": "admin-password"},
        "grafana.ini": {
            # The redirect URI Dex has registered is <root_url>login/generic_oauth.
            "server": {"root_url": f"http://{address}/"},
            "auth": {"disable_login_form": True},
            # Everyone who signs in lands in the main org as a Viewer. Dex's
            # static users carry no role or groups claim, so there is nothing
            # for Grafana to map -- the role comes from this default instead.
            "users": {"auto_assign_org_role": "Viewer"},
            "auth.generic_oauth": {
                "enabled": True,
                "name": "Dex",
                "client_id": DEX_CLIENT_ID,
                "scopes": "openid email profile",
                "auth_url": f"{DEX_ISSUER}/auth",
                "token_url": f"{DEX_BACK_CHANNEL}/token",
                "api_url": f"{DEX_BACK_CHANNEL}/userinfo",
                "login_attribute_path": "email",
                "email_attribute_path": "email",
                # NO role_attribute_path, and NOT strict. A JMESPath literal
                # (`'Viewer'`) was the first attempt and it locked everyone out:
                # Grafana's ini parser strips the quotes, the expression becomes
                # a lookup of a field called `Viewer`, finds nothing, and strict
                # mode refuses the login -- measured, with "idP did not return a
                # role attribute". With no path the role is
                # `auto_assign_org_role` above, and the sign-in path still can
                # never make anyone a server admin.
                "role_attribute_strict": False,
                "allow_assign_grafana_admin": False,
                "skip_org_role_sync": False,
                "allow_sign_up": True,
                "auto_login": True,
                "use_pkce": True,
            },
        },
    }


def apply_sso(provider: str | None, *, chart: str | None, values: Any, name: str) -> Any:
    """Merge the identity provider's sign-in block into ``values`` when declared.

    ``none`` (or unset) returns ``values`` untouched, which is what keeps every
    application that predates the field byte-identical.

    Raises:
        ValueError: for ``dex`` on a chart with no renderer, or on values that
            pin no LoadBalancer address. Both would deploy an application that
            answers and lets nobody in, with nothing logged anywhere.
    """
    if provider in (None, "none"):
        return values
    if provider != "dex":
        msg = f"application {name!r}: sso_provider {provider!r} has no renderer"
        raise ValueError(msg)

    path = _GRAFANA_VALUES_PATH.get(str(chart))
    if path is None:
        msg = (
            f"application {name!r}: sso_provider 'dex' is declared on chart {chart!r}, which has no sign-in "
            f"renderer (known: {sorted(_GRAFANA_VALUES_PATH)})"
        )
        raise ValueError(msg)

    base: dict[str, Any] = values if isinstance(values, dict) else {}
    grafana: Any = base
    for key in path:
        grafana = grafana.get(key, {}) if isinstance(grafana, dict) else {}
    address = (((grafana or {}).get("service") or {}).get("annotations") or {}).get(_PINNED_ADDRESS)
    if not address:
        msg = (
            f"application {name!r}: sso_provider 'dex' needs Grafana's Service to pin its address with "
            f"{_PINNED_ADDRESS}, because the redirect URI registered with Dex names it"
        )
        raise ValueError(msg)

    overlay: dict[str, Any] = _grafana_sign_in(str(address))
    for key in reversed(path):
        overlay = {key: overlay}
    return _deep_merge(base, overlay)


# ---------------------------------------------------------------------------
# externalTrafficPolicy: Local on every exposed application
# ---------------------------------------------------------------------------

# Where a chart keeps the values of the LoadBalancer Service that gets the VIP,
# by chart name. Like `_GRAFANA_VALUES_PATH`, a chart missing from this map is
# not guessed at: its values must say `Local` themselves, or rendering refuses.
_LB_SERVICE_VALUES_PATH: dict[str, tuple[str, ...]] = {
    "whoami": ("service",),
    "kube-prometheus-stack": ("grafana", "service"),
    "grafana": ("service",),
    "podinfo": ("service",),
    "argo-cd": ("server", "service"),
    "coredns": ("service",),
}

_TRAFFIC_POLICY = "externalTrafficPolicy"
_LOCAL = "Local"


def _traffic_policies(values: Any) -> list[Any]:
    """Every ``externalTrafficPolicy`` value anywhere in ``values``."""
    if isinstance(values, dict):
        found = [value for key, value in values.items() if key == _TRAFFIC_POLICY]
        for value in values.values():
            found.extend(_traffic_policies(value))
        return found
    if isinstance(values, list):
        return [found for item in values for found in _traffic_policies(item)]
    return []


def apply_local_traffic(*, exposed: bool, chart: str | None, values: Any, name: str) -> Any:
    """Force ``externalTrafficPolicy: Local`` on an exposed application's Service.

    THE THIRD GATE DEPENDS ON IT. Charts default to ``Cluster``, and with that a
    request landing on a node whose chosen backend is elsewhere is SNATed to the
    node's address before delivery -- measured on ``otternet-demo``: 4 of 6
    requests from host-a reached the pod as 10.110.0.x. The composed
    CiliumNetworkPolicy admits those as ``remote-node``, so
    ``allowed_source_prefixes`` decides nothing for most requests, and a source
    no grant names gets in. With ``Local`` the client address survives, and
    Cilium advertises the VIP only from nodes running a backend.

    Enforced here rather than left to each payload, because a portal request
    supplies its own values and the default it would inherit is the wrong one.
    An unexposed application is returned untouched: it has no VIP, so nothing
    reaches it from outside the cluster.

    Raises:
        ValueError: for an exposed application on a chart with no known Service
            path whose values do not set ``Local`` -- or set anything else.
            Guessing the key would write a value the chart ignores, and the
            application would deploy with the very SNAT this exists to stop.
    """
    if not exposed:
        return values

    path = _LB_SERVICE_VALUES_PATH.get(str(chart))
    if path is None:
        declared = _traffic_policies(values)
        if declared and all(value == _LOCAL for value in declared):
            return values
        msg = (
            f"application {name!r} is exposed on chart {chart!r}, whose values do not set "
            f"{_TRAFFIC_POLICY}: {_LOCAL} on its LoadBalancer Service (found {declared or 'nothing'}); "
            f"with the default the pod sees a node address and the source-prefix policy cannot apply "
            f"(known charts: {sorted(_LB_SERVICE_VALUES_PATH)})"
        )
        raise ValueError(msg)

    overlay: dict[str, Any] = {_TRAFFIC_POLICY: _LOCAL}
    for key in reversed(path):
        overlay = {key: overlay}
    base: dict[str, Any] = values if isinstance(values, dict) else {}
    return _deep_merge(base, overlay)


def build_chart(app: AppNode, values: Any) -> dict[str, Any]:
    """``spec.chart``, or an empty dict when no chart is set."""
    name = _value(app.chart_name)
    if not name:
        return {}

    repository = _value(app.chart_repository)
    version = _value(app.chart_version)
    # THE XRD REQUIRES ALL THREE TOGETHER (`chart` carries `required: [repository,
    # name, version]`). The schema says so too, but an application can now be
    # created by a path that sets them in two steps -- a catalogue request is
    # pinned by its generator -- so a half-pinned one is refused here, where it
    # names itself, rather than delivered to a cluster that rejects it.
    missing = [field for field, value in (("repository", repository), ("version", version)) if not value]
    if missing:
        msg = (
            f"application {_value(app.name)!r} names chart {name!r} but no {' or '.join(missing)}; "
            "the XRD requires chart.repository, chart.name and chart.version together"
        )
        raise ValueError(msg)

    chart: dict[str, Any] = {"name": name, "repository": repository, "version": version}
    if values:
        chart["values"] = values
    return chart


class CrossplaneFabricAppTransform(InfrahubTransform):
    """Render one FabricApp resource for an application service."""

    query = "crossplane_fabric_app"

    async def transform(self, data: dict[str, Any]) -> str:
        """Render the manifest, or raise naming what the model is missing."""
        parsed = CrossplaneFabricAppQuery(**data)

        app = parsed.target.edges[0].node if parsed.target.edges else None
        if app is None:
            msg = "no ServiceFabricApp matched the requested name"
            raise ValueError(msg)

        name = _value(app.name)
        namespace = _value(app.namespace_name)
        if not namespace:
            msg = f"application {name!r} has no namespace_name; the XRD requires spec.namespace"
            raise ValueError(msg)

        values = await self._payload(
            app.values_file, _value(app.chart_values), kind="ServiceFabricAppValuesFile", name=name
        )
        values = apply_sso(_value(app.sso_provider), chart=_value(app.chart_name), values=values, name=name)
        values = apply_local_traffic(
            exposed=bool(_value(app.exposed)), chart=_value(app.chart_name), values=values, name=name
        )
        chart = build_chart(app, values)

        # A CHART IS THE WHOLE WORKLOAD SOURCE since cycle 033. It used to be a
        # chart, raw manifests, or both, which left this deciding which of three
        # shapes it was looking at from whichever fields happened to be
        # populated -- and refusing only when everything was empty. The three
        # chart fields are mandatory together in the schema now, so reaching
        # here without one means the object predates that and was never
        # migrated.
        if not chart:
            msg = (
                f"application {name!r} names no chart; rendering it would produce a namespace and a "
                "network policy with no workload, which applies cleanly and deploys nothing"
            )
            raise ValueError(msg)

        # Key order is the contract with the XRD, not something to alphabetise.
        spec: dict[str, Any] = {"namespace": namespace}
        vrf = _node_of(app.vrf)
        if vrf is not None and _value(vrf.name):
            # K8S_PROD -> k8s-prod. Infrahub VRFs are upper snake case by
            # convention here; Kubernetes tenants are lower kebab. Lower-casing
            # alone leaves k8s_prod, which is not the XRD's default and not what
            # the hand-written manifest says.
            spec["tenant"] = str(_value(vrf.name)).lower().replace("_", "-")
        spec["chart"] = chart
        expose = build_expose(app)
        if expose:
            spec["expose"] = expose
        spec["policy"] = build_policy(app)
        profiles = [edge.node for edge in parsed.monitoring_profile.edges if edge.node is not None]
        monitoring = build_monitoring(app, profiles)
        if monitoring:
            spec["monitoring"] = monitoring

        manifest = {
            "apiVersion": API_VERSION,
            "kind": KIND,
            "metadata": {"name": name},
            "spec": spec,
        }
        return self._dump(manifest)

    async def _payload(self, attachment: Any, inline: Any, *, kind: str, name: str) -> Any:
        """The attachment's content if there is one, else the inline attribute.

        The attachment wins, per cycle 013's documented precedence: it is the
        only one of the two that can hold a payload whose keys contain dots and
        slashes.

        The query returns the file's *metadata* only -- its content lives in
        object storage. `download_file()` is a method on an SDK node, not on the
        generated query model, so the node is re-fetched by id before the
        content can be read.

        Raises:
            ValueError: if an attachment's content is not parseable YAML.
        """
        stub = _node_of(attachment)
        if stub is None:
            return inline

        file_node = await self.client.get(kind=kind, id=stub.id)
        content = await file_node.download_file()
        text = content.decode() if isinstance(content, bytes) else content
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            file_name = _value(stub.file_name)
            msg = f"application {name!r}: attachment {file_name!r} is not parseable YAML: {exc}"
            raise ValueError(msg) from exc

    @staticmethod
    def _dump(manifest: dict[str, Any]) -> str:
        """Emit the manifest. ``sort_keys=False`` because the key order above is
        the contract with the XRD."""
        return yaml.dump(
            manifest,
            Dumper=_ManifestDumper,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=_MAX_WIDTH,
        )

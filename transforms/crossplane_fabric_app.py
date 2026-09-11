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
``app.kubernetes.io/name``, ``kubernetes.io/hostname``, ``nfd41.lab/advertise``.
Cycle 013 added the attachments for exactly this.

Precedence, per cycle 013: **the attachment wins** over the inline attribute,
which remains an escape hatch for payloads small enough not to need a file.

Everything the XRD types as a string stays a string. ``true`` is a label value,
``8080`` is a port, and both would be rejected by the Kubernetes API if they
arrived as a boolean or an integer -- so the dumper decides quoting from the
value's type, and a colon-bearing scalar is force-quoted.
"""

from __future__ import annotations

from typing import Any

import yaml
from infrahub_sdk.transforms import InfrahubTransform

from .crossplane_fabric_app_query import (
    CrossplaneFabricAppQuery,
    CrossplaneFabricAppQueryTargetEdgesNode,
)

AppNode = CrossplaneFabricAppQueryTargetEdgesNode

API_VERSION = "nfd41.lab/v1alpha1"
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


def build_chart(app: AppNode, values: Any) -> dict[str, Any]:
    """``spec.chart``, or an empty dict when no chart is set."""
    name = _value(app.chart_name)
    if not name:
        return {}

    chart: dict[str, Any] = {"name": name}
    repository = _value(app.chart_repository)
    if repository:
        chart["repository"] = repository
    version = _value(app.chart_version)
    if version:
        chart["version"] = version
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

        manifests = await self._payload(
            app.manifests_file, _value(app.manifests), kind="ServiceFabricAppManifestsFile", name=name
        )
        values = await self._payload(
            app.values_file, _value(app.chart_values), kind="ServiceFabricAppValuesFile", name=name
        )
        chart = build_chart(app, values)

        if not chart and not manifests:
            msg = (
                f"application {name!r} has neither a chart nor manifests; rendering it would produce a "
                "namespace and a network policy with no workload, which applies cleanly and deploys nothing"
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
        if chart:
            spec["chart"] = chart
        if manifests:
            spec["manifests"] = manifests
        expose = build_expose(app)
        if expose:
            spec["expose"] = expose
        spec["policy"] = build_policy(app)

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

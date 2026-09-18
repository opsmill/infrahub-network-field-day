"""Crossplane FabricPeering manifest transform.

Renders the ``FabricPeering`` custom resource the lab's Crossplane composition
consumes, from the Infrahub model. This is the loop the schema feature was built
for: change the model, re-render, review the diff, then push.

The artifact target is ``ServiceFabricPeering`` -- the ordered intent, "this
cluster peers with the fabric" -- because only the service kinds inherit
``CoreArtifactTarget``. Every rendered *value* comes from the technical layer
beneath it: the cluster supplies the local ASN, the auth secret's name, the
timers and the selectors, and each ``ClusterFabricPeering`` supplies a peer's
name, address and ASN.

Pure Python with a YAML dumper rather than a Jinja2 template. The output is a
structured document, not a text configuration, so building a dict and emitting
it is both shorter and safer than laying out lines by hand: the dumper decides
what needs quoting. That matters twice here -- ``65401:110`` is a valid
sexagesimal integer in YAML 1.1 and ``true`` is a boolean, and both must stay
strings for the Kubernetes API to accept them. A template gets that right only
as long as whoever edits it remembers to.

Two transformations happen before the dict is built:

* Selectors are stored as ``key=value`` strings, not JSON maps, because Infrahub
  1.10.6 returns a 500 for a JSON attribute key containing a dot or a slash --
  and every Kubernetes label selector has both. See schemas/MARKETPLACE.md.
* ``peer_address`` resolves to an ``IpamIPAddress``, whose value carries the
  mask. A BGP neighbour address must not.

An incomplete model raises rather than rendering. A manifest with an empty
``peers`` list applies cleanly, reports healthy, and carries no routes, which
the lab's own notes describe as the failure that "looks like a different
problem" every time.
"""

from __future__ import annotations

from typing import Any

import yaml
from infrahub_sdk.transforms import InfrahubTransform

from .crossplane_fabric_peering_query import (
    CrossplaneFabricPeeringQuery,
    CrossplaneFabricPeeringQueryTargetEdgesNode,
    CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNode,
    CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNode,
)

# Readable aliases for the verbose generated query model classes, following
# transforms/avd_anta_catalog.py.
ServiceNode = CrossplaneFabricPeeringQueryTargetEdgesNode
ClusterNode = CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNode
PeeringNode = CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNode

# The contract with the lab's composition.
API_VERSION = "otternet.lab/v1alpha1"
KIND = "FabricPeering"

# Timer keys the XRD understands, in the order it documents them. Fixing the
# order here rather than iterating the stored mapping keeps the render
# deterministic even if the JSON attribute's key order changes.
TIMER_KEYS = ("connectRetrySeconds", "holdTimeSeconds", "keepAliveSeconds")

# Wide enough that PyYAML never folds a scalar onto a second line. Folding is
# valid YAML but it would make a one-field change show up as a multi-line diff.
_MAX_WIDTH = 4096


class _ManifestDumper(yaml.SafeDumper):
    """A SafeDumper that indents sequences under the key that owns them.

    PyYAML puts a sequence at the same indentation as its parent key. Kubernetes
    manifests are conventionally written with it indented -- the lab's
    hand-written ``10-peering.yaml`` included -- so matching that keeps a diff
    between the rendered artifact and the file it replaces readable.
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        """Never emit an indentless sequence."""
        del indentless  # PyYAML passes it by keyword; overriding it is the point.
        super().increase_indent(flow, False)


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    """Quote any string containing a colon; leave the rest to the resolver.

    PyYAML emits ``65401:110`` as a plain scalar and reads it back as a string,
    but a colon inside a plain scalar is the one construct YAML parsers have
    historically disagreed about, and this manifest is read by a Go parser, not
    this one. Everything else -- ``true`` becoming ``'true'``, digits staying
    unquoted -- is the resolver's call, which is the reason for dumping rather
    than laying out lines by hand.
    """
    style = "'" if ":" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_ManifestDumper.add_representer(str, _represent_str)


def _value(field: Any) -> Any:
    """Unwrap an Infrahub ``{"value": ...}`` wrapper, tolerating absence."""
    return field.value if field is not None else None


def _parse_selector(entries: list[str] | None, *, field: str) -> dict[str, str]:
    """Turn ``["k=v", ...]`` into a label map.

    Splits on the FIRST ``=`` only: a label value may legitimately contain one.
    Keys are inserted in sorted order, which the dumper preserves, so the
    rendered map is deterministic.

    Raises:
        ValueError: if an entry has no ``=`` at all. Silently dropping it would
            leave a selector that matches more than intended, which for a BGP
            speaker selector means speakers where none were wanted.
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


def _strip_prefix_length(address: str) -> str:
    """``10.110.0.2/24`` -> ``10.110.0.2``. A neighbour is not a prefix."""
    return address.split("/", 1)[0]


def _timers(cluster: ClusterNode) -> dict[str, int]:
    """The XRD's timer keys that the model actually sets, in XRD order."""
    stored = _value(cluster.bgp_timers) or {}
    return {key: stored[key] for key in TIMER_KEYS if key in stored}


def _peer(peering: PeeringNode) -> dict[str, Any]:
    """One entry of ``spec.peers``.

    Raises:
        ValueError: if the peering has no address. The relationship is mandatory
            in the schema, so this guards a partially-migrated database rather
            than ordinary input -- but a peer with no address is a session that
            cannot come up.
    """
    name = _value(peering.name)
    address_node = peering.peer_address.node if peering.peer_address else None
    address = _value(address_node.address) if address_node else None

    if not address:
        msg = f"peering {name!r} has no peer_address; a BGP session needs a neighbour"
        raise ValueError(msg)

    return {
        "name": name,
        "address": _strip_prefix_length(address),
        "asn": _value(peering.peer_asn),
    }


class CrossplaneFabricPeeringTransform(InfrahubTransform):
    """Render one FabricPeering resource for a peering service."""

    query = "crossplane_fabric_peering"

    def transform(self, data: dict[str, Any]) -> str:
        """Render the manifest, or raise naming what the model is missing."""
        parsed = CrossplaneFabricPeeringQuery(**data)

        service = parsed.target.edges[0].node if parsed.target.edges else None
        if service is None:
            msg = "no ServiceFabricPeering matched the requested name"
            raise ValueError(msg)

        cluster = service.cluster.node if service.cluster else None
        if cluster is None:
            msg = f"service {_value(service.name)!r} has no cluster"
            raise ValueError(msg)

        cluster_name = _value(cluster.name)
        local_asn = _value(cluster.local_asn)
        if local_asn is None:
            msg = f"cluster {cluster_name!r} has no local_asn; a BGP session cannot come up without one"
            raise ValueError(msg)

        # Disabled sessions are not peers. Sorted by name so an unchanged model
        # renders byte-identically, independent of the schema's own order_by.
        enabled = [
            edge.node
            for edge in (service.peerings.edges if service.peerings else [])
            if edge.node is not None and _value(edge.node.enabled) is not False
        ]
        if not enabled:
            msg = (
                f"service {_value(service.name)!r} has no enabled peering; rendering an empty "
                "peers list would produce a resource that applies cleanly and carries nothing"
            )
            raise ValueError(msg)

        peers = sorted((_peer(node) for node in enabled), key=lambda peer: peer["name"] or "")

        # The service's own selector is the more specific statement of intent,
        # so it wins; otherwise the cluster's applies.
        advertisement = _value(service.advertisement_selector) or _value(cluster.advertisement_selector)

        # Insertion order is the manifest's key order, matching the XRD's own
        # field order. Optional fields are omitted when unset rather than
        # emitted as null: the XRD carries defaults, and a null overrides one.
        spec: dict[str, Any] = {"localASN": local_asn}
        optional: dict[str, Any] = {
            "authSecretName": _value(cluster.bgp_auth_secret_name),
            "nodeSelector": _parse_selector(_value(cluster.node_selector), field="node_selector"),
            "advertisementSelector": _parse_selector(advertisement, field="advertisement_selector"),
            "podCIDRCommunities": _value(cluster.pod_cidr_communities),
            "timers": _timers(cluster),
        }
        spec.update({key: value for key, value in optional.items() if value})
        spec["peers"] = peers

        # metadata.name comes from the CLUSTER, not the service. The XRD is
        # cluster-scoped with one resource per cluster, so the cluster is what
        # the resource is identified by -- and naming it after the service would
        # let a service rename silently create a second FabricPeering alongside
        # the deployed one instead of updating it. Two services pointing at one
        # cluster would collide here, which a check should catch anyway.
        manifest = {
            "apiVersion": API_VERSION,
            "kind": KIND,
            "metadata": {"name": cluster_name},
            "spec": spec,
        }

        return self._dump(manifest)

    @staticmethod
    def _dump(manifest: dict[str, Any]) -> str:
        """Emit the manifest as YAML.

        ``sort_keys=False`` because the key order above is the contract with the
        XRD, not something to alphabetise.
        """
        return yaml.dump(
            manifest,
            Dumper=_ManifestDumper,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=_MAX_WIDTH,
        )

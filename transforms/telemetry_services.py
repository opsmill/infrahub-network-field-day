"""Service monitoring for the Telemetry Collector Configuration (cycle 035).

A monitoring profile that names a ``service_kind`` watches services rather than
devices: every LIVE service of that kind (``ServiceGeneric``: every kind), where
live means what it means to every renderer here -- not ``decommissioning`` and
not ``decommissioned``. Withdrawing a service therefore withdraws its monitoring
in the same proposed change, and the artifact diff says so.

**This module knows HOW, never WHETHER.** ``SERVICE_DISPATCH`` says how a
measurement is rendered for a service kind; which kinds are watched, for which
measurements, how often and with what timeout is the profiles' business, and
``tests/unit/test_monitoring_measurements_contract.py`` holds the catalogue and
this table to each other in both directions.

What each measurement renders, and why it is that and not something else:

* ``service-lifecycle`` -- one Prometheus scrape of the service-lifecycle
  exporter, asking for exactly the kinds the profiles name (``?kinds=``). The
  exporter has no configuration of its own: the scrape URL in this artifact IS
  its configuration, so turning lifecycle reporting on or off for a kind is a
  diff a reviewer reads here.
* ``service-delivery`` -- intent only, ``otternet_intended_service_workload``
  and ``..._vip``, joined in Grafana to kube-state-metrics by namespace: the
  application's pods ready, and its LoadBalancer address assigned. The pods'
  readiness is the kubelet's own probing, which the composed pod policy admits
  by design (``fromEntities: host``).
* ``service-reachability`` -- a Telegraf ``net_response`` TCP probe of the VIP
  on every TCP port the application advertises, BUT ONLY WHERE THE
  APPLICATION'S POD GATE ADMITS THE COLLECTOR. The composition admits ingress
  by CIDR (which Cilium matches against traffic from OUTSIDE the cluster only),
  from the application's own namespace, and from node entities -- so a probe
  from Telegraf's pod is dropped at every gated application, measured against
  both otternet-demo and Grafana, whose seeded pod CIDR ``10.111.0.0/16`` does
  not admit a pod at all. Rendering those probes would report a healthy
  application as down forever; they are skipped and the artifact says why.
* ``service-access`` -- a grant's rules and the firewall holding them,
  ``otternet_intended_service_access``, joined to that firewall's
  ``DeploymentState``: the rule is on the device once the device is confirmed
  in sync with the artifact that carries it. The branch-side session itself is
  not probed: no collector sits at the branch.
* ``service-routing`` -- the BGP sessions a service is realised by,
  ``otternet_intended_service_bgp``, joined to the sessions the routers and
  switches already report. No new device polling: the WAN kinds name their
  sessions through the sites and peerings they reference, and the VRF-bound
  kinds (tenant cloud, onboarding, segment, peering) take the sessions the
  fabric's own structured configs place in their VRF.
* ``service-cabling`` -- a placed machine's cabled switch ports,
  ``otternet_intended_service_interface``, joined to their operational state.

Every service a profile watches also gets ``otternet_intended_service``, which
is how a dashboard knows a service is watched at all -- and by which profile.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any

FABRIC_APP = "ServiceFabricApp"
APP_ACCESS = "ServiceAppAccess"
L3VPN = "ServiceL3vpn"
INTERNET = "ServiceInternetAccess"
TENANT_CLOUD = "ServiceTenantCloud"
ONBOARDING = "ServiceTenantOnboarding"
SEGMENT = "ServiceNetworkSegment"
PLACEMENT = "ServiceServerPlacement"
PEERING = "ServiceFabricPeering"
SERVICE_GENERIC = "ServiceGeneric"
SERVICE_KINDS = (FABRIC_APP, APP_ACCESS, L3VPN, INTERNET, TENANT_CLOUD, ONBOARDING, SEGMENT, PLACEMENT, PEERING)

# The same reading of `status` every renderer here applies: these are gone.
WITHDRAWN = frozenset({"decommissioning", "decommissioned"})

# Where the service-lifecycle exporter answers, from inside the workload
# cluster: beside Infrahub on the host, reached out of the node's management
# interface the way Prometheus reaches the Infrahub exporter on 8002.
LIFECYCLE_EXPORTER = "http://172.20.41.1:8003/metrics"

# The composition's own annotation for a pinned LoadBalancer address.
PINNED_ADDRESS = "lbipam.cilium.io/ips"

# measurement -> service kind -> the checks it renders. HOW, never WHETHER.
SERVICE_DISPATCH: dict[str, dict[str, tuple[str, ...]]] = {
    "service-lifecycle": dict.fromkeys(SERVICE_KINDS, ("lifecycle",)),
    "service-delivery": {FABRIC_APP: ("workload", "vip")},
    "service-reachability": {FABRIC_APP: ("probe",)},
    "service-access": {APP_ACCESS: ("access",)},
    "service-routing": {
        L3VPN: ("bgp",),
        INTERNET: ("bgp",),
        TENANT_CLOUD: ("bgp",),
        ONBOARDING: ("bgp",),
        SEGMENT: ("bgp", "svi"),
        PEERING: ("bgp",),
    },
    "service-cabling": {PLACEMENT: ("interface",)},
}

# The series intended.prom carries for services, with their HELP text. Listed
# so a dashboard contract can name them, and so an empty section still declares
# its type rather than vanishing.
INTENDED_SERIES: dict[str, str] = {
    "otternet_intended_service": "A live service a monitoring profile watches.",
    "otternet_intended_service_bgp": "A BGP session that realises a service.",
    "otternet_intended_service_workload": "A service's workload, by namespace, expected ready.",
    "otternet_intended_service_vip": "A service's LoadBalancer address, expected assigned from its block.",
    "otternet_intended_service_probe": "A service port the collector probes.",
    "otternet_intended_service_access": "A firewall rule a grant materialised, on the firewall holding it.",
    "otternet_intended_service_interface": "A switch port a placed machine is cabled to, expected up.",
    "otternet_intended_service_svi": "A switch a segment's gateway should render on.",
}


class ServiceMonitoringError(ValueError):
    """A service profile asks for something no renderer can produce."""


@dataclass
class ServiceWatch:
    """One live service, and what the profiles watching it ask for."""

    node: Any
    name: str
    kind: str
    owner: str
    interval: int
    timeout: int
    measurements: set[str] = field(default_factory=set)
    profiles: set[str] = field(default_factory=set)

    def checks(self) -> set[str]:
        return {check for m in self.measurements for check in SERVICE_DISPATCH[m].get(self.kind, ())}


@dataclass
class LifecycleScrape:
    """The one scrape of the lifecycle exporter, and the kinds it asks for."""

    kinds: set[str] = field(default_factory=set)
    profiles: set[str] = field(default_factory=set)
    interval: int = 0


def val(node: Any, name: str) -> Any:
    attr = getattr(node, name, None)
    return getattr(attr, "value", None) if attr is not None else None


def peer(node: Any, name: str) -> Any:
    rel = getattr(node, name, None)
    return getattr(rel, "node", None) if rel is not None else None


def edges(node: Any, name: str) -> list[Any]:
    rel = getattr(node, name, None)
    return [e.node for e in (getattr(rel, "edges", None) or []) if getattr(e, "node", None) is not None]


def select(profiles: list[Any], services: list[Any], notes: list[str]) -> tuple[list[ServiceWatch], LifecycleScrape]:
    """Every live service the service profiles watch, and the lifecycle scrape.

    Raises:
        ServiceMonitoringError: for a service profile naming a kind no renderer
            knows, a device measurement, or a device group -- each of which would
            otherwise render as nothing and say nothing.
    """
    by_name: dict[str, ServiceWatch] = {}
    scrape = LifecycleScrape()
    for profile in profiles:
        pname = str(val(profile, "name"))
        kind = str(val(profile, "service_kind"))
        if not val(profile, "enabled"):
            continue
        if kind != SERVICE_GENERIC and kind not in SERVICE_KINDS:
            msg = f"profile {pname!r} watches service kind {kind!r}, which no renderer knows (known: {SERVICE_KINDS})"
            raise ServiceMonitoringError(msg)
        if edges(profile, "device_groups"):
            msg = f"profile {pname!r} watches services and also names device groups; a profile watches one or the other"
            raise ServiceMonitoringError(msg)
        measurements = sorted(str(val(m, "name")) for m in edges(profile, "measurements"))
        unknown = [m for m in measurements if m not in SERVICE_DISPATCH]
        if unknown:
            msg = f"profile {pname!r} watches services for measurements no service renderer knows: {unknown}"
            raise ServiceMonitoringError(msg)
        interval = int(val(profile, "interval_seconds") or 30)
        timeout = int(val(profile, "timeout_seconds") or 5)
        kinds = SERVICE_KINDS if kind == SERVICE_GENERIC else (kind,)

        if "service-lifecycle" in measurements:
            scrape.kinds.add(kind)
            scrape.profiles.add(pname)
            scrape.interval = min(scrape.interval or interval, interval)

        matched = 0
        for service in services:
            skind = getattr(service, "typename__", None)
            if skind not in kinds or str(val(service, "status")) in WITHDRAWN:
                continue
            applicable = [m for m in measurements if skind in SERVICE_DISPATCH[m] and m != "service-lifecycle"]
            if not applicable:
                continue
            matched += 1
            name = str(val(service, "name"))
            owner = peer(service, "owner")
            watch = by_name.setdefault(
                name,
                ServiceWatch(
                    node=service,
                    name=name,
                    kind=skind,
                    owner=str(getattr(owner, "display_label", "") or ""),
                    interval=interval,
                    timeout=timeout,
                ),
            )
            watch.interval = min(watch.interval, interval)
            watch.timeout = min(watch.timeout, timeout)
            watch.measurements.update(applicable)
            watch.profiles.add(pname)
        if matched == 0 and "service-lifecycle" not in measurements:
            notes.append(f"# matched nothing: profile {pname} (no live {kind})")
    return [by_name[name] for name in sorted(by_name)], scrape


# ---------------------------------------------------------------------------
# telegraf.conf
# ---------------------------------------------------------------------------


def lifecycle_input(collector: str, scrape: LifecycleScrape) -> list[dict[str, Any]]:
    """The scrape of the lifecycle exporter, as (table, items) blocks."""
    if not scrape.kinds:
        return []
    kinds = ",".join(sorted(scrape.kinds))
    return [
        {
            "comment": f"# service lifecycle: {kinds}",
            "table": "inputs.prometheus",
            "items": {
                "urls": [f"{LIFECYCLE_EXPORTER}?kinds={kinds}"],
                "metric_version": 2,
                "interval": f"{scrape.interval}s",
                "timeout": "10s",
            },
            "tags": {"collector": collector, "profile": ",".join(sorted(scrape.profiles))},
        }
    ]


def probe_targets(watch: ServiceWatch, pinned: str | None, notes: list[str]) -> list[tuple[str, int]]:
    """(address, port) for every TCP port the application advertises, or none and why."""
    node = watch.node
    if not val(node, "exposed"):
        notes.append(f"# not probed: {watch.name} is not exposed, so it has no VIP")
        return []
    if val(node, "policy_default_deny") or (getattr(node.allowed_source_prefixes, "count", 0) or 0) > 0:
        notes.append(
            f"# not probed: {watch.name}'s pod gate admits no in-cluster source (the composition admits CIDRs "
            "from outside the cluster, its own namespace and node entities); service-delivery reports its health"
        )
        return []
    block = peer(node, "vip_block")
    prefix = val(block, "prefix") if block is not None else None
    if not prefix:
        notes.append(f"# not probed: {watch.name} is exposed and has no vip_block yet")
        return []
    # Cilium LB-IPAM hands an application's first Service the first address of
    # the application's own pool -- the composition gives each one a pool of
    # its block alone -- unless its values pin one.
    address = pinned or str(ipaddress.ip_network(prefix, strict=False).network_address)
    ports = sorted(
        {
            int(val(svc, "port"))
            for svc in edges(node, "advertised_services")
            if val(svc, "port") and str(val(peer(svc, "ip_protocol"), "name") or "").lower() == "tcp"
        }
    )
    if not ports:
        notes.append(f"# not probed: {watch.name} advertises no TCP service")
    return [(address, port) for port in ports]


def probe_inputs(collector: str, watch: ServiceWatch, targets: list[tuple[str, int]]) -> list[dict[str, Any]]:
    return [
        {
            "comment": f"# {watch.name}: service-reachability, {address}:{port}",
            "table": "inputs.net_response",
            "items": {
                "protocol": "tcp",
                "address": f"{address}:{port}",
                "timeout": f"{watch.timeout}s",
                "interval": f"{watch.interval}s",
            },
            "tags": {
                "collector": collector,
                "profile": ",".join(sorted(watch.profiles)),
                "service": watch.name,
                "service_kind": watch.kind,
            },
        }
        for address, port in targets
    ]


def find_pinned(values: Any) -> str | None:
    """The first ``lbipam.cilium.io/ips`` anywhere in a values document."""
    if isinstance(values, dict):
        if values.get(PINNED_ADDRESS):
            return str(values[PINNED_ADDRESS]).split(",", 1)[0].strip()
        for value in values.values():
            found = find_pinned(value)
            if found:
                return found
    if isinstance(values, list):
        for item in values:
            found = find_pinned(item)
            if found:
                return found
    return None


# ---------------------------------------------------------------------------
# intended.prom
# ---------------------------------------------------------------------------


@dataclass
class Context:
    """What the service checks join to, gathered once per render."""

    # device -> [(vrf, peer address)] from the switches' structured configs
    neighbors: dict[str, list[tuple[str, str]]]
    device_kinds: dict[str, str]
    # circuit id -> [(device, peer address)] recorded on the WAN site using it
    site_sessions: dict[str, list[tuple[str, str]]]
    # (device, device kind, interface) cabled to each device name
    cabled_to: dict[str, list[tuple[str, str, str]]]


def series(metric: str, labels: dict[str, str], value: int = 1) -> str:
    """One Prometheus text-format sample, labels sorted, values escaped."""
    rendered = ",".join(f'{key}="{_escape(labels[key])}"' for key in sorted(labels))
    return f"{metric}{{{rendered}}} {value}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def intended_lines(
    watches: list[ServiceWatch], ctx: Context, probes: dict[str, list[tuple[str, int]]], notes: list[str]
) -> list[str]:
    """The services' half of intended.prom: every series type, declared even when empty."""
    out: dict[str, list[str]] = {metric: [] for metric in INTENDED_SERIES}
    for watch in watches:
        checks = watch.checks()
        rows: list[tuple[str, dict[str, str]]] = [
            ("otternet_intended_service", {"owner": watch.owner, "profile": ",".join(sorted(watch.profiles))})
        ]
        rows += [
            ("otternet_intended_service_probe", {"address": a, "port": str(p)}) for a, p in probes.get(watch.name, [])
        ]
        for check, rows_of in _ROWS.items():
            if check in checks:
                rows += rows_of(watch, ctx, notes)
        for metric, labels in rows:
            out[metric].append(series(metric, {"service": watch.name, "service_kind": watch.kind, **labels}))
    lines: list[str] = []
    for metric, help_text in INTENDED_SERIES.items():
        lines += [f"# TYPE {metric} gauge", f"# HELP {metric} {help_text}", *sorted(set(out[metric]))]
    return lines


Rows = list[tuple[str, dict[str, str]]]


def _workload_rows(watch: ServiceWatch, _ctx: Context, _notes: list[str]) -> Rows:
    namespace = val(watch.node, "namespace_name")
    return [("otternet_intended_service_workload", {"namespace": str(namespace)})] if namespace else []


def _vip_rows(watch: ServiceWatch, _ctx: Context, _notes: list[str]) -> Rows:
    node = watch.node
    block = peer(node, "vip_block")
    prefix = val(block, "prefix") if block is not None else None
    if not (val(node, "exposed") and prefix and val(node, "namespace_name")):
        return []
    return [
        ("otternet_intended_service_vip", {"namespace": str(val(node, "namespace_name")), "vip_block": str(prefix)})
    ]


def _access_rows(watch: ServiceWatch, _ctx: Context, notes: list[str]) -> Rows:
    node = watch.node
    rules = edges(node, "granted_rules")
    if not rules:
        notes.append(f"# no rule yet: {watch.name} has materialised no firewall rule")
    app = val(peer(node, "application"), "name") or ""
    source = val(peer(node, "source_site"), "name") or val(peer(node, "source_zone"), "name") or ""
    return [
        (
            "otternet_intended_service_access",
            {
                "application": str(app),
                "source": str(source),
                "destination_zone": str(val(peer(rule, "destination_zone"), "name") or ""),
                "rule": str(val(rule, "name")),
                "firewall": str(val(peer(peer(rule, "policy"), "device_target"), "name") or ""),
            },
        )
        for rule in rules
    ]


def _bgp_rows(watch: ServiceWatch, ctx: Context, notes: list[str]) -> Rows:
    sessions = _sessions(watch, ctx)
    if not sessions:
        notes.append(f"# no BGP session realises {watch.name} ({watch.kind})")
    rows: Rows = []
    for device, peer_address, vrf in sessions:
        labels = {"device": device, "kind": ctx.device_kinds.get(device, ""), "peer_address": peer_address}
        if vrf:
            labels["vrf"] = vrf
        rows.append(("otternet_intended_service_bgp", labels))
    return rows


def _svi_rows(watch: ServiceWatch, _ctx: Context, _notes: list[str]) -> Rows:
    svi = peer(watch.node, "svi")
    vlan = val(svi, "svi_id") if svi is not None else None
    if not vlan:
        return []
    return [
        ("otternet_intended_service_svi", {"device": device, "vlan": str(vlan)})
        for device in sorted(_tagged_switches(watch.node))
    ]


def _interface_rows(watch: ServiceWatch, ctx: Context, _notes: list[str]) -> Rows:
    server = val(peer(watch.node, "server"), "name")
    return [
        ("otternet_intended_service_interface", {"device": device, "kind": kind, "interface": interface})
        for device, kind, interface in (ctx.cabled_to.get(str(server), []) if server else [])
    ]


# check -> how its intended rows are built. `probe` is not here: its rows come
# from the probes actually rendered, so a skipped probe declares no intent.
_ROWS = {
    "workload": _workload_rows,
    "vip": _vip_rows,
    "access": _access_rows,
    "bgp": _bgp_rows,
    "svi": _svi_rows,
    "interface": _interface_rows,
}


def _tagged_switches(segment: Any) -> set[str]:
    return {
        str(val(device, "name"))
        for tag in edges(segment, "avd_tags")
        for rack in edges(tag, "racks")
        for device in edges(rack, "devices")
        if getattr(device, "typename__", None) == "DcimFabricSwitch" and val(device, "name")
    }


def _vrf_sessions(ctx: Context, vrfs: set[str], devices: set[str] | None) -> list[tuple[str, str, str]]:
    return [
        (device, peer_address, vrf)
        for device, found in ctx.neighbors.items()
        if devices is None or device in devices
        for vrf, peer_address in found
        if vrf in vrfs
    ]


def _sessions(watch: ServiceWatch, ctx: Context) -> list[tuple[str, str, str]]:
    """(device, peer address, vrf) for every BGP session realising the service."""
    node, kind = watch.node, watch.kind
    found: list[tuple[str, str, str]] = []
    if kind == L3VPN:
        for circuit in edges(node, "circuits"):
            found += [(device, peer_address, "") for device, peer_address in ctx.site_sessions.get(circuit.id, [])]
    elif kind == INTERNET:
        peering = peer(node, "peering")
        for session in edges(peering, "bgp_sessions") if peering is not None else []:
            device = val(peer(session, "device"), "name")
            if device and val(session, "peer_address"):
                found.append((str(device), str(val(session, "peer_address")), ""))
    elif kind == TENANT_CLOUD:
        vrf = val(peer(node, "vrf"), "name")
        found = _vrf_sessions(ctx, {str(vrf)}, None) if vrf else []
    elif kind == ONBOARDING:
        tenant = peer(node, "evpn_tenant")
        vrfs = {str(val(v, "name")) for v in edges(tenant, "vrfs")} if tenant is not None else set()
        found = _vrf_sessions(ctx, vrfs, None)
    elif kind == SEGMENT:
        svi = peer(node, "svi")
        vrf = val(peer(svi, "vrf"), "name") if svi is not None else None
        found = _vrf_sessions(ctx, {str(vrf)}, _tagged_switches(node)) if vrf else []
    elif kind == PEERING:
        for peering in edges(node, "peerings"):
            device = val(peer(peering, "peer_device"), "name")
            svi = peer(peering, "svi")
            vrf = val(peer(svi, "vrf"), "name") if svi is not None else None
            if device and vrf:
                found += _vrf_sessions(ctx, {str(vrf)}, {str(device)})
    return sorted(set(found))

"""Telemetry Collector Configuration transform (cycle 034).

Renders one collector's whole Telegraf configuration from monitoring intent, as
a Kubernetes ConfigMap that Vidra's third sync delivers into the collector's
namespace. Every target, subscription and filter Telegraf runs with came from a
``MonitoringProfile``: which devices (the members of the groups a profile names,
optionally narrowed to one role), which measurements, and how often.

**Infrahub decides what is monitored the way it decides what is configured.** A
change to a profile, or a device joining a group, moves this artifact, and the
proposed change shows the difference -- which inputs appear and which go --
before anything is collected differently.

**Intended state rides along.** ``intended.prom`` carries what Infrahub expects
to be true -- the BGP sessions each device is configured with, the links that
are cabled, the interfaces that should be up -- as Prometheus series Telegraf
reads back in. A dashboard joining them to the observed series shows "intended
but down" and "up but never intended", which neither half can show alone.

**Dispatch is by (measurement, device kind)**, and ``DISPATCH`` is the contract:
``tests/unit/test_monitoring_measurements_contract.py`` holds it against the
measurement catalogue. A measurement that does not apply to a matched device's
kind is skipped *and said so* in the rendered file, never silently dropped.

**Services are watched too (cycle 035).** A profile naming a ``service_kind``
watches every live service of that kind instead of devices; how each service
measurement renders is ``transforms/telemetry_services.py``. With no service
profile the render is exactly the device render, line for line.

Two things this refuses rather than renders:

* **An empty configuration.** Telegraf with no inputs refuses to start, and an
  artifact with nothing in it would replace a working ConfigMap. Raising leaves
  the artifact in error and the running collector on its last good config.
* **A device with no address.** Emitting an input with an empty address is a
  collector that fails forever on one target; skipping it and saying so is a
  device visibly not watched.

No credential is rendered except the firewall's SNMP community, which the device
itself receives in its configuration. gNMI's username and password are
``${GNMI_USERNAME}`` and ``${GNMI_PASSWORD}``, substituted by Telegraf from the
Secret ``invoke cluster`` creates. One pair serves both gNMI families: the SR
Linux routers render the same ``NetworkLocalUser`` ``admin`` hash as the switches.

**The WAN routers and the fabric switches are subscribed through the same
OpenConfig paths**, so their series arrive under the same names --
``bgp_neighbor_session_state_code``, ``bgp_afi_safi_*``, ``interface_counters_*``,
``interface_status_oper_status_code``, ``cpu_*``, ``memory_*`` -- with the same
labels. Measured with Telegraf 1.40 against an SR Linux 26.7 router: every
subscription answered, and the BGP series carries ``neighbor_address`` and the
network instance as ``name`` exactly as EOS does. A dashboard written for the
fabric therefore covers the WAN without a second query, which is what replacing
frr_exporter bought. ``tests/unit/test_dashboard_metrics_contract.py`` holds
every dashboard panel to the series this renders.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from typing import Any

import yaml
from infrahub_sdk.transforms import InfrahubTransform

from solution_arista_avd.protocols import AvdStructuredConfigFile

from .telemetry_collector_config_query import TelemetryCollectorConfigQuery
from .telemetry_services import (
    SERVICE_DISPATCH,
    Context,
    LifecycleScrape,
    ServiceMonitoringError,
    ServiceWatch,
    find_pinned,
    intended_lines,
    lifecycle_input,
    probe_inputs,
    probe_targets,
    select,
    series,
)

SWITCH = "DcimFabricSwitch"
ROUTER = "DcimDevice"
FIREWALL = "SecurityFirewall"
SERVER = "ComputePhysicalServer"
KINDS = (SWITCH, ROUTER, FIREWALL, SERVER)
# The kinds collected over gNMI. Everything else is SNMP (the firewall) or a
# Prometheus scrape (the k3s nodes' node-exporter).
GNMI_KINDS = (SWITCH, ROUTER)

GNMI_PORT = 6030
# SR Linux's gNMI server in the management network instance, as srl_config
# renders it: TLS with `default-tls-profile`, a certificate the router generates
# for itself -- so it is encrypted and not verified, rather than pinned to a
# certificate that does not survive a redeploy.
SRL_GNMI_PORT = 57400
NODE_EXPORTER_PORT = 9100
SNMP_PORT = 161
PROMETHEUS_LISTEN = ":9273"

# RFC 4271's finite-state machine, in order, so ESTABLISHED is the one value a
# dashboard compares against.
BGP_STATE_CODES = {"IDLE": 1, "CONNECT": 2, "ACTIVE": 3, "OPENSENT": 4, "OPENCONFIRM": 5, "ESTABLISHED": 6}
# OpenConfig's oper-status, numbered as IF-MIB's ifOperStatus so a gNMI interface
# and an SNMP one compare with the same `== 1`. Measured against EOS and SR Linux
# with Telegraf 1.40: both report these strings.
OPER_STATUS_CODES = {
    "UP": 1,
    "DOWN": 2,
    "TESTING": 3,
    "UNKNOWN": 4,
    "DORMANT": 5,
    "NOT_PRESENT": 6,
    "LOWER_LAYER_DOWN": 7,
}
INTENDED_FILE = "/etc/telegraf-intent/intended.prom"

# ---------------------------------------------------------------------------
# The dispatch table: measurement -> kind -> what to render.
#
#   gnmi:       (subscription name, origin, path)
#   prometheus: metric-name globs Telegraf keeps from the device's exporter
#   snmp:       (table name, [(field name, numeric OID, is_tag)])
#
# Numeric OIDs, so Telegraf needs no MIB files inside its image.
# ---------------------------------------------------------------------------

_IF_TABLE = (
    "interface",
    [
        ("ifName", ".1.3.6.1.2.1.31.1.1.1.1", True),
        # The interface's description, which junos_config renders from the
        # model, so a panel can say what a port is for and not only which
        # port it is.
        ("ifAlias", ".1.3.6.1.2.1.31.1.1.1.18", True),
        ("ifHCInOctets", ".1.3.6.1.2.1.31.1.1.1.6", False),
        ("ifHCOutOctets", ".1.3.6.1.2.1.31.1.1.1.10", False),
        ("ifInErrors", ".1.3.6.1.2.1.2.2.1.14", False),
        ("ifOutErrors", ".1.3.6.1.2.1.2.2.1.20", False),
        ("ifOperStatus", ".1.3.6.1.2.1.2.2.1.8", False),
    ],
)
_JNX_OPERATING = (
    "jnx_operating",
    [
        ("jnxOperatingDescr", ".1.3.6.1.4.1.2636.3.1.13.1.5", True),
        ("jnxOperatingCPU", ".1.3.6.1.4.1.2636.3.1.13.1.8", False),
        ("jnxOperatingBuffer", ".1.3.6.1.4.1.2636.3.1.13.1.11", False),
    ],
)
_JNX_SESSIONS = (
    "jnx_spu",
    [("jnxJsSPUMonitoringCurrentFlowSession", ".1.3.6.1.4.1.2636.3.39.1.12.1.1.1.6", False)],
)

_OC_INTERFACES = ("interface_counters", "openconfig", "/interfaces/interface/state/counters")
# Operational state, which the measurement promises and the counters path does
# not carry. OpenConfig reports a string, so it is mapped onto IF-MIB's
# ifOperStatus numbers -- the values the firewall's SNMP table already reports
# -- and "a cabled interface that is down" is one comparison for every family.
_OC_INTERFACE_STATUS = ("interface_status", "openconfig", "/interfaces/interface/state/oper-status")
_OC_BGP = (
    "bgp_neighbor",
    "openconfig",
    "/network-instances/network-instance/protocols/protocol/bgp/neighbors/neighbor/state",
)
# Prefixes per session and address family: the OpenConfig per-AFI counts rather
# than an EOS-native Sysdb path. Stable across EOS releases, answered by SR Linux
# under the same name, and on the leaves' l2vpn-evpn neighbours exactly the EVPN
# routes received.
_OC_BGP_PREFIXES = (
    "bgp_afi_safi",
    "openconfig",
    "/network-instances/network-instance/protocols/protocol/bgp/neighbors/neighbor/afi-safis/afi-safi/state/prefixes",
)
_OC_CPU = ("cpu", "openconfig", "/components/component/cpu/utilization/state")
_OC_MEMORY = ("memory", "openconfig", "/components/component/state/memory")

DISPATCH: dict[str, dict[str, Any]] = {
    "interface-counters": {
        SWITCH: [_OC_INTERFACES, _OC_INTERFACE_STATUS],
        ROUTER: [_OC_INTERFACES, _OC_INTERFACE_STATUS],
        FIREWALL: [_IF_TABLE],
    },
    # State AND prefixes, as the measurement says: a session that is up and
    # carries nothing is the failure a state panel alone cannot show.
    "bgp-neighbor-state": {
        SWITCH: [_OC_BGP, _OC_BGP_PREFIXES],
        ROUTER: [_OC_BGP, _OC_BGP_PREFIXES],
    },
    # The same subscription, kept as its own measurement so a profile can ask
    # for EVPN routes without every session's state. A device asked for both
    # subscribes once: an input's specs are deduplicated.
    "evpn-routes": {
        SWITCH: [_OC_BGP_PREFIXES],
    },
    "system-resources": {
        SWITCH: [_OC_CPU, _OC_MEMORY],
        ROUTER: [_OC_CPU, _OC_MEMORY],
        FIREWALL: [_JNX_OPERATING],
    },
    "security-sessions": {
        FIREWALL: [_JNX_SESSIONS],
    },
    "node-resources": {
        SERVER: [
            "node_cpu_seconds_total",
            "node_memory_MemAvailable_bytes",
            "node_memory_MemTotal_bytes",
            "node_network_receive_bytes_total",
            "node_network_transmit_bytes_total",
        ],
    },
}


class TelemetryCollectorConfigError(ValueError):
    """The intent cannot be rendered into a configuration Telegraf would run."""


@dataclass
class Device:
    """One watched device, flattened out of whichever fragment matched it."""

    name: str
    kind: str
    role: str
    address: str | None
    rack: str | None = None
    pod: str | None = None
    structured_config_id: str | None = None
    bgp_neighbors: tuple[str, ...] = ()
    snmp_community: str | None = None


@dataclass
class Watch:
    """What one device is watched for at one interval."""

    device: Device
    interval: int
    measurements: set[str] = field(default_factory=set)
    profiles: set[str] = field(default_factory=set)


def _val(node: Any, name: str) -> Any:
    """``node.<name>.value``, or None at any missing step."""
    attr = getattr(node, name, None)
    return getattr(attr, "value", None) if attr is not None else None


def _peer(node: Any, name: str) -> Any:
    """``node.<name>.node``, or None at any missing step."""
    rel = getattr(node, name, None)
    return getattr(rel, "node", None) if rel is not None else None


def _bare(address: str | None) -> str | None:
    return address.split("/", 1)[0] if address else None


def _device(member: Any) -> Device | None:
    kind = getattr(member, "typename__", None)
    if kind not in KINDS:
        return None
    address_rel = "mgmt_ip" if kind == SWITCH else "telemetry_address"
    address_node = _peer(member, address_rel)
    device = Device(
        name=str(_val(member, "name")),
        kind=kind,
        role=str(_val(member, "role") or ""),
        address=_bare(_val(address_node, "address")) if address_node is not None else None,
    )
    if kind == SWITCH:
        device.rack = _val(_peer(member, "rack"), "name")
        device.pod = _val(_peer(member, "pod"), "name")
        artifact = _peer(member, "avd_artifact")
        sc_file = _peer(artifact, "structured_config_file") if artifact is not None else None
        device.structured_config_id = getattr(sc_file, "id", None)
    if kind == ROUTER:
        neighbors = getattr(getattr(member, "bgp_neighbors", None), "edges", None) or []
        device.bgp_neighbors = tuple(
            sorted(str(_val(e.node, "peer_address")) for e in neighbors if e.node and _val(e.node, "peer_address"))
        )
    if kind == FIREWALL:
        device.snmp_community = _val(member, "snmp_community")
    return device


# ---------------------------------------------------------------------------
# A minimal, deterministic TOML emitter. Telegraf's configuration uses tables,
# arrays of tables and scalar values; nothing here needs more. Strings are
# JSON-escaped, which is valid TOML basic-string syntax.
# ---------------------------------------------------------------------------


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    return json.dumps(str(value))


def _kv(indent: str, items: dict[str, Any]) -> list[str]:
    return [f"{indent}{key} = {_toml_value(value)}" for key, value in items.items()]


class TelemetryCollectorConfig(InfrahubTransform):
    """Render one collector's Telegraf configuration as a ConfigMap."""

    query = "telemetry_collector_config"

    async def transform(self, data: dict[str, Any]) -> str:
        """Render the ConfigMap, or raise naming what the intent is missing."""
        parsed = TelemetryCollectorConfigQuery(**data)
        edges = parsed.monitoring_collector.edges
        collector = edges[0].node if edges else None
        if collector is None:
            msg = "no MonitoringCollector matched the requested name"
            raise TelemetryCollectorConfigError(msg)

        name = str(_val(collector, "name"))
        namespace = _val(collector, "namespace_name")
        config_map = _val(collector, "config_map_name") or "telegraf-intent"
        if not namespace:
            msg = f"collector {name!r} has no namespace_name; the ConfigMap would land in Vidra's default namespace"
            raise TelemetryCollectorConfigError(msg)

        notes: list[str] = []
        watches = self._watches(collector, notes)
        service_watches, scrape = self._service_watches(collector, parsed, notes)
        profiles = [e.node for e in collector.monitoring_profiles.edges if e.node is not None]
        probes = await self._probes(service_watches, notes, namespace=str(namespace), profiles=profiles)
        intended = await self._intended(watches, parsed, service_watches, probes, notes)
        conf = self._render_conf(name, watches, notes, scrape, service_watches, probes)

        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": config_map,
                "namespace": namespace,
                "labels": {"app.kubernetes.io/managed-by": "infrahub", "otternet.lab/collector": name},
            },
            "data": {"telegraf.conf": conf, "intended.prom": intended},
        }
        return _dump(manifest)

    # -- selection ---------------------------------------------------------

    @staticmethod
    def _watches(collector: Any, notes: list[str]) -> list[Watch]:
        """Every (device, interval) the profiles ask for, with what to collect."""
        by_key: dict[tuple[str, int], Watch] = {}
        profiles = sorted(
            (e.node for e in collector.monitoring_profiles.edges if e.node is not None),
            key=lambda p: str(_val(p, "name")),
        )
        for profile in profiles:
            pname = str(_val(profile, "name"))
            if not _val(profile, "enabled"):
                notes.append(f"# disabled: profile {pname} renders nothing")
                continue
            if _val(profile, "service_kind"):
                continue  # a service profile: see _service_watches
            interval = int(_val(profile, "interval_seconds") or 30)
            role = _val(profile, "device_role")
            measurements = sorted(str(_val(m.node, "name")) for m in profile.measurements.edges if m.node)
            unknown = [m for m in measurements if m not in DISPATCH]
            if unknown:
                hint = (
                    " (service measurements need the profile's service_kind)"
                    if set(unknown) & set(SERVICE_DISPATCH)
                    else ""
                )
                msg = f"profile {pname!r} names measurements no renderer knows: {unknown}{hint}"
                raise TelemetryCollectorConfigError(msg)
            # device_groups is optional in the schema because a service profile
            # names none; a DEVICE profile without one would render nothing.
            if not profile.device_groups.edges:
                msg = f"profile {pname!r} watches devices and names no device group"
                raise TelemetryCollectorConfigError(msg)

            matched = 0
            for group in (g.node for g in profile.device_groups.edges if g.node is not None):
                for member_edge in group.members.edges or []:
                    device = _device(member_edge.node) if member_edge and member_edge.node else None
                    if device is None or (role and device.role != role):
                        continue
                    matched += 1
                    applicable = [m for m in measurements if device.kind in DISPATCH[m]]
                    notes.extend(
                        f"# skipped: {pname}/{m} on {device.name} ({device.kind})"
                        for m in measurements
                        if m not in applicable
                    )
                    if not applicable:
                        continue
                    if device.address is None:
                        notes.append(f"# skipped: {device.name} ({device.kind}) has no address to collect from")
                        continue
                    watch = by_key.setdefault((device.name, interval), Watch(device=device, interval=interval))
                    watch.measurements.update(applicable)
                    watch.profiles.add(pname)
            if matched == 0:
                notes.append(f"# matched nothing: profile {pname}")
        return [by_key[key] for key in sorted(by_key)]

    @staticmethod
    def _service_watches(
        collector: Any, parsed: TelemetryCollectorConfigQuery, notes: list[str]
    ) -> tuple[list[ServiceWatch], LifecycleScrape]:
        """Every live service the service profiles watch (cycle 035)."""
        profiles = sorted(
            (
                e.node
                for e in collector.monitoring_profiles.edges
                if e.node is not None and _val(e.node, "service_kind")
            ),
            key=lambda p: str(_val(p, "name")),
        )
        services = [e.node for e in parsed.service_generic.edges if e.node is not None]
        try:
            return select(profiles, services, notes)
        except ServiceMonitoringError as exc:
            raise TelemetryCollectorConfigError(str(exc)) from exc

    async def _probes(
        self, watches: list[ServiceWatch], notes: list[str], *, namespace: str, profiles: list[Any]
    ) -> dict[str, list[tuple[str, int]]]:
        """(address, port) per probed application.

        A gated application is probed only where its own FabricApp admits this
        collector's namespace -- decided by ``collector_admission`` over this
        collector's profiles, the derivation ``crossplane_fabric_app`` renders
        the admission from.

        The values file is read only for an application that will be probed,
        for the address its values pin; the download is the expensive half.
        """
        probes: dict[str, list[tuple[str, int]]] = {}
        for watch in watches:
            if "probe" not in watch.checks():
                continue
            pinned = None
            values_file = _peer(watch.node, "values_file")
            if values_file is not None and probe_targets(watch, None, [], namespace=namespace, profiles=profiles):
                stub = await self.client.get(kind="ServiceFabricAppValuesFile", id=values_file.id)
                content = await stub.download_file()
                text = content.decode() if isinstance(content, bytes) else str(content)
                try:
                    pinned = find_pinned(yaml.safe_load(text))
                except yaml.YAMLError:
                    pinned = None
            targets = probe_targets(watch, pinned, notes, namespace=namespace, profiles=profiles)
            if targets:
                probes[watch.name] = targets
        return probes

    # -- telegraf.conf -----------------------------------------------------

    def _render_conf(
        self,
        collector: str,
        watches: list[Watch],
        notes: list[str],
        scrape: LifecycleScrape | None = None,
        service_watches: list[ServiceWatch] | None = None,
        probes: dict[str, list[tuple[str, int]]] | None = None,
    ) -> str:
        lines = [
            "# Rendered by Infrahub from MonitoringProfile intent for collector "
            f"{collector} -- do not edit; change the profiles instead.",
            *sorted(set(notes)),
            "",
            "[agent]",
            *_kv(
                "  ",
                {
                    "interval": "30s",
                    "round_interval": True,
                    "flush_interval": "10s",
                    "metric_batch_size": 1000,
                    "metric_buffer_limit": 10000,
                    "omit_hostname": True,
                    # Agent-wide, not per input: Telegraf 1.40 refuses
                    # `translator` inside [[inputs.snmp]] and exits. gosmi
                    # needs no net-snmp tools in the image, and every OID
                    # rendered here is numeric, so no MIB files either.
                    "snmp_translator": "gosmi",
                    # Set explicitly: the default flips in 1.40, and Telegraf
                    # warns on every start until it is stated.
                    "skip_processors_after_aggregators": True,
                },
            ),
            "",
            "[[outputs.prometheus_client]]",
            *_kv("  ", {"listen": PROMETHEUS_LISTEN, "metric_version": 2, "expiration_interval": "180s"}),
        ]
        if any(w.device.kind in GNMI_KINDS and "bgp-neighbor-state" in w.measurements for w in watches):
            # OpenConfig reports a session's state as a STRING, and Prometheus
            # keeps numbers only, so without this the one field "intended but
            # down" is computed from would be dropped on the way out.
            lines += [
                "",
                "[[processors.enum]]",
                *_kv("  ", {"namepass": ["bgp_neighbor"]}),
                "  [[processors.enum.mapping]]",
                *_kv("    ", {"fields": ["session_state"], "dest": "session_state_code"}),
                "    [processors.enum.mapping.value_mappings]",
                *_kv("      ", BGP_STATE_CODES),
            ]
        if any(w.device.kind in GNMI_KINDS and "interface-counters" in w.measurements for w in watches):
            lines += [
                "",
                "[[processors.enum]]",
                *_kv("  ", {"namepass": ["interface_status"]}),
                "  [[processors.enum.mapping]]",
                *_kv("    ", {"fields": ["oper_status"], "dest": "oper_status_code"}),
                "    [processors.enum.mapping.value_mappings]",
                *_kv("      ", OPER_STATUS_CODES),
            ]
        lines += self._identity_processors(watches)
        rendered_inputs = 0
        for watch in watches:
            block = self._input_block(collector, watch)
            if block:
                lines += ["", *block]
                rendered_inputs += 1
        # Services (cycle 035): the lifecycle scrape, then one probe per port.
        service_blocks = lifecycle_input(collector, scrape or LifecycleScrape())
        for service_watch in service_watches or []:
            service_blocks += probe_inputs(collector, service_watch, (probes or {}).get(service_watch.name, []))
        for block in service_blocks:
            lines += [
                "",
                block["comment"],
                f"[[{block['table']}]]",
                *_kv("  ", block["items"]),
                f"  [{block['table']}.tags]",
                *_kv("    ", dict(sorted(block["tags"].items()))),
            ]
            rendered_inputs += 1
        if rendered_inputs == 0:
            msg = f"collector {collector!r}: the profiles select no device that can be collected from"
            raise TelemetryCollectorConfigError(msg)

        lines += [
            "",
            "# What Infrahub intends, read back so dashboards can compare it with what is observed.",
            "[[inputs.file]]",
            *_kv(
                "  ",
                {
                    "files": [INTENDED_FILE],
                    "data_format": "prometheus",
                    "prometheus_metric_version": 2,
                    "interval": "60s",
                },
            ),
            "  [inputs.file.tags]",
            *_kv("    ", {"collector": collector}),
        ]
        conf = "\n".join(lines) + "\n"
        try:
            tomllib.loads(conf)
        except tomllib.TOMLDecodeError as exc:  # pragma: no cover - a renderer bug, not intent
            msg = f"collector {collector!r}: rendered configuration is not valid TOML: {exc}"
            raise TelemetryCollectorConfigError(msg) from exc
        return conf

    @staticmethod
    def _identity_processors(watches: list[Watch]) -> list[str]:
        """Give node-exporter series their Infrahub device name back.

        node-exporter labels its own series `device` -- the interface,
        `eth0`, `eth1` -- and Telegraf never overwrites a label a metric
        already carries with an input's `tags`. So every node's series arrived
        with the interface name where the node's name belongs, measured as 29
        "devices" from three nodes. Per node, the incoming label is moved to
        `interface` and `device` is then set to the name Infrahub has, matched
        on the scrape URL that identifies the node. `order` matters: the
        rename must run before the override.
        """
        lines: list[str] = []
        for watch in watches:
            if watch.device.kind != SERVER:
                continue
            url = f"http://{watch.device.address}:{NODE_EXPORTER_PORT}/metrics"
            lines += [
                "",
                f"# {watch.device.name}: node-exporter's own `device` label is the interface",
                "[[processors.rename]]",
                *_kv("  ", {"order": 1, "namepass": ["prometheus"]}),
                "  [processors.rename.tagpass]",
                *_kv("    ", {"url": [url]}),
                "  [[processors.rename.replace]]",
                *_kv("    ", {"tag": "device", "dest": "interface"}),
                "[[processors.override]]",
                *_kv("  ", {"order": 2, "namepass": ["prometheus"]}),
                "  [processors.override.tagpass]",
                *_kv("    ", {"url": [url]}),
                "  [processors.override.tags]",
                *_kv("    ", {"device": watch.device.name}),
            ]
        return lines

    @staticmethod
    def _tags(collector: str, watch: Watch, table: str) -> list[str]:
        device = watch.device
        tags: dict[str, Any] = {
            "collector": collector,
            "device": device.name,
            "kind": device.kind,
            "profile": ",".join(sorted(watch.profiles)),
            "role": device.role,
        }
        if device.pod:
            tags["pod"] = device.pod
        if device.rack:
            tags["rack"] = device.rack
        return [f"  [{table}.tags]", *_kv("    ", dict(sorted(tags.items())))]

    def _input_block(self, collector: str, watch: Watch) -> list[str]:
        device = watch.device
        measurements = sorted(watch.measurements)
        interval = f"{watch.interval}s"
        # Deduplicated in first-seen order: two measurements may share a
        # subscription (evpn-routes and bgp-neighbor-state on a leaf), and
        # subscribing twice would report every series twice.
        specs: list[Any] = []
        for spec in (s for m in measurements for s in DISPATCH[m][device.kind]):
            if spec not in specs:
                specs.append(spec)

        if device.kind in GNMI_KINDS:
            if device.kind == SWITCH:
                target: dict[str, Any] = {
                    "addresses": [f"{device.address}:{GNMI_PORT}"],
                    "username": "${GNMI_USERNAME}",
                    "password": "${GNMI_PASSWORD}",
                }
            else:
                target = {
                    "addresses": [f"{device.address}:{SRL_GNMI_PORT}"],
                    "username": "${GNMI_USERNAME}",
                    "password": "${GNMI_PASSWORD}",
                    "tls_enable": True,
                    "insecure_skip_verify": True,
                }
            block = [
                f"# {device.name}: {', '.join(measurements)}",
                "[[inputs.gnmi]]",
                *_kv(
                    "  ",
                    {
                        **target,
                        "redial": "10s",
                        "path_guessing_strategy": "subscription",
                    },
                ),
                *self._tags(collector, watch, "inputs.gnmi"),
            ]
            for sub_name, origin, path in specs:
                block += [
                    "  [[inputs.gnmi.subscription]]",
                    *_kv(
                        "    ",
                        {
                            "name": sub_name,
                            "origin": origin,
                            "path": path,
                            "subscription_mode": "sample",
                            "sample_interval": interval,
                        },
                    ),
                ]
            return block

        if device.kind == FIREWALL:
            if not device.snmp_community:
                return [f"# skipped: {device.name} has no SNMP community modelled"]
            block = [
                f"# {device.name}: {', '.join(measurements)}",
                "[[inputs.snmp]]",
                *_kv(
                    "  ",
                    {
                        "agents": [f"udp://{device.address}:{SNMP_PORT}"],
                        "version": 2,
                        "community": device.snmp_community,
                        "interval": interval,
                        # Patient, because the vSRX's agent is slow now and
                        # then: the same walk takes 0.8s from the host and
                        # occasionally timed out at 5s with one retry.
                        "timeout": "10s",
                        "retries": 2,
                        # The tag naming the agent; "source" is the value every
                        # plugin now uses, and the old default makes Telegraf
                        # log a deprecation warning on each start.
                        "agent_host_tag": "source",
                    },
                ),
                *self._tags(collector, watch, "inputs.snmp"),
            ]
            for table_name, fields in specs:
                block += ["  [[inputs.snmp.table]]", *_kv("    ", {"name": table_name})]
                for field_name, oid, is_tag in fields:
                    entry: dict[str, Any] = {"name": field_name, "oid": oid}
                    if is_tag:
                        entry["is_tag"] = True
                    block += ["    [[inputs.snmp.table.field]]", *_kv("      ", entry)]
            return block

        port = NODE_EXPORTER_PORT
        return [
            f"# {device.name}: {', '.join(measurements)}",
            "[[inputs.prometheus]]",
            *_kv(
                "  ",
                {
                    "urls": [f"http://{device.address}:{port}/metrics"],
                    "metric_version": 2,
                    "interval": interval,
                    "fieldinclude": sorted(set(specs)),
                },
            ),
            *self._tags(collector, watch, "inputs.prometheus"),
        ]

    # -- intended.prom -----------------------------------------------------

    async def _intended(
        self,
        watches: list[Watch],
        parsed: TelemetryCollectorConfigQuery,
        service_watches: list[ServiceWatch] | None = None,
        probes: dict[str, list[tuple[str, int]]] | None = None,
        notes: list[str] | None = None,
    ) -> str:
        bgp = sorted({(w.device.name, w.device.kind) for w in watches if "bgp-neighbor-state" in w.measurements})
        links = {w.device.name for w in watches if "interface-counters" in w.measurements}
        devices = {w.device.name: w.device for w in watches}
        # Downloaded once per device: the service checks join to the same
        # sessions, and only to sessions the collector observes.
        neighbors = {name: await self._intended_neighbors(devices[name]) for name, _kind in bgp}

        lines = [
            "# TYPE otternet_intended_bgp_neighbor gauge",
            "# HELP otternet_intended_bgp_neighbor A BGP session Infrahub intends this device to hold.",
        ]
        for name, kind in bgp:
            for vrf, peer, description in neighbors[name]:
                # `kind` so a dashboard scopes intent the way it scopes what is
                # observed, without joining on a device that may be silent.
                labels = {"device": name, "kind": kind, "peer_address": peer}
                # A router's neighbours carry no network instance in the model,
                # so its sessions name no VRF rather than claiming `default`
                # for a session that lives in a customer's.
                if vrf:
                    labels["vrf"] = vrf
                peer_device = description.split("_", 1)[0] if description else ""
                if peer_device in devices:
                    labels["peer_device"] = peer_device
                lines.append(_series("otternet_intended_bgp_neighbor", labels, 1))

        link_lines: list[str] = []
        up_lines: list[str] = []
        for link in parsed.network_link.edges:
            ends = [
                e.node
                for e in ((link.node.connected_endpoints.edges or []) if link.node else [])
                if e.node is not None and getattr(e.node, "typename__", None) is not None
            ]
            named = [
                (str(_val(_peer(e, "device"), "name")), str(_val(e, "name")), _val(e, "status"))
                for e in ends
                if _peer(e, "device") is not None and _val(e, "name")
            ]
            if len(named) != 2:
                continue
            for (dev, intf, status), (peer_dev, peer_intf, _peer_status) in (named, named[::-1]):
                if dev not in links:
                    continue
                link_lines.append(
                    _series(
                        "otternet_intended_link",
                        {
                            "device": dev,
                            "interface": intf,
                            "kind": devices[dev].kind,
                            "peer_device": peer_dev,
                            "peer_interface": peer_intf,
                        },
                        1,
                    )
                )
                up_lines.append(
                    _series(
                        "otternet_intended_interface_up",
                        {"device": dev, "interface": intf, "kind": devices[dev].kind},
                        1 if status in (None, "active") else 0,
                    )
                )
        lines += [
            "# TYPE otternet_intended_link gauge",
            "# HELP otternet_intended_link A cable Infrahub records between two interfaces.",
            *sorted(set(link_lines)),
            "# TYPE otternet_intended_interface_up gauge",
            "# HELP otternet_intended_interface_up 1 when Infrahub intends the cabled interface to be up.",
            *sorted(set(up_lines)),
        ]
        if service_watches:
            context = Context(
                neighbors={name: [(vrf, peer) for vrf, peer, _ in found] for name, found in neighbors.items()},
                device_kinds={name: device.kind for name, device in devices.items()},
                site_sessions=_site_sessions(parsed),
                cabled_to=_cabled_to(parsed),
            )
            lines += intended_lines(service_watches, context, probes or {}, notes if notes is not None else [])
        return "\n".join(lines) + "\n"

    async def _intended_neighbors(self, device: Device) -> list[tuple[str, str, str]]:
        """(vrf, peer address, description) for every session the device is configured with."""
        if device.kind == ROUTER:
            return [("", peer, "") for peer in device.bgp_neighbors]
        if device.kind != SWITCH or not device.structured_config_id:
            return []
        sc_file = await self.client.get(AvdStructuredConfigFile, id=device.structured_config_id)
        content = await sc_file.download_file()
        structured = json.loads(content)
        router_bgp = structured.get("router_bgp") or {}
        found: list[tuple[str, str, str]] = [
            ("default", str(n["ip_address"]), str(n.get("description") or ""))
            for n in router_bgp.get("neighbors") or []
            if n.get("ip_address")
        ]
        found.extend(
            (str(vrf.get("name")), str(n["ip_address"]), str(n.get("description") or ""))
            for vrf in router_bgp.get("vrfs") or []
            for n in vrf.get("neighbors") or []
            if n.get("ip_address")
        )
        return sorted(set(found))


_series = series


def _site_sessions(parsed: TelemetryCollectorConfigQuery) -> dict[str, list[tuple[str, str]]]:
    """Circuit id -> (device, peer address) for each session the WAN site over it records."""
    found: dict[str, list[tuple[str, str]]] = {}
    for edge in parsed.wan_site.edges:
        site = edge.node
        circuit = _peer(site, "circuit") if site is not None else None
        if circuit is None:
            continue
        for session in (e.node for e in site.bgp_sessions.edges if e.node is not None):
            device = _val(_peer(session, "device"), "name")
            if device and _val(session, "peer_address"):
                found.setdefault(circuit.id, []).append((str(device), str(_val(session, "peer_address"))))
    return found


def _cabled_to(parsed: TelemetryCollectorConfigQuery) -> dict[str, list[tuple[str, str, str]]]:
    """Device name -> (switch, switch kind, switch port) at the far end of each of its cables."""
    found: dict[str, list[tuple[str, str, str]]] = {}
    for link in parsed.network_link.edges:
        ends = [
            (_peer(e.node, "device"), _val(e.node, "name"))
            for e in ((link.node.connected_endpoints.edges or []) if link.node else [])
            if e.node is not None and getattr(e.node, "typename__", None) is not None
        ]
        ends = [(device, port) for device, port in ends if device is not None and port]
        if len(ends) != 2:
            continue
        for (near, _), (far, far_port) in (ends, ends[::-1]):
            if getattr(far, "typename__", None) == SWITCH:
                found.setdefault(str(_val(near, "name")), []).append((str(_val(far, "name")), SWITCH, str(far_port)))
    return found


class _BlockDumper(yaml.SafeDumper):
    """Multi-line strings as literal blocks, so the artifact diff reads line by line."""


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    if "\n" in value:
        return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", value)


_BlockDumper.add_representer(str, _represent_str)


def _dump(manifest: dict[str, Any]) -> str:
    return yaml.dump(manifest, Dumper=_BlockDumper, sort_keys=False, default_flow_style=False, width=4096)

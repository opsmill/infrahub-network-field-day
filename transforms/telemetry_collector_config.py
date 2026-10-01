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
Secret ``invoke cluster`` creates.
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

SWITCH = "DcimFabricSwitch"
ROUTER = "DcimDevice"
FIREWALL = "SecurityFirewall"
SERVER = "ComputePhysicalServer"
KINDS = (SWITCH, ROUTER, FIREWALL, SERVER)

GNMI_PORT = 6030
FRR_EXPORTER_PORT = 9342
NODE_EXPORTER_PORT = 9100
SNMP_PORT = 161
PROMETHEUS_LISTEN = ":9273"

# RFC 4271's finite-state machine, in order, so ESTABLISHED is the one value a
# dashboard compares against.
BGP_STATE_CODES = {"IDLE": 1, "CONNECT": 2, "ACTIVE": 3, "OPENSENT": 4, "OPENCONFIRM": 5, "ESTABLISHED": 6}
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

DISPATCH: dict[str, dict[str, Any]] = {
    "interface-counters": {
        SWITCH: [("interface_counters", "openconfig", "/interfaces/interface/state/counters")],
        FIREWALL: [_IF_TABLE],
    },
    "bgp-neighbor-state": {
        SWITCH: [
            (
                "bgp_neighbor",
                "openconfig",
                "/network-instances/network-instance/protocols/protocol/bgp/neighbors/neighbor/state",
            )
        ],
        ROUTER: ["frr_bgp_peer_*"],
    },
    # The OpenConfig per-AFI prefix counts rather than an EOS-native Sysdb path:
    # stable across EOS releases, and the leaves' l2vpn-evpn neighbours report
    # exactly the EVPN routes received.
    "evpn-routes": {
        SWITCH: [
            (
                "bgp_afi_safi",
                "openconfig",
                "/network-instances/network-instance/protocols/protocol/bgp/neighbors/neighbor/afi-safis/afi-safi/state/prefixes",
            )
        ],
    },
    "system-resources": {
        SWITCH: [
            ("cpu", "openconfig", "/components/component/cpu/utilization/state"),
            ("memory", "openconfig", "/components/component/state/memory"),
        ],
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
        conf = self._render_conf(name, watches, notes)
        intended = await self._intended(watches, parsed)

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
            interval = int(_val(profile, "interval_seconds") or 30)
            role = _val(profile, "device_role")
            measurements = sorted(str(_val(m.node, "name")) for m in profile.measurements.edges if m.node)
            unknown = [m for m in measurements if m not in DISPATCH]
            if unknown:
                msg = f"profile {pname!r} names measurements no renderer knows: {unknown}"
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

    # -- telegraf.conf -----------------------------------------------------

    def _render_conf(self, collector: str, watches: list[Watch], notes: list[str]) -> str:
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
        if any(w.device.kind == SWITCH and "bgp-neighbor-state" in w.measurements for w in watches):
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
        rendered_inputs = 0
        for watch in watches:
            block = self._input_block(collector, watch)
            if block:
                lines += ["", *block]
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
        specs = [spec for m in measurements for spec in DISPATCH[m][device.kind]]

        if device.kind == SWITCH:
            block = [
                f"# {device.name}: {', '.join(measurements)}",
                "[[inputs.gnmi]]",
                *_kv(
                    "  ",
                    {
                        "addresses": [f"{device.address}:{GNMI_PORT}"],
                        "username": "${GNMI_USERNAME}",
                        "password": "${GNMI_PASSWORD}",
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
                        "timeout": "5s",
                        "retries": 1,
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

        port = FRR_EXPORTER_PORT if device.kind == ROUTER else NODE_EXPORTER_PORT
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

    async def _intended(self, watches: list[Watch], parsed: TelemetryCollectorConfigQuery) -> str:
        bgp = sorted({(w.device.name, w.device.kind) for w in watches if "bgp-neighbor-state" in w.measurements})
        links = {w.device.name for w in watches if "interface-counters" in w.measurements}
        devices = {w.device.name: w.device for w in watches}

        lines = [
            "# TYPE otternet_intended_bgp_neighbor gauge",
            "# HELP otternet_intended_bgp_neighbor A BGP session Infrahub intends this device to hold.",
        ]
        for name, _kind in bgp:
            for vrf, peer, description in await self._intended_neighbors(devices[name]):
                labels = {"device": name, "peer_address": peer, "vrf": vrf}
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
                        {"device": dev, "interface": intf, "peer_device": peer_dev, "peer_interface": peer_intf},
                        1,
                    )
                )
                up_lines.append(
                    _series(
                        "otternet_intended_interface_up",
                        {"device": dev, "interface": intf},
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
        return "\n".join(lines) + "\n"

    async def _intended_neighbors(self, device: Device) -> list[tuple[str, str, str]]:
        """(vrf, peer address, description) for every session the device is configured with."""
        if device.kind == ROUTER:
            return [("default", peer, "") for peer in device.bgp_neighbors]
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


def _series(metric: str, labels: dict[str, str], value: int) -> str:
    rendered = ",".join(f'{key}="{_escape(labels[key])}"' for key in sorted(labels))
    return f"{metric}{{{rendered}}} {value}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class _BlockDumper(yaml.SafeDumper):
    """Multi-line strings as literal blocks, so the artifact diff reads line by line."""


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    if "\n" in value:
        return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", value)


_BlockDumper.add_representer(str, _represent_str)


def _dump(manifest: dict[str, Any]) -> str:
    return yaml.dump(manifest, Dumper=_BlockDumper, sort_keys=False, default_flow_style=False, width=4096)

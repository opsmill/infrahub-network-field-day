"""DNS Zone Configuration transform (specs/037-lab-dns-service).

Renders the lab resolver's whole configuration -- its Corefile and its zone file
-- as ONE Kubernetes ConfigMap that Vidra delivers into the resolver's
namespace. Every name the resolver answers came from Infrahub: an address that
carries an ``fqdn`` inside the zone, written by ``generate-dns-record`` for each
exposed, live application.

**The zone file is derived, never typed.** A name appears when its application's
change merges and goes when the application is withdrawn, and the proposed
change shows the record in the artifact difference before either happens.

Three things this refuses rather than renders:

* **An empty zone.** An artifact with no records would replace a working
  ConfigMap and remove every name at once, the way an empty SR Linux artifact
  erases a device. Raising leaves the artifact in error and the running
  resolver on its last good zone.
* **Two addresses for one name.** The zone would answer both, and which one a
  client reached would depend on the order it asked in. Round-robin is not
  what was asked for.
* **A resolver with no name of its own.** The NS record has to point at a name
  that resolves, so a zone whose resolver has no record is refused.

A record whose application is withdrawn, or not exposed, is skipped and said so
in a comment line, never dropped silently.

The SOA serial is a hash of the records, not a counter and not a clock: a render
with nothing changed is byte-identical, so it produces no artifact difference,
and CoreDNS's ``file`` plugin reloads a zone when the serial differs.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass
from itertools import starmap
from typing import Any

import yaml
from infrahub_sdk.transforms import InfrahubTransform

from .dns_zone_config_query import DnsZoneConfigQuery

CONFIG_MAP_NAME = "lab-dns"
ZONE_TTL = 30
# Applications in these states have no name.
WITHDRAWN_STATUSES = frozenset({"decommissioning", "decommissioned"})
_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


class DnsZoneConfigError(ValueError):
    """The records cannot be rendered into a zone the resolver would serve."""


@dataclass(frozen=True)
class Record:
    """One A record: a label inside the zone and the address it answers with."""

    label: str
    address: str


def host_address(address: str) -> str:
    """``10.112.240.16/32`` -> ``10.112.240.16``."""
    return str(ipaddress.ip_interface(address).ip)


def select_records(
    zone: str,
    named: list[tuple[str, str]],
    apps: dict[str, tuple[str | None, bool]],
) -> tuple[list[Record], list[str]]:
    """Choose the records for ``zone`` and the comment lines for what was skipped.

    ``named`` is every (fqdn, address) Infrahub holds; ``apps`` maps an
    application name to (status, exposed). A name outside the zone is not this
    resolver's. A name whose application is withdrawn or unexposed is skipped
    and said so.
    """
    suffix = f".{zone}"
    notes: list[str] = []
    chosen: dict[str, str] = {}
    for fqdn, address in sorted(named):
        if not fqdn.endswith(suffix):
            continue
        label = fqdn[: -len(suffix)]
        if not _LABEL.match(label):
            notes.append(f"; skipped {fqdn}: {label!r} is not a valid DNS label")
            continue
        app = apps.get(label)
        if app is not None:
            status, exposed = app
            if status in WITHDRAWN_STATUSES:
                notes.append(f"; skipped {fqdn}: application {label} is {status}")
                continue
            if not exposed:
                notes.append(f"; skipped {fqdn}: application {label} is not exposed")
                continue
        host = host_address(address)
        if label in chosen and chosen[label] != host:
            msg = f"{fqdn} has two addresses ({chosen[label]} and {host}); a name must have exactly one"
            raise DnsZoneConfigError(msg)
        chosen[label] = host
    return list(starmap(Record, sorted(chosen.items()))), notes


def serial_for(records: list[Record]) -> int:
    """A serial that changes when, and only when, the records change."""
    digest = hashlib.sha256("\n".join(f"{r.label} {r.address}" for r in records).encode()).hexdigest()
    return int(digest[:8], 16) or 1


def render_zone(zone: str, resolver: str, records: list[Record], notes: list[str]) -> str:
    """The zone file. ``resolver`` is the label of the resolver's own record."""
    if not records:
        msg = (
            f"no application has a name in {zone}; an empty zone would remove every name the resolver "
            "answers, so the last good zone stays in the cluster"
        )
        raise DnsZoneConfigError(msg)
    if resolver not in {r.label for r in records}:
        msg = (
            f"the resolver {resolver!r} has no name in {zone}, so the NS record would point at nothing; "
            "run generate-dns-record for it or seed its address with an fqdn"
        )
        raise DnsZoneConfigError(msg)
    lines = [
        f"$ORIGIN {zone}.",
        f"$TTL {ZONE_TTL}",
        f"@ IN SOA {resolver}.{zone}. hostmaster.{zone}. {serial_for(records)} 3600 600 86400 {ZONE_TTL}",
        f"@ IN NS {resolver}.{zone}.",
    ]
    lines.extend(notes)
    lines.extend(f"{record.label} IN A {record.address}" for record in records)
    return "\n".join(lines) + "\n"


def render_corefile(zone: str) -> str:
    """The Corefile: this zone from the file, and a refusal for every other name.

    REFUSED rather than NXDOMAIN or a forward, so a client that lists this
    resolver beside its usual one moves on to the usual one for a name outside
    the zone (glibc treats REFUSED as a reason to try the next server; it treats
    NXDOMAIN as the final answer).
    """
    return (
        f"{zone}:53 {{\n"
        f"    file /etc/coredns/{zone}.db {{\n"
        "        reload 10s\n"
        "    }\n"
        "    errors\n"
        "    health {\n"
        "        lameduck 5s\n"
        "    }\n"
        "    ready\n"
        "    prometheus 0.0.0.0:9153\n"
        "}\n"
        ".:53 {\n"
        "    errors\n"
        "    template ANY ANY {\n"
        "        rcode REFUSED\n"
        "    }\n"
        "}\n"
    )


class _Dumper(yaml.SafeDumper):
    """Block style for the multi-line files, so the artifact diff reads as the zone does."""


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _represent_str)


def _val(node: Any, name: str) -> Any:
    attr = getattr(node, name, None)
    return getattr(attr, "value", None) if attr is not None else None


class DnsZoneConfig(InfrahubTransform):
    """Render the resolver's ConfigMap."""

    query = "dns_zone_config"

    async def transform(self, data: dict[str, Any]) -> str:
        """Render the ConfigMap, or raise naming what the zone is missing."""
        parsed = DnsZoneConfigQuery(**data)
        edges = parsed.target.edges
        resolver = edges[0].node if edges else None
        if resolver is None:
            msg = "no ServiceFabricApp matched the requested name"
            raise DnsZoneConfigError(msg)
        name = str(_val(resolver, "name"))
        zone = _val(resolver, "dns_zone")
        namespace = _val(resolver, "namespace_name")
        if not zone:
            msg = f"{name!r} has no dns_zone, so it is not a resolver"
            raise DnsZoneConfigError(msg)
        if not namespace:
            msg = f"{name!r} has no namespace_name; the ConfigMap would land in Vidra's default namespace"
            raise DnsZoneConfigError(msg)

        named = [
            (str(_val(edge.node, "fqdn")), str(_val(edge.node, "address")))
            for edge in parsed.records.edges
            if edge.node is not None and _val(edge.node, "fqdn")
        ]
        apps = {
            str(_val(edge.node, "name")): (_val(edge.node, "status"), bool(_val(edge.node, "exposed")))
            for edge in parsed.apps.edges
            if edge.node is not None
        }
        records, notes = select_records(str(zone), named, apps)
        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": CONFIG_MAP_NAME,
                "namespace": str(namespace),
                "labels": {"app.kubernetes.io/managed-by": "infrahub", "otternet.lab/resolver": name},
            },
            "data": {
                "Corefile": render_corefile(str(zone)),
                f"{zone}.db": render_zone(str(zone), name, records, notes),
            },
        }
        return yaml.dump(manifest, Dumper=_Dumper, sort_keys=False, width=4096)

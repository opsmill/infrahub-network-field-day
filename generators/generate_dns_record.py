"""Give an exposed application a DNS name (specs/037-lab-dns-service).

For every exposed, live ``ServiceFabricApp`` this puts ``<name>.<zone>`` on the
application's VIP address (``IpamIPAddress.fqdn``), and takes it off again when
the application is withdrawn. ``dns_zone_config`` renders those names into the
resolver's zone, and this generator asks for that artifact to be re-rendered,
because the artifact's target is the resolver and not the application: without
that the proposed change would show the new name in the data and not in the
configuration (the reason ``generate-monitoring-collector`` exists too).

FIVE THINGS THAT LOOK ARBITRARY AND ARE NOT.

* **The address is the FIRST address of the VIP block.** A Cilium
  ``CiliumLoadBalancerIPPool`` is created per application from its block, and
  the application's first LoadBalancer Service takes the first free address in
  it. Measured on the lab: otternet-demo's block 10.112.240.0/28 gave
  10.112.240.0, and otter-shop's 10.112.240.16/28 gave 10.112.240.16. An
  application that pins another address (``lbipam.cilium.io/ips``, as Grafana
  does) sets ``dns_address`` to it, inside the block, and the name follows that
  instead; the generator refuses an address outside the block. An application
  with several Services names one of them the same way.
* **A name that already has an address is never moved.** The first thing it
  looks for is any address holding this exact name; if one exists the run ends
  there. That is what makes it idempotent, and what lets a hand-seeded record
  win over the rule.
* **It creates an address only when none exists, and marks it.** The
  description starts with ``DNS name for``, and withdrawal deletes only an
  address carrying that mark. An address somebody else created -- one a firewall
  address-book entry points at -- loses its ``fqdn`` and is otherwise untouched.
* **Two runs can race, and the address is the same one.** The created event and
  the block's arrival both fire this generator within milliseconds, and each
  looked for the name before either had written it. Both created
  ``10.112.240.16/32``, and the branch could not merge: the unique
  (address, namespace) constraint holds at merge, not at write. So the create
  names the namespace, which lets the second upsert find the first by its
  human-friendly id, and every run ends by removing any duplicate holder of the
  name and keeping the lowest id. Every racing run applies the same rule, so they
  agree on the survivor.
* **No trigger rule may name a Deployment* or Monitoring* kind**, and this one
  names neither. It fires on an application's creation and on the fields that
  decide whether it has a name (status, exposed, vip_block).
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from infrahub_sdk.generator import InfrahubGenerator

from solution_arista_avd.protocols import IpamIPAddress

from .artifact_render import request_artifact_render
from .generate_dns_record_query import GenerateDnsRecordQuery

ZONE_ARTIFACT = "DNS Zone Configuration"
# The IPAM namespace every address in this lab lives in.
DEFAULT_NAMESPACE = "default"
# What marks an address this generator created, and so may delete.
CREATED_MARK = "DNS name for"
# The two statuses that mean "take it away", as in generate-fabric-app.
WITHDRAWN_STATUSES = frozenset({"decommissioning", "decommissioned"})
_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def _value(wrapper: Any) -> Any:
    return wrapper.value if wrapper is not None else None


def first_address(prefix: str) -> str:
    """``10.112.240.16/28`` -> ``10.112.240.16/32``."""
    return f"{ipaddress.ip_network(prefix, strict=False).network_address}/32"


def name_address(prefix: str, dns_address: str | None) -> str:
    """The address a name points at: ``dns_address`` when set, else the first of the block.

    An address outside the block is refused, because the firewall rule, the
    pod policy and the Service all follow the block and a name outside it
    resolves to somewhere nothing answers.
    """
    if not dns_address:
        return first_address(prefix)
    address = ipaddress.ip_address(dns_address)
    if address not in ipaddress.ip_network(prefix, strict=False):
        msg = f"dns_address {dns_address} is outside the VIP block {prefix}"
        raise ValueError(msg)
    return f"{address}/32"


def has_name(*, status: str | None, exposed: bool, prefix: str | None, label: str) -> bool:
    """Whether an application should have a name: live, exposed, with a block and a valid label."""
    return bool(exposed and prefix and status not in WITHDRAWN_STATUSES and _LABEL.match(label))


class DnsRecordGenerator(InfrahubGenerator):
    """Set or clear one application's name, then ask for the zone to be re-rendered."""

    async def generate(self, data: dict[str, Any]) -> None:
        """Write the name; never touch anything but ``fqdn`` and an address this created."""
        parsed = GenerateDnsRecordQuery(**data)
        app = parsed.target.edges[0].node if parsed.target.edges else None
        if app is None:
            msg = "no ServiceFabricApp matched the requested name"
            raise ValueError(msg)
        resolvers = [edge.node for edge in parsed.resolver.edges if edge.node is not None]
        if not resolvers:
            self.logger.info("No application has a dns_zone, so there is no resolver and nothing to name")
            return
        if len(resolvers) > 1:
            names = ", ".join(sorted(str(_value(r.name)) for r in resolvers))
            msg = f"more than one application has a dns_zone ({names}); a lab has one resolver"
            raise ValueError(msg)
        resolver = resolvers[0]
        zone = str(_value(resolver.dns_zone))
        name = str(_value(app.name))
        fqdn = f"{name}.{zone}"
        block = app.vip_block.node if app.vip_block is not None else None
        prefix = _value(block.prefix) if block is not None else None

        if has_name(status=_value(app.status), exposed=bool(_value(app.exposed)), prefix=prefix, label=name):
            address = name_address(str(prefix), _value(app.dns_address))
            await self._ensure(fqdn, address, moves=bool(_value(app.dns_address)))
            await self._keep_one(fqdn)
        else:
            await self._withdraw(fqdn)
        await self._rerender(resolver.id, str(_value(resolver.name)))

    def _forget(self, node: IpamIPAddress) -> None:
        """Drop a deleted address from the generator group's members.

        The SDK adds every node this run saves or reads to the group, and writes
        the group last. A member that was deleted in between does not exist, so
        ``CoreGeneratorGroupUpsert`` fails with ``Unable to find the node`` and the
        whole run is marked failed, after the data was already written.
        """
        context = self.client.group_context
        context.related_node_ids[:] = [node_id for node_id in context.related_node_ids if node_id != node.id]

    async def _holders(self, fqdn: str) -> list[IpamIPAddress]:
        return list(await self.client.filters(IpamIPAddress, fqdn__value=fqdn))

    async def _ensure(self, fqdn: str, address: str, *, moves: bool = False) -> None:
        holders = await self._holders(fqdn)
        if holders and not moves:
            self.logger.info("%s already has an address; leaving it", fqdn)
            return
        if holders:
            if any(str(_value(node.address)) == address for node in holders):
                self.logger.info("%s already points at %s", fqdn, address)
                return
            # The application now names its address, and the name is elsewhere:
            # take it off the old one, which is deleted only if this created it.
            await self._withdraw(fqdn)
        existing = await self.client.filters(IpamIPAddress, address__value=address)
        if existing:
            node = existing[0]
            node.fqdn.value = fqdn
            await node.save(allow_upsert=True)
            self.logger.info("Named %s on the existing address %s", fqdn, address)
            return
        node = await self.client.create(
            IpamIPAddress,
            address=address,
            description=f"{CREATED_MARK} {fqdn.split('.', 1)[0]}",
            fqdn=fqdn,
            ip_namespace={"hfid": [DEFAULT_NAMESPACE]},
        )
        await node.save(allow_upsert=True)
        self.logger.info("Created %s with the name %s", address, fqdn)

    async def _keep_one(self, fqdn: str) -> None:
        """Remove every holder of ``fqdn`` this generator created except the lowest id.

        Only an address carrying the creation mark is ever deleted, so a hand-made
        or seeded holder is never touched. Racing runs sort the same way, so they
        agree on which one survives; one that finds its target already gone has
        nothing left to do.
        """
        holders = sorted(await self._holders(fqdn), key=lambda node: str(node.id))
        for extra in holders[1:]:
            if not str(_value(extra.description) or "").startswith(CREATED_MARK):
                continue
            try:
                await extra.delete()
            except Exception as exc:  # noqa: BLE001 - a racing run deleted it first
                self.logger.info("Duplicate %s was already gone (%s)", _value(extra.address), exc)
                self._forget(extra)
            else:
                self._forget(extra)
                self.logger.info("Removed the duplicate %s for %s", _value(extra.address), fqdn)

    async def _withdraw(self, fqdn: str) -> None:
        for node in await self._holders(fqdn):
            description = _value(node.description) or ""
            if str(description).startswith(CREATED_MARK):
                try:
                    await node.delete()
                except Exception as exc:  # noqa: BLE001 - still referenced: fall back to clearing the name
                    self.logger.warning("Could not delete %s (%s); clearing its name instead", node.address.value, exc)
                else:
                    self._forget(node)
                    self.logger.info("Removed the address %s created for %s", node.address.value, fqdn)
                    continue
            node.fqdn.value = None
            await node.save(allow_upsert=True)
            self.logger.info("Cleared %s from %s", fqdn, node.address.value)

    async def _rerender(self, resolver_id: str, resolver_name: str) -> None:
        """Ask for the zone artifact again, on this generator's branch. Best effort, like its sibling."""
        branch = self.branch_name
        try:
            await request_artifact_render(
                self._init_client,
                artifact_name=ZONE_ARTIFACT,
                target_id=resolver_id,
                branch=branch,
                first_render=True,
            )
        except Exception as exc:  # noqa: BLE001 - never fatal; the artifact check renders it anyway
            self.logger.warning("Could not re-render %r for %s (%s)", ZONE_ARTIFACT, resolver_name, exc)
            return
        self.logger.info("Requested a re-render of %r for %s on %s", ZONE_ARTIFACT, resolver_name, branch or "main")

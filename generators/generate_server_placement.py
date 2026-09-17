"""Put a machine in a rack and let the fabric cable it.

`2_Add_Server.py` in the portal created a `ComputePhysicalServer` straight in
the graph. This generator sits under the request instead, so a machine arrives
with a record of who asked for it, a status, and something to withdraw.

THREE THINGS THAT LOOK ARBITRARY AND ARE NOT.

* **The template is mandatory.** It is what gives the machine its interfaces,
  and `generate-server-cabling` cables interfaces. A server created without one
  has none, so that generator logs "has no interfaces" and returns -- a machine
  that exists, is in the right rack, and is connected to nothing, with no error
  anywhere.

* **The rack is mandatory for the same reason.** `generate-server-cabling`
  finds the leaf switches *in the server's rack*; a machine with no rack is
  cabled to nothing and reports success.

* **The machine joins the `servers` group, and that is what makes it real.**
  A generator targets a group, so a server outside it is created and then never
  cabled. This is the same trap the segment's group membership documents, and
  it is invisible in the logs either way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infrahub_sdk.generator import InfrahubGenerator

from .generate_server_placement_query import (
    GenerateServerPlacementQuery,
    GenerateServerPlacementQueryTargetEdgesNode,
)

PlacementNode = GenerateServerPlacementQueryTargetEdgesNode

# The group `generate-server-cabling` targets. Without membership the machine is
# created and never cabled, and nothing reports it.
SERVERS_GROUP = "servers"

WITHDRAWN_STATUSES = frozenset({"decommissioning", "decommissioned"})

# What a freshly placed machine is until something confirms it. `active` would
# claim the fabric had cabled it, which happens on a later generator run.
INITIAL_SERVER_STATUS = "provisioning"


def _value(wrapper: Any) -> Any:
    return wrapper.value if wrapper is not None else None


def _node_of(relationship: Any) -> Any:
    return relationship.node if relationship is not None else None


def _edges_of(relationship: Any) -> list[Any]:
    if relationship is None:
        return []
    return [edge.node for edge in relationship.edges if edge.node is not None]


def adopted_id(existing: list[Any], hostname: str, recorded_id: str | None) -> str | None:
    """The id of a machine this service already owns, refusing a collision.

    A request named `k8s-node1` must not quietly take ownership of the running
    Kubernetes node -- because decommissioning the request would then delete it.
    """
    matching = [node for node in existing if _value(node.name) == hostname]
    if not matching:
        return None
    if recorded_id in {node.id for node in matching}:
        return recorded_id
    msg = (
        f"a machine named {hostname!r} already exists and this service does not record it; "
        "choose another hostname, or point the request's `server` at it first to adopt it"
    )
    raise ValueError(msg)


@dataclass(frozen=True)
class PlacementContext:
    """A validated request, resolved before the first write."""

    placement: PlacementNode
    name: str
    hostname: str
    role: str
    rack_id: str
    rack_name: str | None
    template_id: str
    description: str | None
    adopted: str | None


def validate_model(parsed: GenerateServerPlacementQuery) -> PlacementContext:
    """Resolve and check everything before anything is written."""
    placement = parsed.target.edges[0].node if parsed.target.edges else None
    if placement is None:
        msg = "no ServiceServerPlacement matched the requested name"
        raise ValueError(msg)

    name = _value(placement.name)
    hostname = _value(placement.hostname)
    if not hostname:
        msg = f"placement {name!r} states no hostname"
        raise ValueError(msg)

    rack = _node_of(placement.rack)
    template = _node_of(placement.template)
    if rack is None:
        msg = (
            f"placement {name!r} names no rack; generate-server-cabling finds leaves in the "
            "server's rack, so the machine would be cabled to nothing"
        )
        raise ValueError(msg)
    if template is None:
        msg = (
            f"placement {name!r} names no object template; the machine would be created with no "
            "interfaces and generate-server-cabling would have nothing to cable"
        )
        raise ValueError(msg)

    recorded = _node_of(placement.server)
    return PlacementContext(
        placement=placement,
        name=name,
        hostname=hostname,
        role=_value(placement.server_role) or "compute",
        rack_id=rack.id,
        rack_name=_value(rack.name),
        template_id=template.id,
        description=_value(placement.description),
        adopted=adopted_id(
            _edges_of(parsed.compute_physical_server), hostname, None if recorded is None else recorded.id
        ),
    )


def is_withdrawn(placement: PlacementNode) -> bool:
    return _value(placement.status) in WITHDRAWN_STATUSES


class ServerPlacementGenerator(InfrahubGenerator):
    """Materialize a requested machine."""

    async def generate(self, data: dict) -> None:
        parsed = GenerateServerPlacementQuery(**data)

        placement = parsed.target.edges[0].node if parsed.target.edges else None
        if placement is None:
            msg = "no ServiceServerPlacement matched the requested name"
            raise ValueError(msg)

        if is_withdrawn(placement):
            await self._withdraw(placement)
            return

        try:
            context = validate_model(parsed)
        except ValueError:
            await self._set_status(placement.id, "error")
            raise

        server_id = await self._upsert_server(context)
        await self._record(context, server_id)
        await self._set_status(placement.id, "active")
        self.logger.info(
            "Machine %r is placed in %s; run the cabling generator to connect it to its leaves",
            context.hostname,
            context.rack_name or "its rack",
        )

    async def _upsert_server(self, context: PlacementContext) -> str:
        """The machine, written again every run so it stays tracked."""
        data: dict[str, Any] = {
            "name": context.hostname,
            "description": context.description or f"{context.hostname}, placed by {context.name}",
            "status": INITIAL_SERVER_STATUS,
            "role": context.role,
            "rack": context.rack_id,
            # The template is what supplies the interfaces. Passed on every run
            # rather than only at creation, because an upsert that omits it
            # would leave a re-created machine bare.
            "object_template": context.template_id,
            "member_of_groups": [SERVERS_GROUP],
        }
        if context.adopted is not None:
            data["id"] = context.adopted

        server = await self.client.create(kind="ComputePhysicalServer", data=data)
        await server.save(allow_upsert=True)
        return server.id

    async def _record(self, context: PlacementContext, server_id: str) -> None:
        service = await self.client.get(kind="ServiceServerPlacement", id=context.placement.id)
        service.server = server_id  # type: ignore[attr-defined]
        await service.save(update_group_context=False)

    async def _withdraw(self, placement: PlacementNode) -> None:
        """Remove the machine an earlier run created.

        The tracking context does not cover this: `update_group` returns early
        on an empty member set, so a run that writes nothing prunes nothing.

        Only what the service records is deleted. A machine that merely shares
        the hostname was refused at build time and is not this generator's to
        remove.
        """
        name = _value(placement.name)
        server = _node_of(placement.server)
        if server is None:
            self.logger.info("Placement %r built no machine; nothing to withdraw", name)
            await self._set_status(placement.id, "decommissioned")
            return

        service = await self.client.get(kind="ServiceServerPlacement", id=placement.id)
        service.server = None  # type: ignore[attr-defined]
        await service.save(update_group_context=False)

        # Deleting the machine takes its interfaces and its cabling with it,
        # which is the intended meaning of decommissioning a placement.
        await self.client.delete(kind="ComputePhysicalServer", id=server.id)
        await self._set_status(placement.id, "decommissioned")
        self.logger.info("Withdrew machine %r and its cabling", _value(server.name))

    async def _set_status(self, service_id: str, status: str) -> None:
        service = await self.client.get(kind="ServiceServerPlacement", id=service_id)
        if _value(service.status) == status:  # type: ignore[attr-defined]
            return
        service.status.value = status  # type: ignore[union-attr]
        await service.save(update_group_context=False)
        self.logger.info("Placement status set to %s", status)

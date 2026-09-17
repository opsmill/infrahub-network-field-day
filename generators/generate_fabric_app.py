"""Allocate an exposed application's LoadBalancer VIP block.

`ServiceFabricApp` is the one service kind whose renderer **raises** on an
incomplete request: `crossplane_fabric_app.py` fails with "application {name} is
exposed but has no vip_block; the XRD requires expose.vipBlock". So every exposed
application has had to have a block chosen by hand out of the cluster's VIP pool
-- `10.112.240.0/28` for `nfd41-demo`, written into
`objects/29_nfd41_offfabric_prefixes.yml` -- with nothing anywhere preventing the
next one from choosing the same addresses.

This generator makes stating a SIZE the request, and naming a block the
exception, which is the same inversion `generate-network-segment` performs for
subnets and VLAN ids.

FOUR THINGS THAT LOOK ARBITRARY AND ARE NOT.

* **`vip_block_managed` exists because one field holds two different things.**
  `vip_block` may be a block a human declared in `objects/` or a block this
  generator took from the pool, and only the second is ever safe to delete. The
  flag records which, it is set only on the allocating path, and withdrawal
  consults nothing else. It is the same guard `managed_by_service` provides on
  `SecurityPolicyRule`, for the same reason: a generator working next to
  hand-maintained data must be able to tell its own output apart.

* **The pool is found through the CLUSTER, not by name and not by role.** An
  application belongs to a cluster, and that cluster's `vip_pools` are the only
  supernets its LoadBalancer addresses may come from -- the leaves' inbound route
  policy permits exactly `10.112.240.0/24 le 32`, so a block from anywhere else
  is advertised by the cluster and refused by the fabric. Resolving by role would
  pick the wrong pool the moment a second cluster existed.

* **`exposed: false` withdraws rather than being ignored.** An unexposed
  application gets no pool, no VIP and no advertisement, which
  `schemas/service/kubernetes_services.yml` states on `exposed` itself. Leaving a
  block allocated to it would hold addresses out of the pool for an application
  that cannot receive traffic.

* **Allocation is keyed on the service's ID, never its name.** The identifier is
  what makes `allocate_next_ip_prefix` idempotent; keyed on a name, a rename
  would take a second block and orphan the first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infrahub_sdk.generator import InfrahubGenerator

from .generate_fabric_app_query import (
    GenerateFabricAppQuery,
    GenerateFabricAppQueryTargetEdgesNode,
)

AppNode = GenerateFabricAppQueryTargetEdgesNode

# The two statuses that mean "take it away". Everything else builds, `error`
# included, so a failed run that is corrected rebuilds rather than needing its
# status reset by hand.
WITHDRAWN_STATUSES = frozenset({"decommissioning", "decommissioned"})

# `IpamPrefix.role` is mandatory and describes what the prefix is for. The
# cluster's supernet already carries this value, and so does the hand-written
# block beneath it.
VIP_ROLE = "vip_pool"

# The artifact this service renders into, by its artifact_name in .infrahub.yml.
APP_ARTIFACT = "Crossplane FabricApp"


def _value(wrapper: Any) -> Any:
    """Unwrap an Infrahub ``{"value": ...}`` wrapper, tolerating absence."""
    return wrapper.value if wrapper is not None else None


def _node_of(relationship: Any) -> Any:
    """Unwrap a cardinality-one relationship, tolerating absence."""
    return relationship.node if relationship is not None else None


def _edges_of(relationship: Any) -> list[Any]:
    """Unwrap a cardinality-many relationship into its nodes, skipping nulls."""
    if relationship is None:
        return []
    return [edge.node for edge in relationship.edges if edge.node is not None]


def resolve_vip_pool(parsed: GenerateFabricAppQuery, app: AppNode) -> str:
    """The pool this application's VIP block comes from.

    The cluster's `vip_pools` name the supernets; the pool is whichever
    `CoreIPPrefixPool` draws from one of them. Exactly one candidate is required,
    because two pools over the same supernet would allocate against each other
    and the generator must not guess which was meant.
    """
    cluster = _node_of(app.cluster)
    if cluster is None:
        msg = f"application {_value(app.name)!r} names no cluster, so its VIP pool cannot be found"
        raise ValueError(msg)

    supernets = {node.id for node in _edges_of(cluster.vip_pools)}
    if not supernets:
        msg = (
            f"cluster {_value(cluster.name)!r} declares no vip_pools, so there is no supernet to "
            "allocate a VIP block from; add one to the cluster"
        )
        raise ValueError(msg)

    candidates = [
        node.id
        for node in _edges_of(parsed.core_ip_prefix_pool)
        if {resource.id for resource in _edges_of(node.resources)} & supernets
    ]
    if len(candidates) != 1:
        found = "none" if not candidates else str(len(candidates))
        msg = (
            f"expected exactly one CoreIPPrefixPool drawing from {_value(cluster.name)!r}'s vip_pools, "
            f"found {found}; the fabric's inbound route policy only permits those supernets"
        )
        raise ValueError(msg)
    return candidates[0]


def wants_a_block(app: AppNode) -> bool:
    """Whether this application should hold a VIP block at all.

    Two independent reasons not to, and both withdraw rather than skip: an
    unexposed application receives no traffic, and a decommissioned one is on its
    way out.
    """
    return bool(_value(app.exposed)) and _value(app.status) not in WITHDRAWN_STATUSES


@dataclass(frozen=True)
class AppContext:
    """A validated request, resolved before the first write."""

    app: AppNode
    name: str
    pool_id: str
    block_size: int
    recorded_block_id: str | None
    recorded_block_prefix: str | None
    block_is_managed: bool


def validate_model(parsed: GenerateFabricAppQuery) -> AppContext:
    """Resolve and check everything before anything is written."""
    app = parsed.target.edges[0].node if parsed.target.edges else None
    if app is None:
        msg = "no ServiceFabricApp matched the requested name"
        raise ValueError(msg)

    name = _value(app.name)
    if not name:
        msg = "the application has no name"
        raise ValueError(msg)

    size = _value(app.vip_block_size)
    if size is None:
        msg = f"application {name!r} states no vip_block_size, so nothing can be allocated for it"
        raise ValueError(msg)

    recorded = _node_of(app.vip_block)
    return AppContext(
        app=app,
        name=name,
        pool_id=resolve_vip_pool(parsed, app),
        block_size=int(size),
        recorded_block_id=None if recorded is None else recorded.id,
        recorded_block_prefix=None if recorded is None else _value(recorded.prefix),
        block_is_managed=bool(_value(app.vip_block_managed)),
    )


class FabricAppGenerator(InfrahubGenerator):
    """Give an exposed application a VIP block, or take one back."""

    async def generate(self, data: dict) -> None:
        """Allocate, adopt, or withdraw."""
        parsed = GenerateFabricAppQuery(**data)

        app = parsed.target.edges[0].node if parsed.target.edges else None
        if app is None:
            msg = "no ServiceFabricApp matched the requested name"
            raise ValueError(msg)

        if not wants_a_block(app):
            await self._withdraw(app)
            return

        # A block that already exists is kept, whoever put it there. This is the
        # seeded application's path: nfd41-demo names 10.112.240.0/28 and the
        # rendered Crossplane manifest must not move.
        if _node_of(app.vip_block) is not None:
            self.logger.info(
                "Application %r already holds %s; leaving it alone",
                _value(app.name),
                _value(_node_of(app.vip_block).prefix),
            )
            return

        context = validate_model(parsed)
        await self._allocate(context)

    async def _allocate(self, context: AppContext) -> None:
        """Take the next free block and record that it is ours.

        `vip_block_managed` is written in the SAME save as `vip_block`. Splitting
        them leaves a window in which the block exists and nothing records who
        owns it -- and a withdrawal landing in that window would decline to
        remove a block the generator had in fact allocated, leaking it.
        """
        pool = await self.client.get(kind="CoreIPPrefixPool", id=context.pool_id)
        prefix = await self.client.allocate_next_ip_prefix(
            resource_pool=pool,
            identifier=f"fabric-app-{context.app.id}",
            member_type="prefix",
            prefix_length=context.block_size,
            data={
                "role": VIP_ROLE,
                "description": f"VIP block for the {context.name} application",
            },
        )
        allocated = str(prefix.prefix.value)  # type: ignore[union-attr]

        service = await self.client.get(kind="ServiceFabricApp", id=context.app.id)
        service.vip_block = prefix.id  # type: ignore[attr-defined]
        service.vip_block_managed.value = True  # type: ignore[union-attr]
        await service.save(update_group_context=False)

        self.logger.info("Allocated %s to application %r", allocated, context.name)
        await self._rerender(context.app.id)

    async def _withdraw(self, app: AppNode) -> None:
        """Take back a block this generator allocated, and only that.

        THE TRACKING CONTEXT DOES NOT COVER THIS. `update_group` opens with
        ``if not members: return``, so a run that writes nothing prunes nothing
        -- an unexposed application would keep its block while the run reported
        success.

        `vip_block_managed` is the whole guard. A hand-written block is left
        exactly where it is: `nfd41-demo`'s `10.112.240.0/28` is declared in
        `objects/29_nfd41_offfabric_prefixes.yml`, and deleting it would remove
        an object the seed data owns and break the next `invoke load`.
        """
        name = _value(app.name)
        block = _node_of(app.vip_block)

        if block is None:
            self.logger.info("Application %r holds no VIP block; nothing to withdraw", name)
            return

        if not _value(app.vip_block_managed):
            self.logger.info(
                "Application %r holds %s, which this generator did not allocate; leaving it alone",
                name,
                _value(block.prefix),
            )
            return

        # The reference goes first. Deleting the prefix while the service still
        # points at it leaves a dangling relationship for as long as the second
        # write takes, and a failure in between would leave one permanently.
        service = await self.client.get(kind="ServiceFabricApp", id=app.id)
        service.vip_block = None  # type: ignore[attr-defined]
        service.vip_block_managed.value = False  # type: ignore[union-attr]
        await service.save(update_group_context=False)

        await self.client.delete(kind="IpamPrefix", id=block.id)
        self.logger.info("Withdrew %s from application %r and returned it to the pool", _value(block.prefix), name)
        await self._rerender(app.id)

    async def _rerender(self, app_id: str) -> None:
        """Ask for the Crossplane manifest to be re-rendered.

        Best effort, and deliberately so: the allocation is already written and
        correct by this point, and raising here would skip the tracking
        context's `update_group`. A failed request is recoverable by
        regenerating the artifact, so it is logged loudly rather than thrown.

        Unlike `generate-app-access`, the changed object here IS the artifact's
        target, so Infrahub regenerates on its own. This is belt and braces
        against that assumption, which cost cycle 033 a day when it turned out
        not to hold for the firewall.
        """
        try:
            service = await self._init_client.get(kind="ServiceFabricApp", id=app_id)
            await service.artifact_generate(APP_ARTIFACT)
        except Exception as exc:  # noqa: BLE001 - see the docstring; never fatal here
            self.logger.warning(
                "Could not re-render %r (%s); the allocation is correct, regenerate the artifact",
                APP_ARTIFACT,
                exc,
            )
            return
        self.logger.info("Requested a re-render of %r", APP_ARTIFACT)

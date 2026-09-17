"""Put a tenant onto a fabric.

`3_Create_Tenant.py` in the portal wrote an `EvpnTenant` straight into the
graph. This generator sits under the request instead, so there is a record of
who asked, a status, and something to withdraw.

THE VNI BASE IS DERIVED, NOT POOLED, AND THAT IS THE WHOLE DESIGN DECISION.
Every tenant's L2VLAN VNIs are allocated upward from its base, so two tenants
whose bases are close share VNIs. This lab spaces them a thousand apart --
11000, 12000, 13000, 15000 -- and a `CoreNumberPool` hands out CONSECUTIVE
integers, so pooling `mac_vrf_vni_base` would produce 16000 and 16001 for two
tenants and silently overlap their entire VNI ranges. Nothing would error; the
fabric would simply bridge two tenants together.

So the next base is the lowest free multiple of `VNI_SPACING` above every base
in use. `14000` in this lab is free and is what a new tenant gets, which is also
the evidence that the derivation fills gaps rather than only appending.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infrahub_sdk.generator import InfrahubGenerator

from .generate_tenant_onboarding_query import (
    GenerateTenantOnboardingQuery,
    GenerateTenantOnboardingQueryTargetEdgesNode,
)

OnboardingNode = GenerateTenantOnboardingQueryTargetEdgesNode

# The gap between one tenant's base and the next. Matches the lab's own
# numbering, and is the number that keeps two tenants' VNI ranges apart.
VNI_SPACING = 1000

# Where derivation starts when no tenant exists at all.
VNI_FLOOR = 11000

WITHDRAWN_STATUSES = frozenset({"decommissioning", "decommissioned"})


def _value(wrapper: Any) -> Any:
    return wrapper.value if wrapper is not None else None


def _node_of(relationship: Any) -> Any:
    return relationship.node if relationship is not None else None


def _edges_of(relationship: Any) -> list[Any]:
    if relationship is None:
        return []
    return [edge.node for edge in relationship.edges if edge.node is not None]


def next_vni_base(taken: set[int]) -> int:
    """The lowest free multiple of ``VNI_SPACING`` at or above ``VNI_FLOOR``.

    Fills gaps rather than only appending, so a decommissioned tenant's range
    becomes available again instead of the numbering drifting upward forever.
    """
    candidate = VNI_FLOOR
    while candidate in taken:
        candidate += VNI_SPACING
    return candidate


def taken_bases(parsed: GenerateTenantOnboardingQuery) -> set[int]:
    """Every VNI base already in use, ignoring tenants that carry none."""
    bases: set[int] = set()
    for tenant in _edges_of(parsed.evpn_tenant):
        base = _value(tenant.mac_vrf_vni_base)
        if base is not None:
            bases.add(int(base))
    return bases


def adopted_id(existing: list[Any], wanted_name: str, recorded_id: str | None) -> str | None:
    """The id of an EVPN tenant this service already owns, refusing a collision.

    Same rule as `generate-network-segment`: our own earlier output is written
    again every run so it stays inside the tracking group, and anything else
    wearing the name is refused rather than adopted -- upserting onto the lab's
    `TENANT_K8S` and then deleting it on decommissioning is the failure this
    prevents.
    """
    matching = [node for node in existing if _value(node.name) == wanted_name]
    if not matching:
        return None
    if recorded_id in {node.id for node in matching}:
        return recorded_id
    msg = (
        f"an EVPN tenant named {wanted_name!r} already exists and this service does not record it; "
        "rename the request, or point its evpn_tenant at the existing object first to adopt it"
    )
    raise ValueError(msg)


@dataclass(frozen=True)
class OnboardingContext:
    """A validated request, resolved before the first write."""

    onboarding: OnboardingNode
    name: str
    description: str | None
    tenant_name: str
    fabric_id: str
    vni_base: int
    adopted: str | None


def evpn_tenant_name(organization: str) -> str:
    """`acme` becomes `TENANT_ACME`, which is what the lab's own tenants look
    like and what every VRF and route target already references."""
    return f"TENANT_{organization.upper().replace('-', '_')}"


def validate_model(parsed: GenerateTenantOnboardingQuery) -> OnboardingContext:
    """Resolve and check everything before anything is written."""
    onboarding = parsed.target.edges[0].node if parsed.target.edges else None
    if onboarding is None:
        msg = "no ServiceTenantOnboarding matched the requested name"
        raise ValueError(msg)

    name = _value(onboarding.name)
    organization = _node_of(onboarding.organization)
    fabric = _node_of(onboarding.fabric)
    if organization is None or fabric is None:
        missing = "organization" if organization is None else "fabric"
        msg = f"onboarding {name!r} names no {missing}"
        raise ValueError(msg)

    organization_name = _value(organization.name)
    if not organization_name:
        msg = f"onboarding {name!r} names an organization with no name"
        raise ValueError(msg)

    recorded = _node_of(onboarding.evpn_tenant)
    tenant_name = evpn_tenant_name(organization_name)

    stated = _value(onboarding.mac_vrf_vni_base)
    if stated is not None:
        vni_base = int(stated)
    elif recorded is not None and _value(recorded.mac_vrf_vni_base) is not None:
        # A rebuild keeps the base it already has; re-deriving could move it,
        # and every VNI beneath it with it.
        vni_base = int(_value(recorded.mac_vrf_vni_base))
    else:
        vni_base = next_vni_base(taken_bases(parsed))

    return OnboardingContext(
        onboarding=onboarding,
        name=name,
        description=_value(onboarding.description),
        tenant_name=tenant_name,
        fabric_id=fabric.id,
        vni_base=vni_base,
        adopted=adopted_id(_edges_of(parsed.evpn_tenant), tenant_name, None if recorded is None else recorded.id),
    )


def is_withdrawn(onboarding: OnboardingNode) -> bool:
    return _value(onboarding.status) in WITHDRAWN_STATUSES


class TenantOnboardingGenerator(InfrahubGenerator):
    """Materialize a tenant's presence on a fabric."""

    async def generate(self, data: dict) -> None:
        parsed = GenerateTenantOnboardingQuery(**data)

        onboarding = parsed.target.edges[0].node if parsed.target.edges else None
        if onboarding is None:
            msg = "no ServiceTenantOnboarding matched the requested name"
            raise ValueError(msg)

        if is_withdrawn(onboarding):
            await self._withdraw(onboarding)
            return

        try:
            context = validate_model(parsed)
        except ValueError:
            await self._set_status(onboarding.id, "error")
            raise

        tenant_id = await self._upsert_tenant(context)
        await self._record(context, tenant_id)
        await self._set_status(onboarding.id, "active")
        self.logger.info(
            "Tenant %r is on the fabric with VNI base %s; run `invoke avd` to reach the switches",
            context.tenant_name,
            context.vni_base,
        )

    async def _upsert_tenant(self, context: OnboardingContext) -> str:
        """The EVPN tenant, written again on every run.

        Skipping it because it already exists is what leaves it outside this
        run's tracking group, and `delete_unused_nodes` then removes it while
        the service still points at it.
        """
        data: dict[str, Any] = {
            "name": context.tenant_name,
            "description": context.description or f"{context.tenant_name} on the fabric",
            "mac_vrf_vni_base": context.vni_base,
            "fabrics": [context.fabric_id],
        }
        if context.adopted is not None:
            data["id"] = context.adopted

        tenant = await self.client.create(kind="EvpnTenant", data=data)
        await tenant.save(allow_upsert=True)
        return tenant.id

    async def _record(self, context: OnboardingContext, tenant_id: str) -> None:
        """``update_group_context=False``: the request is this generator's
        target, not something it owns."""
        service = await self.client.get(kind="ServiceTenantOnboarding", id=context.onboarding.id)
        service.evpn_tenant = tenant_id  # type: ignore[attr-defined]
        service.mac_vrf_vni_base.value = context.vni_base  # type: ignore[union-attr]
        await service.save(update_group_context=False)

    async def _withdraw(self, onboarding: OnboardingNode) -> None:
        """Remove the EVPN tenant an earlier run created.

        The tracking context does not cover this -- `update_group` returns early
        on an empty member set, so a run that writes nothing prunes nothing.

        **Refused while anything hangs off it.** An EvpnTenant carries VRFs and
        L2VLANs, and deleting one with tenants' networks beneath it would take
        them too. The generator reports rather than cascading, because the
        operator has to decide what happens to those networks.
        """
        name = _value(onboarding.name)
        tenant = _node_of(onboarding.evpn_tenant)
        if tenant is None:
            self.logger.info("Onboarding %r built no EVPN tenant; nothing to withdraw", name)
            await self._set_status(onboarding.id, "decommissioned")
            return

        live = await self._init_client.get(kind="EvpnTenant", id=tenant.id, prefetch_relationships=False)
        for relationship in ("vrfs", "l2vlans"):
            manager = getattr(live, relationship, None)
            if manager is None:
                continue
            await manager.fetch()
            if manager.peer_ids:
                self.logger.warning(
                    "EVPN tenant %r still has %s %s; refusing to delete it. Remove them first",
                    _value(tenant.name),
                    len(manager.peer_ids),
                    relationship,
                )
                await self._set_status(onboarding.id, "error")
                return

        service = await self.client.get(kind="ServiceTenantOnboarding", id=onboarding.id)
        service.evpn_tenant = None  # type: ignore[attr-defined]
        await service.save(update_group_context=False)

        await self.client.delete(kind="EvpnTenant", id=tenant.id)
        await self._set_status(onboarding.id, "decommissioned")
        self.logger.info("Withdrew EVPN tenant %r", _value(tenant.name))

    async def _set_status(self, service_id: str, status: str) -> None:
        service = await self.client.get(kind="ServiceTenantOnboarding", id=service_id)
        if _value(service.status) == status:  # type: ignore[attr-defined]
            return
        service.status.value = status  # type: ignore[union-attr]
        await service.save(update_group_context=False)
        self.logger.info("Onboarding status set to %s", status)

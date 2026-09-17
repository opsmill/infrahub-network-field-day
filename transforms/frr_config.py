"""FRR configuration for the WAN: the ISP, the customer edges and the branch.

The half of the lab AVD does not cover. The fabric renders through PyAVD; these
six routers render here, from the same graph, with the same property: change the
model, re-render, review the diff.

The templates are ported from ``../lab/wan/templates`` with one line changed --
the provenance header, because Infrahub is not ``wan/render.py``. Everything
else, comments included, is identical, and ``tests/unit/test_frr_config.py``
holds it to the lab's rendered output line for line.

WHERE THE SERVICE LAYER BECOMES VISIBLE. ``isp-pe1``'s per-tenant import policy
is assembled from ordered intent rather than from device facts:

    route-map RM-ACME-IMPORT permit 10   <- ServiceL3vpn.dc_service_prefixes
    route-map RM-ACME-IMPORT permit 20   <- ServiceTenantCloud.prefix
    route-map RM-ACME-IMPORT permit 30   <- a ServiceInternetAccess EXISTS

globex has no ``permit 30`` because globex bought no internet access. The
difference between the two tenants is the presence of one object, and it shows
up as four lines of routing policy on a real device.

Cycle 010's assumption 6 says renderers read technical objects. The provider
edge is the exception that layering was built for: its import policy *is* the
service intent, which is why three service kinds are inputs here.
"""

from __future__ import annotations

from typing import Any

from infrahub_sdk.transforms import InfrahubTransform
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .frr_config_query import FrrConfigQuery

# One template per device role, so a second router of an existing role needs no
# code change. cust-acme-dr-ce also has role `customer_edge` and is deliberately
# not a target -- it runs no routing protocol and the lab renders no FRR config
# for it, which is why the target group names its members explicitly.
ROLE_TO_TEMPLATE = {
    "isp_edge": "isp-edge.j2",
    "isp_core": "isp-core.j2",
    "internet_edge": "internet-rtr.j2",
    "customer_edge": "customer-ce.j2",
    "branch_router": "branch-router.j2",
}

# The lab's tenant order, which drives the order of the VRF blocks and import
# route-maps on the provider edge. Infrahub stores no authoring order, so an
# explicit sequence is the only way to reproduce it deterministically.
TENANT_ORDER = ("acme", "globex")


# A service in either state is rendered as though it did not exist. See
# `FrrConfig._live`: `decommissioning` counts as gone rather than going, because
# the alternative is a window where the intent is withdrawn and the router is
# not.
DECOMMISSIONED_STATUSES = frozenset({"decommissioning", "decommissioned"})


class FrrConfigError(RuntimeError):
    """A required value was missing.

    Raised rather than rendering a blank. The lab's renderer uses
    ``StrictUndefined`` for the same reason: a BGP neighbor line with an empty
    address is accepted by vtysh and never comes up, so a silent blank is worse
    than a failed render.
    """


def _strip_mask(address: str) -> str:
    return address.split("/", 1)[0]


def _first(edges: list[Any]) -> Any | None:
    return edges[0].node if edges else None


class FrrConfig(InfrahubTransform):
    """Renders one WAN router's FRR configuration."""

    query = "frr_config"

    async def transform(self, data: dict[str, Any]) -> str:
        result = FrrConfigQuery(**data)

        target = _first(result.target.edges)
        if target is None:
            raise FrrConfigError("query returned no target device")

        node_name = target.name.value
        role = target.role.value
        template_name = ROLE_TO_TEMPLATE.get(role)
        if template_name is None:
            raise FrrConfigError(f"{node_name}: role {role!r} has no FRR template")

        context = self._build_context(result, target)
        env = Environment(
            loader=FileSystemLoader(f"{self.root_directory}/transforms/templates/frr"),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            # Autoescaping is for markup. HTML-escaping a router config would
            # corrupt it -- `&` in a description, `>` nowhere -- and the output
            # is never served to a browser.
            autoescape=False,  # noqa: S701
            keep_trailing_newline=True,
        )
        return env.get_template(template_name).render(node=node_name, **context)

    # -- context assembly ---------------------------------------------------

    def _build_context(self, result: FrrConfigQuery, target: Any) -> dict[str, Any]:
        devices = {edge.node.name.value: edge.node for edge in result.dcim_device.edges}
        devices[target.name.value] = target
        by_role = {node.role.value: node for node in devices.values()}

        addr_owner = self._address_owners(result)
        services = self._services(result)

        context: dict[str, Any] = {
            "isp": self._isp(by_role, services, result),
            "tenants": self._tenants(result, services, addr_owner),
        }
        if "branch_router" in by_role:
            context["branch"] = self._branch(result, by_role["branch_router"])

        # The customer-edge template is rendered per site, so it needs its own
        # site and tenant rather than the whole list.
        if target.role.value == "customer_edge":
            tenant, site = self._site_for_ce(context["tenants"], target.name.value)
            # The CE's router id IS its LAN-side address -- one of the three
            # routers whose router id is not a loopback, which is why cycle 020
            # made router_id explicit rather than derived.
            if target.router_id is None or target.router_id.node is None:
                raise FrrConfigError(f"{target.name.value}: no router id, so no router-id line can be rendered")
            site["ce"]["lan_address"] = target.router_id.node.address.value
            context["tenant"] = tenant
            context["site"] = site
        return context

    @staticmethod
    def _address_owners(result: FrrConfigQuery) -> dict[str, str]:
        """Map bare address -> owning device.

        This is how a statically attached site's CE is found: it has no BGP
        session, but its static route's next hop is its own WAN address, and
        cycle 021 attached every address to its interface.
        """
        owners: dict[str, str] = {}
        for edge in result.ipam_ip_address.edges:
            interface = edge.node.interface.node if edge.node.interface else None
            device = getattr(interface, "device", None) if interface else None
            if device and device.node:
                owners[_strip_mask(edge.node.address.value)] = device.node.name.value
        return owners

    @staticmethod
    def _live(node: Any) -> bool:
        """Whether a service should be rendered at all.

        A decommissioned service is treated as ABSENT, which is the only
        interpretation that makes `status` mean anything here. Until this
        existed, marking a tenant's L3VPN decommissioned left the provider edge
        importing its prefixes exactly as before: the service said gone, the
        router said up, and nothing reported the disagreement.

        `decommissioning` counts as gone rather than going. The alternative is a
        window in which the intent is withdrawn and the configuration is not,
        and the whole point of the state is to close that window.
        """
        status = getattr(node, "status", None)
        return status is None or status.value not in DECOMMISSIONED_STATUSES

    @classmethod
    def _services(cls, result: FrrConfigQuery) -> dict[str, Any]:
        l3vpn = {e.node.tenant.node.name.value: e.node for e in result.service_l_3_vpn.edges if cls._live(e.node)}
        cloud = {e.node.tenant.node.name.value: e.node for e in result.service_tenant_cloud.edges if cls._live(e.node)}
        # Presence is the datum. A tenant is in this set if it bought internet
        # access, and that is the only place the fact lives -- so a
        # decommissioned one has to be filtered out here rather than anywhere
        # downstream, because downstream only ever sees the set.
        internet = {
            e.node.l_3_vpn.node.tenant.node.name.value
            for e in result.service_internet_access.edges
            if e.node.l_3_vpn and e.node.l_3_vpn.node and cls._live(e.node)
        }
        return {"l3vpn": l3vpn, "cloud": cloud, "internet": internet}

    def _isp(self, by_role: dict[str, Any], services: dict[str, Any], result: FrrConfigQuery) -> dict[str, Any]:
        edge, core = by_role.get("isp_edge"), by_role.get("isp_core")
        if edge is None or core is None:
            raise FrrConfigError("the provider edge and core devices must both be modelled")

        isp: dict[str, Any] = {
            "asn": edge.asn.node.asn.value,
            "edge": self._provider_device(edge, core.name.value),
            "core": self._provider_device(core, edge.name.value),
            # The shared DC service range: what every tenant may reach
            # regardless of what it buys. Identical on every L3VPN.
            "dc_service_prefixes": [
                p.node.prefix.value for p in next(iter(services["l3vpn"].values())).dc_service_prefixes.edges
            ],
        }

        isp["core"]["dc"] = self._dc_handoff(core, isp["asn"], peering_asns=self._peering_asns(result))

        peering = _first(result.wan_internet_peering.edges)
        if peering is not None:
            router = by_role.get("internet_edge")
            if router is None:
                raise FrrConfigError("an internet peering exists but its router is not modelled")
            # `lan` is the network behind the internet router, which it
            # announces to the provider; `internet_prefixes` holds it.
            lan = _first(peering.internet_prefixes.edges)
            if lan is None:
                raise FrrConfigError("the internet peering names no internet prefix")
            isp["internet"] = {
                "asn": peering.peer_asn.value,
                "router": router.name.value,
                "customer_aggregate": peering.customer_aggregate.node.prefix.value,
                "lan": lan.prefix.value,
                # Two sides, two addresses. `peer` is what the provider dials
                # and `address` is what the internet router dials back, which is
                # why the lab's own model names them separately.
                "peering": {
                    "node": core.name.value,
                    "peer": self._session_toward(core, peering.peer_asn.value)["peer"],
                    "address": f"{self._session_toward(router, isp['asn'])['peer']}/30",
                },
            }
        return isp

    def _provider_device(self, device: Any, peer_name: str) -> dict[str, Any]:
        """A PE's own identity plus its session toward its partner.

        The iBGP session between the two PEs hangs off the DEVICE, not off any
        WanSite -- it is provider infrastructure rather than a tenant
        attachment, so no site names it.
        """
        entry: dict[str, Any] = {
            "node": device.name.value,
            "loopback": _strip_mask(device.router_id.node.address.value),
        }
        own_asn = device.asn.node.asn.value
        ibgp = self._session_toward(device, own_asn)
        entry["core"] = {"peer": ibgp["peer"], "node": peer_name}
        return entry

    @staticmethod
    def _session_toward(device: Any, remote_as: int | str) -> dict[str, Any]:
        wanted = str(remote_as)
        for edge in device.bgp_neighbors.edges:
            if edge.node.remote_as and edge.node.remote_as.value == wanted:
                return {"peer": edge.node.peer_address.value, "remote_as": wanted}
        raise FrrConfigError(f"{device.name.value}: no BGP session toward AS {wanted}")

    @staticmethod
    def _peering_asns(result: FrrConfigQuery) -> set[str]:
        return {str(e.node.peer_asn.value) for e in result.wan_internet_peering.edges}

    @staticmethod
    def _dc_handoff(device: Any, own_asn: int, peering_asns: set[str]) -> dict[str, Any]:
        """The session toward the fabric, found by elimination.

        The core PE holds three sessions: iBGP to the edge (its own AS), transit
        to the internet (the peering's AS), and the handoff to border-leaf1. The
        last is whatever is left, and it is device-scoped -- no WanSite names it,
        because the fabric is not a tenant attachment.
        """
        for edge in device.bgp_neighbors.edges:
            remote = edge.node.remote_as.value if edge.node.remote_as else None
            if remote and remote != str(own_asn) and remote not in peering_asns:
                return {"peer": edge.node.peer_address.value, "peer_asn": int(remote)}
        raise FrrConfigError(f"{device.name.value}: no session toward the fabric")

    def _tenants(
        self, result: FrrConfigQuery, services: dict[str, Any], addr_owner: dict[str, str]
    ) -> list[dict[str, Any]]:
        sites_by_tenant: dict[str, list[Any]] = {}
        for edge in result.wan_site.edges:
            sites_by_tenant.setdefault(edge.node.tenant.node.name.value, []).append(edge.node)

        tenants = []
        for name in TENANT_ORDER:
            if name not in services["l3vpn"]:
                continue
            tenants.append(
                {
                    "name": name,
                    "vrf": services["l3vpn"][name].vrf.node.name.value,
                    "internet": name in services["internet"],
                    "dc": {"subnet": services["cloud"][name].prefix.node.prefix.value},
                    "sites": [
                        self._site(site, addr_owner) for site in self._ordered_sites(sites_by_tenant.get(name, []))
                    ],
                }
            )
        return tenants

    @staticmethod
    def _ordered_sites(sites: list[Any]) -> list[Any]:
        """BGP attachments first, then static, each by name.

        Reproduces the lab's authoring order, which Infrahub does not store, and
        matches how the templates read them -- two separate loops by kind.
        Sorting by name alone leaves a two-line diff in the per-tenant site
        inventory comment on isp-pe1.
        """
        return sorted(sites, key=lambda s: (s.attachment_kind.value != "bgp", s.name.value))

    def _site(self, site: Any, addr_owner: dict[str, str]) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "name": site.name.value,
            "kind": site.attachment_kind.value,
            "lan": site.lan_prefix.node.prefix.value,
        }
        if entry["kind"] == "bgp":
            entry["asn"] = site.site_asn.value
            pe_side = self._session_from_role(site, "isp_edge")
            ce_side = self._session_from_role(site, "customer_edge")
            if pe_side is None or ce_side is None:
                # The branch peers with a fabric device, so only its own side is
                # a WAN session. It is not a tenant site on the provider edge.
                entry["pe"] = {"address": None}
                entry["ce"] = {"wan_address": None, "node": None}
                return entry
            entry["pe"] = {"address": f"{ce_side.peer_address.value}/30"}
            entry["ce"] = {
                "wan_address": f"{pe_side.peer_address.value}/30",
                "node": ce_side.device.node.name.value,
            }
        else:
            route = _first(site.static_routes.edges)
            if route is None:
                raise FrrConfigError(f"static site {entry['name']!r} has no static route")
            next_hop = _strip_mask(route.next_hop.value)
            entry["ce"] = {
                "wan_address": f"{next_hop}/30",
                "node": addr_owner.get(next_hop),
            }
            if entry["ce"]["node"] is None:
                raise FrrConfigError(f"static site {entry['name']!r}: no device owns {next_hop}")
        return entry

    @staticmethod
    def _session_from_role(site: Any, role: str) -> Any | None:
        for edge in site.bgp_sessions.edges:
            if edge.node.device and edge.node.device.node.role.value == role:
                return edge.node
        return None

    def _site_for_ce(self, tenants: list[dict[str, Any]], ce_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for tenant in tenants:
            for site in tenant["sites"]:
                if site.get("ce", {}).get("node") == ce_name:
                    return tenant, site
        raise FrrConfigError(f"{ce_name}: no WanSite names this device as its customer edge")

    def _branch(self, result: FrrConfigQuery, device: Any) -> dict[str, Any]:
        site = next(
            (e.node for e in result.wan_site.edges if e.node.tenant.node.name.value == "branch"),
            None,
        )
        if site is None:
            raise FrrConfigError("the branch router is modelled but its site is not")
        session = _first(site.bgp_sessions.edges)
        if session is None:
            raise FrrConfigError("the branch site has no BGP session")
        return {
            "name": site.tenant.node.name.value,
            "asn": device.asn.node.asn.value,
            "loopback": _strip_mask(device.router_id.node.address.value),
            "lan": site.lan_prefix.node.prefix.value,
            "router": {
                "node": device.name.value,
                "dc_peer": session.peer_address.value,
                "dc_peer_asn": int(session.remote_as.value),
            },
        }

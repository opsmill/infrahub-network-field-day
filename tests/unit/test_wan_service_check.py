"""Unit tests for the WAN service consistency check.

Fixtures rather than a live instance, for the reason `peering_consistency_check`
gives: none of these violations can be created against the running lab without
first breaking it. A proposed change can contain every one of them, which is the
point.

The fixtures are the lab's real shapes -- `acme` with two circuits and `globex`
with one, `TENANT_ACME`/`TENANT_GLOBEX` behind `acme-cloud`/`globex-cloud` --
because the rules are about relationships *between* those objects and invented
shapes would satisfy them trivially.

**The rule that matters most is the first.** `ServiceL3vpn.circuits` is not a
label, it is the routing domain: two of a tenant's sites reach each other because
both circuits are in the list. A circuit belonging to another tenant therefore
joins the two tenants directly across the provider edge -- the thing the whole
design exists to prevent, and the thing nothing checked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from checks import wan_service_check
from checks.wan_service_check import (
    check_circuit_membership,
    check_cloud_zone_matches_vrf,
    check_dependents_renderable,
    check_exclusive_clouds,
    check_exclusive_vrfs,
    check_l3vpn_renderable,
    collect_findings,
)
from checks.wan_service_check_query import WanServiceCheckQuery
from transforms import srl_config

# Captured graph responses, not hand-written: `main` is the seeded lab, and
# `third-tenant` is a scratch branch that added `initech` the long way -- a
# tenant cloud, a statically routed site, its CE and a provider-edge port --
# and on which srl_config rendered the tenant onto ethernet-1/5.
FIXTURES = Path(__file__).parent / "fixtures" / "wan_service_check"

# The sections rules 1-4 never read. The synthetic L3VPNs and clouds below keep
# their own shapes; everything else is the lab as captured.
_RENDER_SECTIONS = ("WanSite", "DcimDevice", "WanInternetPeering", "IpamIPAddress")


def _captured(name: str = "main") -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


ACME = ("tenant-acme", "acme")
GLOBEX = ("tenant-globex", "globex")
VRF_ACME_PE = ("vrf-cust-acme", "CUST_ACME")
VRF_GLOBEX_PE = ("vrf-cust-globex", "CUST_GLOBEX")
VRF_ACME_DC = ("vrf-tenant-acme", "TENANT_ACME")
VRF_GLOBEX_DC = ("vrf-tenant-globex", "TENANT_GLOBEX")
ZONE_ACME = ("zone-acme-cloud", "acme-cloud")
ZONE_GLOBEX = ("zone-globex-cloud", "globex-cloud")


def _wrap(value: Any) -> dict[str, Any]:
    return {"value": value}


def _rel(pair: tuple[str, str] | None) -> dict[str, Any]:
    return {"node": None} if pair is None else {"node": {"id": pair[0], "name": _wrap(pair[1])}}


def _circuit(circuit_id: str, owner: tuple[str, str] | None) -> dict[str, Any]:
    return {"node": {"id": f"ckt-{circuit_id}", "circuit_id": _wrap(circuit_id), "tenant": _rel(owner)}}


def _l3vpn(
    name: str,
    *,
    tenant: tuple[str, str] | None,
    vrf: tuple[str, str] | None,
    circuits: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "node": {
            "id": f"vpn-{name}",
            "name": _wrap(name),
            "status": _wrap("active"),
            "tenant": _rel(tenant),
            "vrf": _rel(vrf),
            "circuits": {"edges": circuits},
            "dc_service_prefixes": {"edges": [{"node": {"prefix": _wrap("10.112.240.0/24")}}]},
        }
    }


def _cloud(
    name: str,
    *,
    tenant: tuple[str, str],
    vrf: tuple[str, str],
    zone: tuple[str, str],
    zone_vrf: tuple[str, str] | None,
    prefix: str = "10.220.10.0/24",
) -> dict[str, Any]:
    return {
        "node": {
            "id": f"cloud-{name}",
            "name": _wrap(name),
            "status": _wrap("active"),
            "tenant": _rel(tenant),
            "vrf": _rel(vrf),
            "zone": {"node": {"id": zone[0], "name": _wrap(zone[1]), "vrf": _rel(zone_vrf)}},
            "prefix": {"node": {"id": f"pfx-{name}", "prefix": _wrap(prefix)}},
        }
    }


def _lab() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The lab as it actually is: two L3VPNs, two clouds, all consistent."""
    vpns = [
        _l3vpn(
            "acme-l3vpn", tenant=ACME, vrf=VRF_ACME_PE, circuits=[_circuit("acme-hq", ACME), _circuit("acme-dr", ACME)]
        ),
        _l3vpn("globex-l3vpn", tenant=GLOBEX, vrf=VRF_GLOBEX_PE, circuits=[_circuit("globex-hq", GLOBEX)]),
    ]
    clouds = [
        _cloud("acme-cloud", tenant=ACME, vrf=VRF_ACME_DC, zone=ZONE_ACME, zone_vrf=VRF_ACME_DC),
        _cloud(
            "globex-cloud",
            tenant=GLOBEX,
            vrf=VRF_GLOBEX_DC,
            zone=ZONE_GLOBEX,
            zone_vrf=VRF_GLOBEX_DC,
            prefix="10.220.20.0/24",
        ),
    ]
    return vpns, clouds


def _query(
    vpns: list[dict[str, Any]] | None = None, clouds: list[dict[str, Any]] | None = None
) -> WanServiceCheckQuery:
    lab_vpns, lab_clouds = _lab()
    captured = _captured()
    return WanServiceCheckQuery(
        ServiceL3vpn={"edges": lab_vpns if vpns is None else vpns},
        ServiceTenantCloud={"edges": lab_clouds if clouds is None else clouds},
        **{section: captured[section] for section in _RENDER_SECTIONS},
    )


# ---------------------------------------------------------------------------
# The lab itself is clean, which is what makes every failure below evidence
# ---------------------------------------------------------------------------


def test_the_lab_as_modelled_passes_every_rule() -> None:
    """Without this, a check that reports nothing proves nothing."""
    assert collect_findings(_query()) == []


# ---------------------------------------------------------------------------
# Rule 1 -- a circuit belonging to another tenant
# ---------------------------------------------------------------------------


def test_a_foreign_circuit_is_reported() -> None:
    """The failure the provider-edge design exists to prevent.

    Membership of `circuits` IS the routing domain, so globex's circuit inside
    acme's VPN means the two reach each other directly.
    """
    vpns, _ = _lab()
    vpns[0]["node"]["circuits"]["edges"].append(_circuit("globex-hq", GLOBEX))

    findings = check_circuit_membership(_query(vpns=vpns))
    assert len(findings) == 1
    assert "globex" in findings[0].message
    assert findings[0].object_type == "ServiceL3vpn"


def test_a_circuit_with_no_tenant_is_left_to_another_check() -> None:
    """Attributing it here points at the VPN for a defect in the circuit."""
    vpns, _ = _lab()
    vpns[0]["node"]["circuits"]["edges"].append(_circuit("orphan", None))
    assert check_circuit_membership(_query(vpns=vpns)) == []


def test_a_vpn_with_no_tenant_is_not_judged() -> None:
    vpns = [_l3vpn("headless", tenant=None, vrf=VRF_ACME_PE, circuits=[_circuit("acme-hq", ACME)])]
    assert check_circuit_membership(_query(vpns=vpns)) == []


# ---------------------------------------------------------------------------
# Rule 2 -- two L3VPNs in one provider-edge VRF
# ---------------------------------------------------------------------------


def test_two_vpns_sharing_a_vrf_are_both_reported() -> None:
    """Both, because neither is more wrong than the other and a reviewer needs
    to see the pair."""
    vpns, _ = _lab()
    vpns[1]["node"]["vrf"] = _rel(VRF_ACME_PE)

    findings = check_exclusive_vrfs(_query(vpns=vpns))
    assert len(findings) == 2
    assert {f.object_id for f in findings} == {"vpn-acme-l3vpn", "vpn-globex-l3vpn"}
    assert "one routing table" in findings[0].message


def test_distinct_vrfs_are_clean() -> None:
    assert check_exclusive_vrfs(_query()) == []


# ---------------------------------------------------------------------------
# Rule 3 -- a zone governing a different VRF
# ---------------------------------------------------------------------------


def test_a_cloud_whose_zone_governs_another_vrf_is_reported() -> None:
    """generate-app-access matches an application's VRF against the zone's, so
    a mismatch here sends grants into a policy for somewhere else."""
    _, clouds = _lab()
    clouds[0] = _cloud("acme-cloud", tenant=ACME, vrf=VRF_ACME_DC, zone=ZONE_ACME, zone_vrf=VRF_GLOBEX_DC)

    findings = check_cloud_zone_matches_vrf(_query(clouds=clouds))
    assert len(findings) == 1
    assert "TENANT_GLOBEX" in findings[0].message
    assert findings[0].object_type == "ServiceTenantCloud"


def test_a_zone_with_no_vrf_is_left_to_another_check() -> None:
    """It cannot be matched to an application either, but that is the zone's
    defect rather than this service's."""
    _, clouds = _lab()
    clouds[0] = _cloud("acme-cloud", tenant=ACME, vrf=VRF_ACME_DC, zone=ZONE_ACME, zone_vrf=None)
    assert check_cloud_zone_matches_vrf(_query(clouds=clouds)) == []


# ---------------------------------------------------------------------------
# Rule 4 -- two clouds sharing a VRF or a zone
# ---------------------------------------------------------------------------


def test_two_clouds_sharing_a_vrf_are_reported() -> None:
    _, clouds = _lab()
    clouds[1]["node"]["vrf"] = _rel(VRF_ACME_DC)

    findings = check_exclusive_clouds(_query(clouds=clouds))
    assert len(findings) == 2
    assert all("collapses two" in f.message for f in findings)


def test_two_clouds_sharing_a_zone_are_reported() -> None:
    """The one that most looks like tidy reuse when it is written."""
    _, clouds = _lab()
    clouds[1]["node"]["zone"] = {"node": {"id": ZONE_ACME[0], "name": _wrap(ZONE_ACME[1]), "vrf": _rel(VRF_GLOBEX_DC)}}

    findings = check_exclusive_clouds(_query(clouds=clouds))
    assert len(findings) == 2
    assert all("firewall zone" in f.message.lower() for f in findings)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def test_findings_from_every_rule_are_collected() -> None:
    vpns, clouds = _lab()
    vpns[0]["node"]["circuits"]["edges"].append(_circuit("globex-hq", GLOBEX))
    clouds[0] = _cloud("acme-cloud", tenant=ACME, vrf=VRF_ACME_DC, zone=ZONE_ACME, zone_vrf=VRF_GLOBEX_DC)

    findings = collect_findings(_query(vpns=vpns, clouds=clouds))
    assert {f.object_type for f in findings} == {"ServiceL3vpn", "ServiceTenantCloud"}
    assert len(findings) == 2


@pytest.mark.parametrize("empty", [[], None])
def test_an_empty_graph_reports_nothing_rather_than_raising(empty: Any) -> None:
    """A check that raises takes the whole proposed change with it."""
    sections = ("ServiceL3vpn", "ServiceTenantCloud", *_RENDER_SECTIONS)
    parsed = WanServiceCheckQuery(**{section: {"edges": empty or []} for section in sections})
    assert collect_findings(parsed) == []


# ---------------------------------------------------------------------------
# Rules 5 and 6 -- a request srl_config cannot render is red, not a green no-op
#
# The gap these close: srl_config rendered `acme` and `globex` BY NAME and
# skipped every other tenant without a word, so an L3VPN requested through the
# portal for a third one merged green and changed nothing on any router. The
# renderer now takes any tenant; these rules name what a tenant still needs.
# ---------------------------------------------------------------------------


def _parsed(data: dict[str, Any]) -> WanServiceCheckQuery:
    return WanServiceCheckQuery(**data)


def _messages(findings: list[Any]) -> str:
    return "\n".join(f.message for f in findings)


def _portal_l3vpn(name: str = "initech-l3vpn", tenant: str = "initech", **overrides: Any) -> dict[str, Any]:
    """What the portal's generated ServiceL3vpn form creates.

    name, status, tenant and vrf -- and no circuits or dc_service_prefixes,
    because the form builder admits optional relationships of cardinality one
    only.
    """
    node: dict[str, Any] = {
        "id": f"vpn-{name}",
        "name": _wrap(name),
        "status": _wrap("active"),
        "tenant": {"node": {"id": f"tenant-{tenant}", "name": _wrap(tenant)}},
        "vrf": {"node": {"id": f"vrf-{tenant}", "name": _wrap(f"CUST_{tenant.upper()}")}},
        "circuits": {"edges": []},
        "dc_service_prefixes": {"edges": []},
    }
    node.update(overrides)
    return {"node": node}


def _site(data: dict[str, Any], tenant: str, name: str) -> dict[str, Any]:
    return next(
        e["node"]
        for e in data["WanSite"]["edges"]
        if e["node"]["tenant"]["node"]["name"]["value"] == tenant and e["node"]["name"]["value"] == name
    )


def test_the_captured_lab_passes_every_rule() -> None:
    """The seeded graph, as the check actually receives it."""
    assert collect_findings(_parsed(_captured())) == []


def test_a_fully_modelled_third_tenant_passes() -> None:
    """The branch on which srl_config rendered initech onto a port: nothing to report.

    This is the half that proves the rules do not simply refuse every new
    tenant -- the same tenant, modelled, is clean.
    """
    data = _captured("third-tenant")
    tenants = {e["node"]["tenant"]["node"]["name"]["value"] for e in data["ServiceL3vpn"]["edges"]}
    assert tenants == {"acme", "globex", "initech"}
    assert collect_findings(_parsed(data)) == []


def test_a_portal_request_for_a_tenant_the_lab_cannot_carry_names_what_is_missing() -> None:
    """THE GAP. The old check passed this and the old renderer skipped it.

    Measured on a scratch branch before the fix: the provider edge rendered
    byte-identical to main and `wan-service-consistency` reported PASSED.
    """
    data = _captured()
    data["ServiceL3vpn"]["edges"].append(_portal_l3vpn())

    findings = check_l3vpn_renderable(_parsed(data))
    text = _messages(findings)
    assert {f.object_id for f in findings} == {"vpn-initech-l3vpn"}
    assert {f.object_type for f in findings} == {"ServiceL3vpn"}
    assert "no live ServiceTenantCloud for 'initech'" in text
    assert "no WanSite for 'initech'" in text
    # acme and globex are not dragged in: one tenant's gap is not everyone's.
    assert "acme" not in text and "globex" not in text


def test_a_request_with_no_vrf_is_reported() -> None:
    """`vrf` is optional on the schema, so the portal form lets a request omit it."""
    data = _captured()
    data["ServiceL3vpn"]["edges"].append(_portal_l3vpn(vrf={"node": None}))

    assert "no provider-edge VRF" in _messages(check_l3vpn_renderable(_parsed(data)))


def test_a_name_srl_cannot_carry_is_reported() -> None:
    data = _captured()
    data["ServiceL3vpn"]["edges"].append(_portal_l3vpn(tenant="Initech Corp"))

    assert "cannot be spliced" in _messages(check_l3vpn_renderable(_parsed(data)))


def test_two_live_l3vpns_for_one_tenant_are_both_reported() -> None:
    """srl_config refuses either rather than let the second replace the first."""
    data = _captured()
    data["ServiceL3vpn"]["edges"].append(_portal_l3vpn(name="acme-l3vpn-2", tenant="acme"))

    findings = check_l3vpn_renderable(_parsed(data))
    assert len(findings) == 2
    assert all("2 live L3VPNs" in f.message for f in findings)


@pytest.mark.parametrize("status", ["decommissioning", "decommissioned"])
def test_a_withdrawn_request_is_not_judged_on_renderability(status: str) -> None:
    """It deliberately renders as absent, so it needs no attachment."""
    data = _captured()
    data["ServiceL3vpn"]["edges"].append(_portal_l3vpn(status=_wrap(status)))

    assert check_l3vpn_renderable(_parsed(data)) == []


def test_a_static_site_whose_next_hop_nobody_owns_is_reported() -> None:
    data = _captured()
    _site(data, "acme", "dr")["static_routes"]["edges"][0]["node"]["next_hop"] = _wrap("10.51.11.6/32")

    text = _messages(check_l3vpn_renderable(_parsed(data)))
    assert "site acme/dr: no device owns the static route's next hop 10.51.11.6" in text
    # The same address is on no provider-edge port either, and both are said.
    assert "no provider-edge interface has an address on the subnet of 10.51.11.6" in text


def test_a_site_with_no_provider_edge_port_is_reported() -> None:
    """The VRF renders with nothing in it -- the failure that looks like success."""
    data = _captured()
    for device in data["DcimDevice"]["edges"]:
        if device["node"]["name"]["value"] == "isp-pe1":
            for interface in device["node"]["interfaces"]["edges"]:
                if interface["node"].get("name", {}).get("value") == "ethernet-1/3":
                    interface["node"]["ip_addresses"]["edges"] = []

    findings = check_l3vpn_renderable(_parsed(data))
    assert len(findings) == 1
    assert "site globex/hq: no provider-edge interface" in findings[0].message


def test_a_bgp_site_with_no_customer_edge_session_is_reported() -> None:
    """srl_config used to render this as `neighbor None peer-group ...`."""
    data = _captured()
    site = _site(data, "globex", "hq")
    site["bgp_sessions"]["edges"] = [
        e for e in site["bgp_sessions"]["edges"] if e["node"]["device"]["node"]["role"]["value"] != "customer_edge"
    ]

    assert "needs a session on the provider edge AND one on a customer edge" in _messages(
        check_l3vpn_renderable(_parsed(data))
    )


def test_a_customer_edge_outside_srl_routers_is_reported() -> None:
    """No artifact is rendered for it, so the session never comes up."""
    data = _captured()
    for device in data["DcimDevice"]["edges"]:
        if device["node"]["name"]["value"] == "cust-globex-ce":
            device["node"]["member_of_groups"]["edges"] = []

    assert "'cust-globex-ce' is not in the `srl_routers` group" in _messages(check_l3vpn_renderable(_parsed(data)))


def test_a_bgp_site_without_an_asn_is_reported() -> None:
    data = _captured()
    _site(data, "globex", "hq")["site_asn"] = _wrap(None)

    assert "no site_asn" in _messages(check_l3vpn_renderable(_parsed(data)))


def test_a_site_lan_outside_the_customer_aggregate_is_reported() -> None:
    """border-leaf1 accepts `10.60.0.0/16 le 24` from the WAN and fw1 routes only that back."""
    data = _captured()
    _site(data, "globex", "hq")["lan_prefix"]["node"]["prefix"] = _wrap("10.61.20.0/24")

    assert "lies outside the customer aggregate 10.60.0.0/16" in _messages(check_l3vpn_renderable(_parsed(data)))


def test_a_tenant_cloud_with_no_live_l3vpn_renders_nowhere() -> None:
    data = _captured()
    for vpn in data["ServiceL3vpn"]["edges"]:
        if vpn["node"]["tenant"]["node"]["name"]["value"] == "globex":
            vpn["node"]["status"] = _wrap("decommissioned")

    findings = check_dependents_renderable(_parsed(data))
    assert [f.object_type for f in findings] == ["ServiceTenantCloud"]
    assert "globex-cloud" in findings[0].message


def test_an_l3vpn_stating_no_dc_range_takes_the_shared_one() -> None:
    """The portal cannot state one, and must not need to."""
    data = _captured()
    data["ServiceL3vpn"]["edges"][0]["node"]["dc_service_prefixes"]["edges"] = []

    assert check_dependents_renderable(_parsed(data)) == []


def test_disagreeing_dc_ranges_are_reported() -> None:
    data = _captured()
    data["ServiceL3vpn"]["edges"][0]["node"]["dc_service_prefixes"]["edges"] = [
        {"node": {"prefix": _wrap("10.112.0.0/16")}}
    ]

    findings = check_dependents_renderable(_parsed(data))
    assert len(findings) == 2
    assert all("differ from another live L3VPN" in f.message for f in findings)


def test_no_dc_range_anywhere_is_reported() -> None:
    data = _captured()
    for vpn in data["ServiceL3vpn"]["edges"]:
        vpn["node"]["dc_service_prefixes"]["edges"] = []

    assert "has no source" in _messages(check_dependents_renderable(_parsed(data)))


def test_the_check_and_the_renderer_agree_on_what_counts_as_live_and_safe() -> None:
    """Restated rather than imported, so held equal here."""
    assert wan_service_check.DECOMMISSIONED_STATUSES == srl_config.DECOMMISSIONED_STATUSES
    assert wan_service_check.SAFE_NAME.pattern == srl_config.SAFE_NAME.pattern

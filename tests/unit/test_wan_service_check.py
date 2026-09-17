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

from typing import Any

import pytest

from checks.wan_service_check import (
    check_circuit_membership,
    check_cloud_zone_matches_vrf,
    check_exclusive_clouds,
    check_exclusive_vrfs,
    collect_findings,
)
from checks.wan_service_check_query import WanServiceCheckQuery

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
    return WanServiceCheckQuery(
        ServiceL3vpn={"edges": lab_vpns if vpns is None else vpns},
        ServiceTenantCloud={"edges": lab_clouds if clouds is None else clouds},
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
    parsed = WanServiceCheckQuery(ServiceL3vpn={"edges": empty or []}, ServiceTenantCloud={"edges": empty or []})
    assert collect_findings(parsed) == []

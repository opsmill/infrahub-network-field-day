"""Unit tests for the zone advertisement check.

Fixtures rather than a live instance, for the reason the peering check gives:
most of these violations cannot be created against a running lab. The generator
raises on a half-modelled zone before it writes anything, and a prefix list that
no scope declares is not a state anything will produce on purpose. A proposed
change can still contain every one of them, which is the point.

The check exists to discharge a condition cycle 032 attached to its own design:
`dc_advertised_prefix_list` is a NAME rather than a relationship, because there
is no object to reference -- every prefix list in this fabric lives inside
`avd_custom_hostvars`. That was only defensible if the mismatch were detectable.
"""

from __future__ import annotations

from typing import Any

from checks.zone_advertisement_check import (
    PREFIX_LISTS_KEY,
    check_grant_reachability,
    check_zone_policies,
    collect_findings,
    declared_prefix_lists,
)
from checks.zone_advertisement_check_query import ZoneAdvertisementCheckQuery

ADVERTISED_LIST = "PL-DC-ADVERTISED-BRANCH"
BORDER_LEAF = "leaf-otternet-pod1-3-1"
VIP_BLOCK = "10.112.240.0/28"


def _hostvars(*names: str) -> dict[str, Any]:
    return {PREFIX_LISTS_KEY: [{"name": name, "sequence_numbers": []} for name in names]}


def _zone(
    name: str,
    *,
    prefix_list: str | None = ADVERTISED_LIST,
    device: str | None = BORDER_LEAF,
    device_hostvars: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "node": {
            "id": f"zone-{name}",
            "name": {"value": name},
            "dc_advertised_prefix_list": {"value": prefix_list},
            "advertising_device": (
                {
                    "node": {
                        "id": f"dev-{device}",
                        "name": {"value": device},
                        "avd_custom_hostvars": {"value": device_hostvars},
                    }
                }
                if device
                else {"node": None}
            ),
        }
    }


def _grant(
    name: str = "branch-to-otternet-demo",
    *,
    approved: bool = True,
    vip: str | None = "10.112.240.10/32",
    exposed: bool = True,
    block: str | None = VIP_BLOCK,
) -> dict[str, Any]:
    return {
        "node": {
            "id": f"grant-{name}",
            "name": {"value": name},
            # `approved` used to select the grants worth judging; the branch
            # is the gate now, so a WITHDRAWN grant is the one to skip.
            "status": {"value": "provisioning" if approved else "decommissioning"},
            "destination_vip": ({"node": {"id": "ip-vip", "address": {"value": vip}}} if vip else {"node": None}),
            "application": {
                "node": {
                    "id": "app-otternet-demo",
                    "name": {"value": "otternet-demo"},
                    "exposed": {"value": exposed},
                    "vip_block": ({"node": {"id": "pfx-vip", "prefix": {"value": block}}} if block else {"node": None}),
                }
            },
            "source_zone": {"node": {"id": "zone-branch", "name": {"value": "branch"}}},
        }
    }


def _query(
    *,
    zones: list[dict[str, Any]] | None = None,
    fabric_hostvars: dict[str, Any] | None = None,
    grants: list[dict[str, Any]] | None = None,
) -> ZoneAdvertisementCheckQuery:
    return ZoneAdvertisementCheckQuery(
        SecurityZone={"edges": zones if zones is not None else [_zone("branch")]},
        NetworkFabric={
            "edges": [
                {
                    "node": {
                        "id": "fabric-otternet",
                        "name": {"value": "OTTERNET_FABRIC"},
                        "avd_custom_hostvars": {
                            "value": fabric_hostvars if fabric_hostvars is not None else _hostvars(ADVERTISED_LIST)
                        },
                    }
                }
            ]
        },
        ServiceAppAccess={"edges": grants if grants is not None else []},
    )


# ---------------------------------------------------------------------------
# Rule 1 -- the named prefix list has to exist somewhere
# ---------------------------------------------------------------------------


def test_a_zone_naming_a_declared_list_is_clean() -> None:
    assert check_zone_policies(_query()) == []


def test_a_zone_naming_a_list_nobody_declares_is_reported() -> None:
    """The silent failure this check exists for.

    The generator writes a permit into a list no route map matches. The route
    never appears, the firewall still permits the session, and nothing errors.
    """
    parsed = _query(fabric_hostvars=_hostvars("PL-SOMETHING-ELSE"))
    findings = check_zone_policies(parsed)
    assert len(findings) == 1
    assert "the fabric does not declare" in findings[0].message


def test_a_list_declared_only_at_device_scope_does_not_count() -> None:
    """The regression test for a hole a live negative case found.

    `generate-app-access` creates the named list at device scope whenever it
    advertises -- that is how the merge composes a grant with the baseline. So
    once a grant has run, the device declares the very name this rule questions
    and the reference becomes self-fulfilling. Measured: a branch naming
    PL-DOES-NOT-EXIST failed this check before any grant ran and passed it
    afterwards.

    A prefix list is declared where a human authored it, which is fabric scope.
    """
    parsed = _query(
        zones=[_zone("branch", device_hostvars=_hostvars(ADVERTISED_LIST))],
        fabric_hostvars=_hostvars("PL-SOMETHING-ELSE"),
    )
    findings = check_zone_policies(parsed)
    assert len(findings) == 1
    assert "the fabric does not declare" in findings[0].message


def test_the_generators_own_entry_does_not_excuse_a_bad_name() -> None:
    """The exact live shape: the device declares both the real list and the
    bogus one the generator created for it."""
    parsed = _query(
        zones=[
            _zone(
                "branch",
                prefix_list="PL-DOES-NOT-EXIST",
                device_hostvars=_hostvars(ADVERTISED_LIST, "PL-DOES-NOT-EXIST"),
            )
        ],
        fabric_hostvars=_hostvars(ADVERTISED_LIST),
    )
    assert len(check_zone_policies(parsed)) == 1


# ---------------------------------------------------------------------------
# Rule 2 -- both halves, or neither
# ---------------------------------------------------------------------------


def test_a_zone_with_neither_half_is_not_a_finding() -> None:
    """Four of the six zones are in this state: the DC advertises nothing toward
    them. Reporting it would make the check noise on a correct lab."""
    parsed = _query(zones=[_zone("k8s-prod", prefix_list=None, device=None)])
    assert check_zone_policies(parsed) == []


def test_a_zone_missing_its_device_is_reported() -> None:
    parsed = _query(zones=[_zone("branch", device=None)])
    findings = check_zone_policies(parsed)
    assert len(findings) == 1
    assert "advertising_device is unset" in findings[0].message


def test_a_zone_missing_its_prefix_list_is_reported() -> None:
    parsed = _query(zones=[_zone("branch", prefix_list=None)])
    findings = check_zone_policies(parsed)
    assert len(findings) == 1
    assert "dc_advertised_prefix_list is unset" in findings[0].message


# ---------------------------------------------------------------------------
# Rules 3 and 4 -- a grant the fabric can never carry
# ---------------------------------------------------------------------------


def test_a_grant_inside_the_vip_block_is_clean() -> None:
    assert check_grant_reachability(_query(grants=[_grant()])) == []


def test_a_grant_outside_the_vip_block_is_reported() -> None:
    """Permitted and unroutable -- what access_services.yml warns about on
    `destination_vip`. The cluster only advertises from the block."""
    parsed = _query(grants=[_grant(vip="10.112.241.10/32")])
    findings = check_grant_reachability(parsed)
    assert len(findings) == 1
    assert "outside" in findings[0].message


def test_a_grant_on_an_unexposed_application_is_reported() -> None:
    """An unexposed application gets no pool, no VIP and no advertisement."""
    parsed = _query(grants=[_grant(exposed=False)])
    findings = check_grant_reachability(parsed)
    assert len(findings) == 1
    assert "not exposed" in findings[0].message


def test_a_withdrawn_grant_is_not_judged() -> None:
    """It materializes nothing, so it cannot be unroutable yet. Reporting it
    would block every merge that merely drafts a request."""
    parsed = _query(grants=[_grant(approved=False, vip="10.112.241.10/32", exposed=False)])
    assert check_grant_reachability(parsed) == []


def test_a_malformed_address_is_left_to_another_check() -> None:
    """Attributing it here would point at the grant for a defect in the IPAM
    object, and the check must not raise and take the proposed change down."""
    parsed = _query(grants=[_grant(vip="not-an-address")])
    assert check_grant_reachability(parsed) == []


# ---------------------------------------------------------------------------
# Shape tolerance -- the attribute is hand-edited free-form JSON
# ---------------------------------------------------------------------------


def test_malformed_hostvars_declare_nothing_rather_than_raising() -> None:
    """A check that raises takes the whole proposed change with it, so a blob
    someone typed badly must degrade to "declares nothing"."""
    for blob in (None, [], "text", {PREFIX_LISTS_KEY: "not-a-list"}, {PREFIX_LISTS_KEY: [{"no_name": 1}]}):
        assert declared_prefix_lists(blob) == set()


def test_findings_from_both_halves_are_collected() -> None:
    parsed = _query(
        zones=[_zone("branch", device=None)],
        grants=[_grant(exposed=False)],
    )
    assert len(collect_findings(parsed)) == 2

"""Golden-file tests for the WAN FRR render.

The oracle is `../lab/wan/rendered/*/frr.conf` -- 448 lines the lab actually
runs, written by a renderer this repository did not author. That makes equality
the right assertion: a substring check would pass on a config with a missing BGP
neighbour, which vtysh accepts and which never comes up, and avoiding exactly
that is why cycles 020 and 021 existed.

One line is excluded. Every lab file opens with

    ! Rendered by wan/render.py for <node> -- do not edit.

and Infrahub is not `wan/render.py`. Reproducing it verbatim would put a false
provenance claim in six device configurations, so the port names its real
renderer and the comparison normalises that line only.

Fixtures are captured graph responses, not hand-written, so drift between the
model and the fixture cannot hide a rendering bug.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from transforms.frr_config import ROLE_TO_TEMPLATE, FrrConfig, FrrConfigError

FIXTURES = Path("tests/unit/fixtures/frr")
RENDERED = Path("../lab/wan/rendered")
REPO_ROOT = Path(__file__).parents[2]

DEVICES = (
    "isp-pe1",
    "isp-pe2",
    "internet-rtr",
    "cust-acme-ce",
    "cust-globex-ce",
    "branch-rtr",
)


def _fixture(device: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{device}.json").read_text(encoding="utf-8"))


def _golden(device: str) -> str:
    path = RENDERED / device / "frr.conf"
    if not path.is_file():
        pytest.skip("lab repo not checked out alongside this one")
    return path.read_text(encoding="utf-8")


def _without_provenance(text: str) -> str:
    """Drop the one line that must differ, and only that line."""
    return "\n".join(line for line in text.splitlines() if "-- do not edit." not in line)


def _transform() -> FrrConfig:
    """Built with __new__, as the other transform tests do.

    InfrahubTransform.__init__ wants a client and a node type that a unit test
    has no use for; only `root_directory` matters here, because the Jinja2
    loader resolves the template directory from it.
    """
    transform = FrrConfig.__new__(FrrConfig)
    transform.root_directory = str(REPO_ROOT)
    return transform


async def _render(device: str) -> str:
    return await _transform().transform(_fixture(device))


# ---------------------------------------------------------------------------
# The gate: every device, byte for byte
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("device", DEVICES)
async def test_render_matches_the_lab(device: str) -> None:
    rendered = await _render(device)

    assert _without_provenance(rendered) == _without_provenance(_golden(device))


@pytest.mark.parametrize("device", DEVICES)
async def test_provenance_names_infrahub_not_the_lab(device: str) -> None:
    """The single deliberate difference, asserted so it cannot drift back."""
    first = (await _render(device)).splitlines()[0]

    assert first == f"! Rendered by Infrahub for {device} -- do not edit."
    assert "wan/render.py" not in first


# ---------------------------------------------------------------------------
# The service layer, which is the point of the exercise
# ---------------------------------------------------------------------------


async def test_removing_internet_access_changes_only_its_own_clause() -> None:
    """SC-003, measured rather than reasoned about.

    Five lines removed -- the `permit 30` clause, its description, its match,
    the `!` closing the block, and the old tenant header -- and one added, the
    header re-rendered with `internet: no`.
    """
    import difflib

    with_access = await _render("isp-pe1")

    fixture = _fixture("isp-pe1")
    fixture["ServiceInternetAccess"]["edges"] = []
    without = await _transform().transform(fixture)

    changed = [
        line
        for line in difflib.unified_diff(with_access.splitlines(), without.splitlines(), lineterm="", n=0)
        if line[:1] in "+-" and line[:3] not in ("+++", "---")
    ]

    assert len(changed) == 6, changed
    assert "-route-map RM-ACME-IMPORT permit 30" in changed
    assert "- match ip address prefix-list PL-DEFAULT" in changed
    assert "+! ==== tenant acme (VRF CUST_ACME, internet: no) ====" in changed


async def test_the_default_route_prefix_list_survives_that_removal() -> None:
    """It is guarded by the ISP having an internet connection, not by a tenant
    buying access, so it must stay even when no tenant has bought any.
    """
    fixture = _fixture("isp-pe1")
    fixture["ServiceInternetAccess"]["edges"] = []
    without = await _transform().transform(fixture)

    assert "ip prefix-list PL-DEFAULT seq 10 permit 0.0.0.0/0" in without


async def test_globex_has_no_default_route_clause() -> None:
    """The control. globex is configured identically apart from what it bought."""
    rendered = await _render("isp-pe1")

    assert "route-map RM-ACME-IMPORT permit 30" in rendered
    assert "route-map RM-GLOBEX-IMPORT permit 30" not in rendered


async def test_the_static_site_is_redistributed_not_peered() -> None:
    """acme/dr runs no protocol: a route in the VRF, and no neighbour."""
    rendered = await _render("isp-pe1")

    assert " ip route 10.60.11.0/24 10.51.11.2" in rendered
    assert "  redistribute static" in rendered
    assert "neighbor 10.51.11.2" not in rendered


# ---------------------------------------------------------------------------
# Failing loudly
# ---------------------------------------------------------------------------


async def test_a_missing_router_id_raises_rather_than_rendering_a_blank() -> None:
    """A BGP router-id line with an empty value is accepted by vtysh and the
    session still forms, so a blank here is worse than a failed render.

    Two guards catch it, and this asserts the inner one. An absent `router_id`
    key fails in the generated query model before the transform runs at all --
    stronger than expected, and worth knowing -- so this sets the relationship
    present but unresolved, which is the shape a device with no router id
    actually produces.
    """
    fixture = _fixture("cust-acme-ce")
    fixture["target"]["edges"][0]["node"]["router_id"] = {"node": None}

    with pytest.raises(FrrConfigError, match="no router id"):
        await _transform().transform(fixture)


async def test_an_absent_router_id_key_fails_in_the_typed_model() -> None:
    """The outer guard: the generated query model will not accept it as None."""
    import pydantic

    fixture = _fixture("cust-acme-ce")
    fixture["target"]["edges"][0]["node"]["router_id"] = None

    with pytest.raises(pydantic.ValidationError):
        await _transform().transform(fixture)


async def test_an_unmapped_role_raises() -> None:
    fixture = _fixture("cust-acme-ce")
    fixture["target"]["edges"][0]["node"]["role"]["value"] = "firewall"
    with pytest.raises(FrrConfigError, match="no FRR template"):
        await _transform().transform(fixture)


def test_every_frr_role_has_a_template() -> None:
    template_dir = Path("transforms/templates/frr")

    for role, name in ROLE_TO_TEMPLATE.items():
        assert (template_dir / name).is_file(), f"{role} -> {name} missing"


def test_the_statically_attached_ce_has_no_template_target() -> None:
    """cust-acme-dr-ce shares the customer_edge role but the lab renders no FRR
    config for it, which is why the target group lists its members explicitly
    instead of deriving them from the role.
    """
    assert not (FIXTURES / "cust-acme-dr-ce.json").exists()

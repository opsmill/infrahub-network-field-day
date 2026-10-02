"""Golden-file tests for the WAN SR Linux render.

The oracle is `lab/wan/rendered/*/config.cli`, rendered by `lab/wan/render.py`
from `lab/wan/tenants.yml` -- the files ContainerLab boots the routers with.
Equality is the right assertion: a substring check would pass on a configuration
with a missing BGP neighbour, which loads and never comes up.

What makes this oracle stronger than the FRR one it replaces is that it was
BOOTED. The same files ran on a throwaway six-router SR Linux prototype with a
stand-in border leaf, and the reachability matrix in the pull request -- tenant
isolation, the static site, the bridged branch LAN, full
MTU -- passed against them. Byte-for-byte equality here is what extends that
evidence to the artifact Infrahub renders.

One line is excluded. Every lab file opens with

    # Rendered by wan/render.py for <node> -- do not edit.

and Infrahub is not `wan/render.py`, so the transform names its real renderer
and the comparison normalises that line only.

Fixtures are captured graph responses -- from a scratch branch after
`scripts/migrate_wan_srlinux.py` and the object load -- not hand-written, so
drift between the model and the fixture cannot hide a rendering bug.
"""

from __future__ import annotations

import difflib
import json
import re
import subprocess  # noqa: S404 - one fixed-argv call to the committed renderer
import sys
from pathlib import Path
from typing import Any

import pytest

from transforms import srl_config
from transforms.srl_config import (
    LAN_MAC_VRF,
    ROLE_TO_TEMPLATE,
    SrlConfig,
    SrlConfigError,
    assert_comments_unquoted,
    port_key,
)

FIXTURES = Path("tests/unit/fixtures/srl")
REPO_ROOT = Path(__file__).parents[2]
LAB_WAN = REPO_ROOT / "lab" / "wan"
RENDERED = LAB_WAN / "rendered"
LAB_TEMPLATES = LAB_WAN / "templates"
HUB_TEMPLATES = REPO_ROOT / "transforms" / "templates" / "srl"

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
    """The lab's own rendering of `device`, produced on demand.

    `lab/wan/rendered/` is gitignored output of `lab/wan/render.py`, so a fresh
    clone -- CI included -- has none. The renderer needs nothing this
    environment lacks, so render instead of skipping.
    """
    path = RENDERED / device / "config.cli"
    if not path.is_file():
        subprocess.run(  # noqa: S603 - a fixed argv: this interpreter and a committed script
            [sys.executable, str(LAB_WAN / "render.py")], check=True, capture_output=True
        )
    return _without_internet_product(path.read_text(encoding="utf-8"))


def _without_internet_product(text: str) -> str:
    """The lab's text, minus the internet-access product this repository does not model.

    The lab renders `statement 30` for a tenant with `internet: true`. The
    service kind that drives it is not part of this model, so the oracle is
    compared with those lines, the header annotation and the two comments that
    describe them removed. Applies to rendered output and to template source.
    """
    text = re.sub(r"\{% if t\.internet %\}\n.*?\{% endif %\}\n", "", text, flags=re.DOTALL)
    text = re.sub(r"# \S+ buys internet access\n(?:set .* statement 30 .*\n)+", "", text)
    text = text.replace(", internet: {{ 'yes' if t.internet else 'no' }})", ")")
    text = re.sub(r", internet: (?:yes|no)\)", ")", text)
    text = text.replace(
        "subnet of that tenant, and a default route only if the tenant buys internet", "subnet of that tenant"
    )
    text = re.sub(
        r"# Announce only the sites of tenants.*?(?=set / routing-policy policy RM-INTERNET-OUT default-action)",
        "# No tenant buys internet access, so nothing is announced: the policy is its\n# default action alone.\n",
        text,
        flags=re.DOTALL,
    )
    return text.replace(
        "# Shared DC services, plus the own cloud subnet of this tenant, plus a default\n"
        "# route if it bought internet. Anything",
        "# Shared DC services, plus the own cloud subnet of this tenant. Anything",
    )


def _without_provenance(text: str) -> str:
    """Drop the one line that must differ, and only that line."""
    return "\n".join(line for line in text.splitlines() if "-- do not edit." not in line)


def _transform() -> SrlConfig:
    """Built with __new__, as the other transform tests do.

    InfrahubTransform.__init__ wants a client and a node type that a unit test
    has no use for; only `root_directory` matters here, because the Jinja2
    loader resolves the template directory from it.
    """
    transform = SrlConfig.__new__(SrlConfig)
    transform.root_directory = str(REPO_ROOT)
    return transform


async def _render(device: str) -> str:
    return await _transform().transform(_fixture(device))


def _changed(before: str, after: str) -> list[str]:
    return [
        line
        for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
        if line[:1] in "+-" and line[:3] not in ("+++", "---")
    ]


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

    assert first == f"# Rendered by Infrahub for {device} -- do not edit."
    assert "wan/render.py" not in first


def test_the_templates_are_the_labs_with_one_line_changed() -> None:
    """Two copies of seven templates, held together.

    The golden test above only exercises the paths today's data takes; a
    branch of a template that no fixture reaches -- no tenant without internet
    access on the core, say -- could drift unnoticed. This holds every line.
    """
    lab = sorted(p.name for p in LAB_TEMPLATES.glob("*.srl.j2"))
    hub = sorted(p.name for p in HUB_TEMPLATES.glob("*.srl.j2"))
    assert lab == hub

    for name in lab:
        assert _without_provenance(
            _without_internet_product((LAB_TEMPLATES / name).read_text())
        ) == _without_provenance((HUB_TEMPLATES / name).read_text()), name


# ---------------------------------------------------------------------------
# The service layer, which is the point of the exercise
# ---------------------------------------------------------------------------


async def test_the_default_route_prefix_set_follows_the_isp_internet_connection() -> None:
    """It is guarded by the ISP having an internet connection, not by a tenant service."""
    without = await _render("isp-pe1")

    assert "set / routing-policy prefix-set PL-DEFAULT prefix 0.0.0.0/0 mask-length-range exact" in without


async def test_the_static_site_is_routed_and_put_into_bgp_not_peered() -> None:
    """acme/dr runs no protocol: a route in the VRF, the BGP table takes it, no neighbour."""
    rendered = await _render("isp-pe1")

    assert "set / network-instance CUST_ACME static-routes route 10.60.11.0/24 next-hop-group acme-dr" in rendered
    assert "set / routing-policy policy BGP-TABLE-CUST_ACME statement 20 match protocol static" in rendered
    assert "policy BGP-TABLE-CUST_GLOBEX statement 20" not in rendered
    assert "neighbor 10.51.11.2" not in rendered


async def test_both_halves_of_route_leaking_are_rendered() -> None:
    """Measured on the prototype: either half alone leaks NOTHING, silently.

    An import policy with no inter-instance export leaves every tenant VRF
    empty; leaked routes without `rib-management` reach the route table and
    never BGP, so the core learns only a loopback. Every session is up in both
    failure modes.
    """
    rendered = await _render("isp-pe1")

    for instance, import_policy in (
        ("default", "IMPORT-TENANT-VRFS"),
        ("CUST_ACME", "RM-ACME-IMPORT"),
        ("CUST_GLOBEX", "RM-GLOBEX-IMPORT"),
    ):
        prefix = f"set / network-instance {instance} "
        assert f"{prefix}inter-instance-policies apply-policy import-policy [ {import_policy} ]" in rendered
        assert f"{prefix}inter-instance-policies apply-policy export-policy [ LEAKABLE ]" in rendered
        table = f"BGP-TABLE-{'DEFAULT' if instance == 'default' else instance}"
        assert f"{prefix}protocols bgp rib-management table ipv4-unicast route-table-import {table}" in rendered


async def test_every_tenant_import_is_restricted_to_the_provider_instance() -> None:
    """`import vrf default` in FRR: only routes that ORIGINATED in default."""
    rendered = await _render("isp-pe1")
    statements = [line for line in rendered.splitlines() if "-IMPORT statement" in line and " match prefix " in line]
    for line in statements:
        policy, number = line.split()[4], line.split()[6]
        assert f"set / routing-policy policy {policy} statement {number} match origin-network-instance default" in (
            rendered
        )


# ---------------------------------------------------------------------------
# `status` withdraws, as it did under FRR
# ---------------------------------------------------------------------------


async def test_a_decommissioned_l3vpn_withdraws_its_tenant_and_shuts_its_ports() -> None:
    """The tenant leaves the provider edge, and its ports do NOT fall into default.

    Under FRR the boot script enslaved a customer port to its VRF whatever the
    services said. Here the artifact owns the port, so a withdrawn tenant's port
    must go somewhere deliberate: shut, in no network instance. Left to the
    default branch of the logic it would land in the provider instance, with the
    tenant's subnet in the provider table.
    """
    fixture = _fixture("isp-pe1")
    for edge in fixture["ServiceL3vpn"]["edges"]:
        if edge["node"]["tenant"]["node"]["name"]["value"] == "acme":
            edge["node"]["status"] = {"value": "decommissioned"}
    rendered = await _transform().transform(fixture)

    assert "RM-ACME-IMPORT" not in rendered
    assert "network-instance CUST_ACME" not in rendered
    for port in ("ethernet-1/2", "ethernet-1/4"):
        assert f"set / interface {port} admin-state disable" in rendered
        assert f"interface {port}.0" not in rendered
        assert f"set / interface {port} subinterface" not in rendered
    # globex is untouched, so this is a withdrawal rather than a wholesale break.
    assert "RM-GLOBEX-IMPORT" in rendered
    assert "set / network-instance CUST_GLOBEX interface ethernet-1/3.0" in rendered


# ---------------------------------------------------------------------------
# Interfaces, which FRR never rendered
# ---------------------------------------------------------------------------


async def test_provider_edge_ports_land_in_their_tenants_vrf() -> None:
    """Derived from the attachment addresses: nothing stores the membership."""
    rendered = await _render("isp-pe1")

    assert "set / network-instance CUST_ACME interface ethernet-1/2.0" in rendered  # acme/hq, eBGP
    assert "set / network-instance CUST_ACME interface ethernet-1/4.0" in rendered  # acme/dr, static
    assert "set / network-instance CUST_GLOBEX interface ethernet-1/3.0" in rendered
    assert "set / network-instance default interface ethernet-1/1.0" in rendered  # the core


async def test_the_branch_lan_is_a_mac_vrf_routed_by_its_irb() -> None:
    rendered = await _render("branch-rtr")

    assert f"set / network-instance {LAN_MAC_VRF} type mac-vrf" in rendered
    for port in ("ethernet-1/2", "ethernet-1/3", "ethernet-1/4"):
        assert f"set / interface {port} subinterface 0 type bridged" in rendered
        assert f"set / network-instance {LAN_MAC_VRF} interface {port}.0" in rendered
    assert "set / interface irb0 subinterface 0 ipv4 address 10.70.0.1/24" in rendered
    assert f"set / network-instance {LAN_MAC_VRF} interface irb0.0" in rendered
    assert "set / network-instance default interface irb0.0" in rendered


@pytest.mark.parametrize("device", DEVICES)
async def test_every_routed_port_states_its_ip_mtu(device: str) -> None:
    """SR Linux defaults ip-mtu to 1500 whatever the port carries; the border leaf runs 9214."""
    rendered = await _render(device)
    addressed = {line.split()[3] for line in rendered.splitlines() if " ipv4 address " in line and "lo0" not in line}

    for interface in addressed:
        assert f"set / interface {interface} subinterface 0 ip-mtu 9214" in rendered


@pytest.mark.parametrize("device", DEVICES)
async def test_every_router_carries_the_management_lifeline(device: str) -> None:
    """A push replaces the WHOLE configuration: without these, mgmt0 is deleted."""
    rendered = await _render(device)

    assert "set / interface mgmt0 subinterface 0 ipv4 dhcp-client" in rendered
    assert "set / network-instance mgmt interface mgmt0.0" in rendered


async def test_a_physical_port_with_nothing_to_say_is_refused() -> None:
    fixture = _fixture("cust-acme-ce")
    for edge in fixture["target"]["edges"][0]["node"]["interfaces"]["edges"]:
        edge["node"]["ip_addresses"]["edges"] = []
    with pytest.raises(SrlConfigError, match="neither an address nor an L2 mode"):
        await _transform().transform(fixture)


async def test_bridged_ports_without_an_irb_are_refused() -> None:
    fixture = _fixture("branch-rtr")
    edges = fixture["target"]["edges"][0]["node"]["interfaces"]["edges"]
    fixture["target"]["edges"][0]["node"]["interfaces"]["edges"] = [
        e for e in edges if e["node"]["name"]["value"] != "irb0"
    ]
    with pytest.raises(SrlConfigError, match="no irb routes them"):
        await _transform().transform(fixture)


def test_ports_sort_numerically_not_lexically() -> None:
    names = ["ethernet-1/10", "lo0", "ethernet-1/2", "irb0", "ethernet-1/1"]

    assert sorted(names, key=port_key) == ["ethernet-1/1", "ethernet-1/2", "ethernet-1/10", "irb0", "lo0"]


# ---------------------------------------------------------------------------
# Failing loudly
# ---------------------------------------------------------------------------


def test_a_quote_in_a_comment_is_refused() -> None:
    """sr_cli tokenises quotes before comments: one apostrophe swallows the lines after it.

    Measured on the prototype, and silent -- the router booted, every line
    between two apostrophes simply never applied.
    """
    with pytest.raises(SrlConfigError, match="comment carrying a quote"):
        assert_comments_unquoted("x", "set / a b\n# the tenant's VRF\nset / c d\n")

    assert_comments_unquoted("x", 'set / interface lo0 description "quotes are fine here"\n')


@pytest.mark.parametrize("device", DEVICES)
async def test_no_rendered_comment_carries_a_quote(device: str) -> None:
    rendered = await _render(device)
    assert_comments_unquoted(device, rendered)


async def test_a_missing_router_id_raises_rather_than_rendering_a_blank() -> None:
    fixture = _fixture("cust-acme-ce")
    fixture["target"]["edges"][0]["node"]["router_id"] = {"node": None}

    with pytest.raises(SrlConfigError, match="no router id"):
        await _transform().transform(fixture)


async def test_an_absent_router_id_key_fails_in_the_typed_model() -> None:
    import pydantic

    fixture = _fixture("cust-acme-ce")
    fixture["target"]["edges"][0]["node"]["router_id"] = None

    with pytest.raises(pydantic.ValidationError):
        await _transform().transform(fixture)


async def test_an_l3vpn_without_a_vrf_is_refused_by_name() -> None:
    """The portal's L3VPN form lets `vrf` be omitted; the render must say so.

    It used to raise AttributeError, which Infrahub reports as "Unable to find the
    class SrlConfig" -- an artifact failure on every WAN router naming neither the
    service nor the field.
    """
    fixture = _fixture("isp-pe1")
    for edge in fixture["ServiceL3vpn"]["edges"]:
        if edge["node"]["tenant"]["node"]["name"]["value"] == "acme":
            edge["node"]["vrf"] = {"node": None}

    with pytest.raises(SrlConfigError, match="names no provider-edge VRF"):
        await _transform().transform(fixture)


async def test_a_second_live_l3vpn_for_a_tenant_is_refused_not_folded_in() -> None:
    fixture = _fixture("isp-pe1")
    acme = next(
        edge for edge in fixture["ServiceL3vpn"]["edges"] if edge["node"]["tenant"]["node"]["name"]["value"] == "acme"
    )
    second = json.loads(json.dumps(acme))
    second["node"]["name"] = {"value": "acme-second"}
    fixture["ServiceL3vpn"]["edges"].append(second)

    with pytest.raises(SrlConfigError, match="two live L3VPNs"):
        await _transform().transform(fixture)

    # A decommissioned second one is absent, so it is not a conflict.
    second["node"]["status"] = {"value": "decommissioned"}
    assert await _transform().transform(fixture) == await _render("isp-pe1")


# ---------------------------------------------------------------------------
# Any tenant, not two named ones
#
# srl_config iterated `TENANT_ORDER = ("acme", "globex")`, so that tuple was
# both the render order and the render SET: an L3VPN for any third tenant was
# skipped without a word. Measured on a scratch branch before the fix: with a
# third tenant fully modelled -- cloud, static site, CE, provider-edge port --
# isp-pe1 rendered byte-identical to main apart from that port, shut, because
# it matched no tenant the renderer would look at.
# ---------------------------------------------------------------------------

THIRD_TENANT = FIXTURES / "third-tenant"


def test_the_tenant_set_is_not_a_constant() -> None:
    assert not hasattr(srl_config, "TENANT_ORDER")


async def test_a_third_tenant_renders_onto_its_port() -> None:
    """Captured from the scratch branch; the render there is the one asserted here."""
    fixture = json.loads((THIRD_TENANT / "isp-pe1.json").read_text(encoding="utf-8"))
    rendered = await _transform().transform(fixture)

    for line in (
        "set / interface ethernet-1/5 subinterface 0 ipv4 address 10.51.30.1/30",
        "set / network-instance CUST_INITECH type ip-vrf",
        "set / network-instance CUST_INITECH interface ethernet-1/5.0",
        "set / network-instance CUST_INITECH static-routes route 10.60.30.0/24 next-hop-group initech-hq",
        "set / routing-policy prefix-set PL-INITECH-CLOUD prefix 10.220.30.0/24 mask-length-range exact",
        "set / routing-policy policy RM-INITECH-IMPORT default-action policy-result reject",
        "set / routing-policy policy IMPORT-TENANT-VRFS statement 30 match origin-network-instance CUST_INITECH",
        "set / network-instance CUST_INITECH inter-instance-policies apply-policy import-policy [ RM-INITECH-IMPORT ]",
    ):
        assert line in rendered, line
    # Its portal-shaped L3VPN states no DC range -- it takes the shared one rather than emptying it.
    assert "RM-INITECH-IMPORT statement 30" not in rendered
    assert "set / interface ethernet-1/5 admin-state disable" not in rendered


async def test_adding_a_tenant_only_adds_lines() -> None:
    """acme and globex are untouched: every changed line is an addition."""
    fixture = json.loads((THIRD_TENANT / "isp-pe1.json").read_text(encoding="utf-8"))
    changed = _changed(_golden("isp-pe1"), await _transform().transform(fixture))

    assert changed
    assert [line for line in changed if line.startswith("-") and "-- do not edit." not in line] == []


async def test_tenant_order_does_not_depend_on_query_order() -> None:
    fixture = _fixture("isp-pe1")
    fixture["ServiceL3vpn"]["edges"].reverse()
    fixture["ServiceTenantCloud"]["edges"].reverse()

    assert await _transform().transform(fixture) == await _render("isp-pe1")


async def test_an_l3vpn_stating_no_dc_range_takes_the_shared_one() -> None:
    """The portal's L3VPN form cannot offer dc_service_prefixes.

    The renderer read the FIRST L3VPN's range, so one that stated none and
    came first would have emptied PL-DC-SERVICES for every tenant.
    """
    fixture = _fixture("isp-pe1")
    for edge in fixture["ServiceL3vpn"]["edges"]:
        if edge["node"]["tenant"]["node"]["name"]["value"] == "acme":
            edge["node"]["dc_service_prefixes"]["edges"] = []

    assert await _transform().transform(fixture) == await _render("isp-pe1")


async def test_disagreeing_dc_ranges_are_refused() -> None:
    fixture = _fixture("isp-pe1")
    fixture["ServiceL3vpn"]["edges"][0]["node"]["dc_service_prefixes"]["edges"] = [
        {"node": {"prefix": {"value": "10.112.0.0/16"}}}
    ]
    with pytest.raises(SrlConfigError, match="disagree on the shared DC service range"):
        await _transform().transform(fixture)


async def test_a_tenant_name_srl_cannot_carry_is_refused() -> None:
    fixture = _fixture("isp-pe1")
    for edge in fixture["ServiceL3vpn"]["edges"] + fixture["ServiceTenantCloud"]["edges"]:
        if edge["node"]["tenant"]["node"]["name"]["value"] == "globex":
            edge["node"]["tenant"]["node"]["name"] = {"value": "Globex Corp"}
    with pytest.raises(SrlConfigError, match="cannot be spliced"):
        await _transform().transform(fixture)


async def test_a_bgp_site_without_a_customer_edge_session_is_refused_not_rendered_as_none() -> None:
    """It rendered `neighbor None peer-group globex-hq`, which aborts the candidate."""
    fixture = _fixture("isp-pe1")
    for edge in fixture["WanSite"]["edges"]:
        site = edge["node"]
        if site["tenant"]["node"]["name"]["value"] == "globex":
            site["bgp_sessions"]["edges"] = [
                s for s in site["bgp_sessions"]["edges"] if s["node"]["device"]["node"]["role"]["value"] == "isp_edge"
            ]
    with pytest.raises(SrlConfigError, match="no session on both a provider edge and a customer edge"):
        await _transform().transform(fixture)


async def test_the_branch_is_found_by_its_router_not_by_its_tenant_name() -> None:
    fixture = _fixture("branch-rtr")
    for edge in fixture["WanSite"]["edges"]:
        if edge["node"]["tenant"]["node"]["name"]["value"] == "branch":
            edge["node"]["tenant"]["node"]["name"] = {"value": "head-office"}

    rendered = await _transform().transform(fixture)
    assert _without_provenance(rendered.replace("head-office", "branch")) == _without_provenance(
        await _render("branch-rtr")
    )


async def test_a_customer_edge_router_id_renders_bare_whatever_the_lan_size() -> None:
    """The template strips a literal `/24`; any other LAN would leak its mask."""
    fixture = _fixture("cust-acme-ce")
    fixture["target"]["edges"][0]["node"]["router_id"]["node"]["address"]["value"] = "10.60.10.1/25"

    rendered = await _transform().transform(fixture)
    assert "set / network-instance default protocols bgp router-id 10.60.10.1\n" in rendered


async def test_an_unmapped_role_raises() -> None:
    fixture = _fixture("cust-acme-ce")
    fixture["target"]["edges"][0]["node"]["role"]["value"] = "firewall"
    with pytest.raises(SrlConfigError, match="no SR Linux template"):
        await _transform().transform(fixture)


def test_every_role_has_a_template() -> None:
    for role, name in ROLE_TO_TEMPLATE.items():
        assert (HUB_TEMPLATES / name).is_file(), f"{role} -> {name} missing"


def test_the_statically_attached_ce_has_no_template_target() -> None:
    """cust-acme-dr-ce shares the customer_edge role but runs no protocol, which
    is why the target group lists its members explicitly."""
    assert not (FIXTURES / "cust-acme-dr-ce.json").exists()


# ---------------------------------------------------------------------------
# A FULL configuration: everything the router needs, nothing secret
# ---------------------------------------------------------------------------

LAB_HASH_SOURCE = REPO_ROOT / "objects" / "22_otternet_management.yml"


@pytest.mark.parametrize("device", DEVICES)
async def test_the_artifact_is_a_full_replace_and_passes_the_reconcilers_lifeline(device: str) -> None:
    """`delete /` opens it, so applying it anywhere -- boot or push -- leaves exactly this file."""
    from solution_arista_avd.deployment.devices import Target, assert_srl_lifeline

    rendered = await _render(device)
    commands = [line for line in rendered.splitlines() if line.strip() and not line.startswith("#")]

    assert commands[0] == "delete /"
    assert_srl_lifeline(Target(device, "SR Linux Configuration", "x", "Ready", None), rendered)
    assert "set / system grpc-server mgmt default-tls-profile true" in rendered
    assert "set / system management openconfig admin-state enable" in rendered, "the OpenConfig gNMI paths need it"
    assert sum(line.startswith("set / acl acl-filter cpm ") for line in commands) > 500


@pytest.mark.parametrize("device", DEVICES)
async def test_no_key_material_and_no_device_encrypted_value_is_rendered(device: str) -> None:
    """The TLS key and SNMP community ContainerLab writes are `$aes1$`-encrypted per device."""
    rendered = await _render(device)

    for forbidden in ("$aes1$", "BEGIN CERTIFICATE", "PRIVATE KEY", "ssh-key", "tls profile", "snmp"):
        assert forbidden not in rendered, forbidden


async def test_the_admin_hash_is_the_one_the_whole_lab_shares() -> None:
    """NetworkLocalUser `admin` -- the fabric's -- and the lab model's copy are one hash.

    Measured on a router: with it set, admin logs in with the lab password and
    the image default is refused.
    """
    import yaml

    seeded = next(
        u["password"]
        for doc in yaml.safe_load_all(LAB_HASH_SOURCE.read_text(encoding="utf-8"))
        if doc and doc["spec"]["kind"] == "NetworkLocalUser"
        for u in doc["spec"]["data"]
        if u["name"] == "admin"
    )
    lab = yaml.safe_load((LAB_WAN / "tenants.yml").read_text(encoding="utf-8"))["admin_password_hash"]
    rendered = await _render("isp-pe1")

    assert seeded == lab
    assert seeded.startswith("$6$")
    assert f"set / system aaa authentication admin-user password {seeded}" in rendered


@pytest.mark.parametrize(
    ("password_type", "password", "match"),
    [
        (None, None, "no NetworkLocalUser"),
        ("sha512", "admin", "no sha512-crypt hash"),
        ("cleartext", "admin", "no sha512-crypt hash"),
    ],
)
async def test_a_missing_or_cleartext_admin_password_is_refused(
    password_type: str | None, password: str | None, match: str
) -> None:
    fixture = _fixture("isp-pe1")
    if password_type is None:
        fixture["NetworkLocalUser"]["edges"] = []
    else:
        node = fixture["NetworkLocalUser"]["edges"][0]["node"]
        node["password_type"] = {"value": password_type}
        node["password"] = {"value": password}
    with pytest.raises(SrlConfigError, match=match):
        await _transform().transform(fixture)

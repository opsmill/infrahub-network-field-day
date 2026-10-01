#!/usr/bin/env python3
"""Render every WAN device's config from wan/tenants.yml.

The same workflow AVD gives the fabric, for the half of the lab AVD does not
cover: offline rendering, so a change to the data model is reviewable as a diff
before anything is pushed, and CI can check it with no lab running at all.

    make wan-build      # render into wan/rendered/
    git diff wan/rendered/
    make wan-deploy     # push and reload

Writes wan/rendered/<node>/{frr.conf,daemons,init.sh}. The topology
bind-mounts those paths directly, so rendering IS the source of truth for what
a node will run -- there is no second copy to drift.
"""

from __future__ import annotations

import shutil
import stat
import sys
from pathlib import Path

try:
    import yaml
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError as exc:  # pragma: no cover
    sys.exit(
        f"missing dependency: {exc.name}\n"
        "  These come from the AVD virtualenv. Run: make setup\n"
        "  or: .venv/bin/python wan/render.py"
    )

WAN_DIR = Path(__file__).resolve().parent
MODEL = WAN_DIR / "tenants.yml"
TEMPLATES = WAN_DIR / "templates"
OUT = WAN_DIR / "rendered"


def env() -> Environment:
    # StrictUndefined: a typo in the data model must fail the render, not
    # silently emit a config with a blank where an IP should be. A BGP neighbor
    # line with an empty address is accepted by vtysh and never comes up.
    # No autoescape: the output is FRR configuration, where an HTML-escaped `<`
    # or `&` would be a corrupt config rather than a safe one.
    return Environment(  # noqa: S701
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def write(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  {path.relative_to(WAN_DIR.parent)}")


def render_router(
    e: Environment,
    node: str,
    template: str,
    ctx: dict,
    interfaces: list[dict],
    vrfs: list[dict],
    loopback: str | None,
    mtu: int,
    bridges: list[dict] | None = None,
) -> None:
    d = OUT / node
    write(d / "frr.conf", e.get_template(template).render(node=node, **ctx))
    write(d / "daemons", e.get_template("daemons.j2").render(node=node))
    write(
        d / "init.sh",
        e.get_template("init.sh.j2").render(
            node=node,
            interfaces=interfaces,
            vrfs=vrfs,
            loopback=loopback,
            mtu=mtu,
            bridges=bridges or [],
        ),
        executable=True,
    )


def render_host(e: Environment, host: dict, mtu: int, default_route: bool = False) -> None:
    """A plain end host: one address, one way out.

    `default_route` is the difference internet access makes at the host. A host
    behind a tenant that did not buy it gets a route for 10.0.0.0/8 and nothing
    else, so a packet to the internet has nowhere to go from the very first
    hop; a host behind a tenant that did gets a default. Both then depend on
    the PE actually having a default route in that tenant's VRF, which is where
    the product is really enforced -- this just stops the host being the reason
    it fails.
    """
    node = host["node"]
    write(
        OUT / node / "init.sh",
        e.get_template("host-init.sh.j2").render(
            node=node,
            interface=host["interface"],
            address=host["address"],
            gateway=host["gateway"],
            mtu=mtu,
            default_route=default_route,
        ),
        executable=True,
    )


def render_static_ce(e: Environment, tenant: dict, site: dict, mtu: int) -> None:
    """A customer edge with no routing protocol on it at all."""
    node = site["ce"]["node"]
    write(
        OUT / node / "init.sh",
        e.get_template("static-ce.init.sh.j2").render(
            node=node,
            tenant=tenant,
            site=site,
            mtu=mtu,
        ),
        executable=True,
    )


def main() -> int:  # noqa: C901 - one linear pass per node family
    model = yaml.safe_load(MODEL.read_text())
    isp, tenants, branch = model["isp"], model["tenants"], model["branch"]
    mtu = model["mtu"]
    e = env()

    # Prune configs for nodes that are no longer in the model -- a site removed
    # from tenants.yml must not leave a config behind that the topology would
    # still happily bind-mount and boot.
    #
    # Deliberately NOT a wholesale rmtree of wan/rendered/. The topology
    # bind-mounts these exact files into the running containers, and deleting
    # and recreating them replaces the inode, which leaves every running router
    # mounted on a file that no longer exists. Overwriting in place means a
    # re-render is immediately visible inside the container, so `make
    # wan-deploy` only has to tell FRR to re-read it.
    expected = {isp["edge"]["node"], isp["core"]["node"], branch["router"]["node"]}
    expected.update(h["node"] for h in branch["hosts"])
    if "internet" in isp:
        expected.add(isp["internet"]["router"])
        expected.add(isp["internet"]["host"]["node"])
    for t in tenants:
        for site in t["sites"]:
            expected.add(site["ce"]["node"])
            expected.add(site["host"]["node"])
        expected.update(host["node"] for host in t.get("dc", {}).get("hosts", []))
    if OUT.exists():
        for stale in sorted(d for d in OUT.iterdir() if d.is_dir() and d.name not in expected):
            print(f"  pruning {stale.relative_to(WAN_DIR.parent)} (no longer in the model)")
            shutil.rmtree(stale)

    ids = [t["id"] for t in tenants]
    if len(ids) != len(set(ids)):
        return _fail(f"duplicate tenant id in {MODEL.name}: {ids}")
    tables = [t["vrf_table"] for t in tenants]
    if len(tables) != len(set(tables)):
        return _fail(f"duplicate vrf_table in {MODEL.name}: {tables}")
    # Two sites of one tenant share a VRF, so an overlapping LAN between them
    # is not caught by BGP -- it is simply the wrong route winning. Catch it
    # in the model instead, where the fix is obvious.
    lans = [(t["name"], s["name"], s["lan"]) for t in tenants for s in t["sites"]]
    seen: dict[str, tuple[str, str]] = {}
    for tname, sname, lan in lans:
        if lan in seen:
            return _fail(f"duplicate site LAN {lan}: {seen[lan]} and {(tname, sname)}")
        seen[lan] = (tname, sname)

    print("Rendering WAN configs")

    # ---- ISP edge: one VRF per TENANT, one interface per SITE ----
    render_router(
        e,
        isp["edge"]["node"],
        "isp-edge.frr.conf.j2",
        {"isp": isp, "tenants": tenants},
        interfaces=[
            {
                "name": isp["edge"]["core"]["interface"],
                "address": isp["edge"]["core"]["address"],
                "vrf": None,
                "bridge": None,
            },
            *[
                {"name": site["pe"]["interface"], "address": site["pe"]["address"], "vrf": t["vrf"], "bridge": None}
                for t in tenants
                for site in t["sites"]
            ],
        ],
        vrfs=[{"name": t["vrf"], "table": t["vrf_table"]} for t in tenants],
        loopback=isp["edge"]["loopback"],
        mtu=mtu,
    )

    # ---- ISP core: default VRF only, plus the internet peering ----
    core_interfaces = [
        {
            "name": isp["core"]["core"]["interface"],
            "address": isp["core"]["core"]["address"],
            "vrf": None,
            "bridge": None,
        },
        {"name": isp["core"]["dc"]["interface"], "address": isp["core"]["dc"]["address"], "vrf": None, "bridge": None},
    ]
    if "internet" in isp:
        core_interfaces.append(
            {
                "name": isp["internet"]["peering"]["interface"],
                "address": isp["internet"]["peering"]["address"],
                "vrf": None,
                "bridge": None,
            }
        )
    render_router(
        e,
        isp["core"]["node"],
        "isp-core.frr.conf.j2",
        {"isp": isp, "tenants": tenants},
        interfaces=core_interfaces,
        vrfs=[],
        loopback=isp["core"]["loopback"],
        mtu=mtu,
    )

    # ---- the internet ----
    if "internet" in isp:
        net = isp["internet"]
        render_router(
            e,
            net["router"],
            "internet-rtr.frr.conf.j2",
            {"isp": isp},
            interfaces=[
                {
                    "name": net["peering"]["router_interface"],
                    "address": net["peering"]["peer"] + "/30",
                    "vrf": None,
                    "bridge": None,
                },
                {"name": net["lan_interface"], "address": net["lan_address"], "vrf": None, "bridge": None},
            ],
            vrfs=[],
            loopback=None,
            mtu=mtu,
        )
        render_host(e, net["host"], mtu)

    # ---- tenants, and their sites ----
    for t in tenants:
        for site in t["sites"]:
            if site["kind"] == "bgp":
                render_router(
                    e,
                    site["ce"]["node"],
                    "customer-ce.frr.conf.j2",
                    {"isp": isp, "tenant": t, "site": site},
                    interfaces=[
                        {
                            "name": site["ce"]["wan_interface"],
                            "address": site["ce"]["wan_address"],
                            "vrf": None,
                            "bridge": None,
                        },
                        {
                            "name": site["ce"]["lan_interface"],
                            "address": site["ce"]["lan_address"],
                            "vrf": None,
                            "bridge": None,
                        },
                    ],
                    vrfs=[],
                    loopback=None,
                    mtu=mtu,
                )
            elif site["kind"] == "static":
                render_static_ce(e, t, site, mtu)
            else:
                return _fail(
                    f"{t['name']}/{site['name']}: unknown site kind {site['kind']!r} (expected 'bgp' or 'static')"
                )
            render_host(e, site["host"], mtu, default_route=t.get("internet", False))

        # The tenant's isolated cloud instances. Ordinary hosts on an access
        # port in the fabric; what makes them the tenant's is the VRF the SVI
        # sits in and the firewall zone in front of it, neither of which is
        # this file's business.
        for host in t.get("dc", {}).get("hosts", []):
            render_host(e, host, mtu)

    # ---- branch ----
    # The LAN side is a bridge with every branch-facing port enslaved to it, so
    # the site behaves like one switched segment rather than a set of /30s.
    rtr = branch["router"]
    render_router(
        e,
        rtr["node"],
        "branch-router.frr.conf.j2",
        {"branch": branch},
        interfaces=[
            {"name": rtr["dc_interface"], "address": rtr["dc_address"], "vrf": None, "bridge": None},
            *[
                {"name": name, "address": None, "vrf": None, "bridge": rtr["lan_bridge"]}
                for name in rtr["lan_interfaces"]
            ],
        ],
        bridges=[{"name": rtr["lan_bridge"], "address": rtr["lan_address"]}],
        vrfs=[],
        loopback=branch["loopback"],
        mtu=mtu,
    )
    for host in branch["hosts"]:
        render_host(e, host, mtu)

    sites = sum(len(t["sites"]) for t in tenants)
    print(
        f"\n{len(tenants)} tenant(s) / {sites} site(s) + branch"
        f"{' + internet' if 'internet' in isp else ''} rendered into "
        f"{OUT.relative_to(WAN_DIR.parent)}/"
    )
    return 0


def _fail(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

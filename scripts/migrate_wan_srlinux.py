"""Migrate the WAN routers' graph data from FRR naming to SR Linux, in place.

The re-platform renames every router interface to its native SR Linux name --
`eth2` becomes `ethernet-1/2`, `lo` becomes `lo0` -- because the artifact now
configures interfaces and an interface the model calls `eth2` does not exist on
the device. Seed files cannot do a rename on their own:

  * An object load is an UPSERT keyed on the human-friendly id, which for an
    interface is `[device, name]`. Loading `ethernet-1/2` onto a graph that holds
    `eth2` creates a SECOND interface and leaves the first in place, still
    carrying its address -- and `srl_config` would then render both, one with a
    name SR Linux rejects, which aborts the whole candidate.
  * The same is true of the artifact target group, `frr_routers`, which
    becomes `srl_routers`. (Circuit endpoints need nothing: their names are
    computed from the circuit, `acme-hq_A`, and the interface they point at is
    renamed underneath them.)

So this renames in place, which keeps every id and every relationship -- the
addresses stay attached, the circuit endpoints keep their interface, the group keeps its members --
and the seed files then upsert onto names that already exist.

Two things are not renames:

  * `br-branch` was an `InterfacePhysical` standing in for a Linux bridge. Its
    SR Linux successor, `irb0`, is an `InterfaceVirtual`, and a node cannot
    change kind. It is DELETED here; the object load creates `irb0` and moves
    the address `10.70.0.1/24` onto it.
  * `--phase post` runs after the object load and removes what nothing
    references any more: the FRR platform, device type and manufacturer, and
    the `FRR Configuration` artifacts with their definition. Each is deleted only
    if nothing still points at it, and says so if something does.

**It enumerates from the graph**, like scripts/migrate_fabric_app_charts.py, and
is idempotent: a second run finds nothing to rename and says so.

    uv run python scripts/migrate_wan_srlinux.py --branch <b>                 # report
    uv run python scripts/migrate_wan_srlinux.py --branch <b> --apply         # pre: renames
    uv run infrahubctl object load objects/ --branch <b>
    uv run python scripts/migrate_wan_srlinux.py --branch <b> --phase post --apply

Rollback is `--reverse` on the pre phase, followed by loading the PREVIOUS
commit's seed files, which recreate `br-branch` and the FRR platform, device
type and manufacturer the post phase removed.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from typing import Any

from infrahub_sdk import Config, InfrahubClient

# The six routers that become SR Linux. cust-acme-dr-ce is deliberately absent:
# it stays a plain Linux container, so its `eth1`/`eth2` are still real names.
ROUTERS = ("isp-pe1", "isp-pe2", "internet-rtr", "cust-acme-ce", "cust-globex-ce", "branch-rtr")

OLD_GROUP, NEW_GROUP = "frr_routers", "srl_routers"
OLD_PLATFORM, OLD_DEVICE_TYPE, OLD_MANUFACTURER = "FRR", "FRR Container Router", "FRRouting"
OLD_ARTIFACT, OLD_ARTIFACT_DEFINITION = "FRR Configuration", "frr_config"

_ETH = re.compile(r"^eth(\d+)$")
_SRL_PORT = re.compile(r"^ethernet-1/(\d+)$")


def srl_name(name: str) -> str | None:
    """The SR Linux name for a FRR-era interface name, or None if it keeps its name."""
    match = _ETH.match(name)
    if match:
        return f"ethernet-1/{match.group(1)}"
    if name == "lo":
        return "lo0"
    return None


def frr_name(name: str) -> str | None:
    """The inverse of `srl_name`, for `--reverse`: the rollback rename."""
    match = _SRL_PORT.match(name)
    if match:
        return f"eth{match.group(1)}"
    if name == "lo0":
        return "lo"
    return None


def _value(field: Any) -> Any:
    return field.value if field is not None else None


async def _named(client: InfrahubClient, kind: str, name: str, branch: str) -> list[Any]:
    """Nodes whose `name` IS `name` -- re-checked, because the filter alone is not enough.

    Measured on a branch: after renaming `frr_routers` to `srl_routers`, a filter
    on `name__value="frr_routers"` still returned the renamed group, apparently
    matching the value `main` holds. Trusted as-is, this script then reported
    both groups present and refused to run a second time.
    """
    return [
        node for node in await client.filters(kind=kind, name__value=name, branch=branch) if _value(node.name) == name
    ]


def _client(branch: str) -> InfrahubClient:
    token = os.environ.get("INFRAHUB_API_TOKEN")
    if not token:
        msg = (
            "INFRAHUB_API_TOKEN is not set. Export the same token infrahubctl uses -- "
            "for a local stack that is INFRAHUB_INITIAL_ADMIN_TOKEN from "
            "docker-compose.override.yml."
        )
        raise SystemExit(msg)
    return InfrahubClient(
        config=Config(
            address=os.environ.get("INFRAHUB_ADDRESS", "http://localhost:8000"),
            api_token=token,
            default_branch=branch,
        )
    )


async def _pre(client: InfrahubClient, branch: str, apply: bool, reverse: bool = False) -> int:
    """Renames, and the one deletion that must precede the object load.

    `reverse` is the rollback: it renames back, and nothing more. Loading the
    PREVIOUS commit's seed files afterwards recreates `br-branch` and moves the
    branch LAN address back onto it; `irb0` and the three bridged ports remain
    as unaddressed extras, which frr_config never reads.
    """
    changes = 0
    verb = "renamed" if apply else "would rename"
    rename = frr_name if reverse else srl_name
    group_from, group_to = (NEW_GROUP, OLD_GROUP) if reverse else (OLD_GROUP, NEW_GROUP)

    for kind in ("InterfacePhysical", "InterfaceVirtual"):
        for router in ROUTERS:
            for intf in await client.filters(kind=kind, device__name__value=router, branch=branch):
                old = str(_value(intf.name))
                if not reverse and kind == "InterfacePhysical" and router == "branch-rtr" and old == "br-branch":
                    changes += 1
                    if apply:
                        await intf.delete()
                    print(f"  {'deleted' if apply else 'would delete'} {router} {old} (succeeded by irb0)")
                    continue
                if reverse and router == "branch-rtr" and old in {"ethernet-1/2", "ethernet-1/3", "ethernet-1/4"}:
                    continue  # the bridged ports have no FRR-era name; they stay as extras
                new = rename(old)
                if new is None:
                    continue
                changes += 1
                if apply:
                    intf.name.value = new
                    await intf.save()
                print(f"  {verb} {kind} {router} {old} -> {new}")

    groups = await _named(client, "CoreStandardGroup", group_from, branch)
    existing = await _named(client, "CoreStandardGroup", group_to, branch)
    for group in groups:
        if existing:
            raise SystemExit(
                f"both {group_from} and {group_to} exist. Merge their members by hand before re-running: "
                "renaming would collide, and deleting either would orphan its artifacts."
            )
        changes += 1
        if apply:
            group.name.value = group_to
            await group.save()
        print(f"  {verb} group {group_from} -> {group_to} (members kept)")
    return changes


async def _delete_if_unreferenced(node: Any, label: str, references: list[str], apply: bool) -> int:
    for rel in references:
        manager = getattr(node, rel, None)
        if manager is None:
            continue
        await manager.fetch()
        if manager.peers:
            print(f"  kept {label}: {len(manager.peers)} {rel} still reference it")
            return 0
    if apply:
        await node.delete()
    print(f"  {'deleted' if apply else 'would delete'} {label}")
    return 1


async def _post(client: InfrahubClient, branch: str, apply: bool) -> int:
    """Remove what the FRR era left behind, once nothing points at it."""
    changes = 0
    for artifact in await _named(client, "CoreArtifact", OLD_ARTIFACT, branch):
        changes += 1
        if apply:
            await artifact.delete()
        print(f"  {'deleted' if apply else 'would delete'} artifact {OLD_ARTIFACT} {artifact.id}")
    for definition in await _named(client, "CoreArtifactDefinition", OLD_ARTIFACT_DEFINITION, branch):
        changes += await _delete_if_unreferenced(
            definition, f"artifact definition {OLD_ARTIFACT_DEFINITION}", [], apply
        )
    for device_type in await _named(client, "DcimDeviceType", OLD_DEVICE_TYPE, branch):
        # DcimDeviceType declares no reverse relationship to its devices, so they
        # are found from the device side.
        users = await client.filters(kind="DcimPhysicalDevice", device_type__name__value=OLD_DEVICE_TYPE, branch=branch)
        if users:
            print(f"  kept device type {OLD_DEVICE_TYPE}: {len(users)} device(s) still use it")
        else:
            changes += await _delete_if_unreferenced(device_type, f"device type {OLD_DEVICE_TYPE}", [], apply)
    for platform in await _named(client, "DcimPlatform", OLD_PLATFORM, branch):
        changes += await _delete_if_unreferenced(platform, f"platform {OLD_PLATFORM}", ["devices"], apply)
    for manufacturer in await _named(client, "OrganizationManufacturer", OLD_MANUFACTURER, branch):
        changes += await _delete_if_unreferenced(
            manufacturer, f"manufacturer {OLD_MANUFACTURER}", ["device_type", "platform"], apply
        )
    return changes


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--branch", required=True, help="branch to migrate")
    parser.add_argument(
        "--phase",
        choices=("pre", "post"),
        default="pre",
        help="pre: renames, before the object load (default). post: cleanup, after it.",
    )
    parser.add_argument("--apply", action="store_true", help="write the changes; without it the script only reports")
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="rollback: rename back to the FRR-era names (pre phase only), then load the previous seed files",
    )
    args = parser.parse_args()
    if args.reverse and args.phase != "pre":
        parser.error("--reverse applies to the pre phase only; the post phase deletes, and is not undone")

    client = _client(args.branch)
    direction = " (reverse)" if args.reverse else ""
    print(f"{args.phase} phase{direction} on branch {args.branch}{'' if args.apply else ' (report only)'}")
    if args.phase == "pre":
        changes = await _pre(client, args.branch, args.apply, reverse=args.reverse)
    else:
        changes = await _post(client, args.branch, args.apply)
    if not changes:
        print("  nothing to do -- already migrated")
    elif not args.apply:
        print(f"\n{changes} change(s) pending. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

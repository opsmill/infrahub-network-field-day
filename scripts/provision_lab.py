"""Push Infrahub-rendered configuration onto the running ContainerLab devices.

The lab comes up with management connectivity and nothing else -- the cEOS nodes
in `../lab/otternet.clab.yml` are given no `startup-config`, only `CLAB_MGMT_VRF`
and a management address. This script is the second half: it fetches each
device's rendered artifact from Infrahub and makes the device match it, so the
running lab's configuration comes from the model rather than from a file
somebody edited.

**This file is the command; the work lives in
`solution_arista_avd.deployment.devices`.** Cycle 030 lifted it there so the
reconciler and this command drive the same code rather than two copies that
drift apart. The behaviour of the command is unchanged -- same flags, same
output, same exit statuses.

Usage:

    uv run python scripts/provision_lab.py                    # push everything
    uv run python scripts/provision_lab.py --dry-run          # show, change nothing
    uv run python scripts/provision_lab.py --only spine1      # one device
    uv run python scripts/provision_lab.py --kind eos         # one family
    uv run python scripts/provision_lab.py --branch my-change # from a branch

Normally invoked as `uv run invoke provision`.
"""

from __future__ import annotations

import argparse
import sys

import httpx

from solution_arista_avd.deployment.devices import (
    INFRAHUB_API_TOKEN,
    KINDS,
    ProvisionError,
    discover,
    provision,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--branch", default="", help="Infrahub branch to read artifacts from (default: main)")
    parser.add_argument("--dry-run", action="store_true", help="List what would be pushed, change nothing")
    parser.add_argument("--only", default="", help="Provision a single device by its Infrahub name")
    parser.add_argument("--kind", choices=sorted(KINDS), default="", help="Provision one device family only")
    args = parser.parse_args()

    if not INFRAHUB_API_TOKEN:
        print("INFRAHUB_API_TOKEN is not set; Infrahub will reject the artifact download.", file=sys.stderr)
        return 2

    try:
        targets = discover(args.branch)
    except (httpx.HTTPError, ProvisionError) as error:
        print(f"Could not read the artifact list from Infrahub: {error}", file=sys.stderr)
        return 2

    if args.kind:
        targets = [t for t in targets if t.artifact_name == KINDS[args.kind]]
    if args.only:
        targets = [t for t in targets if t.device == args.only]

    if not targets:
        print("Nothing to provision. Has `invoke avd` run, so the artifacts exist?", file=sys.stderr)
        return 1

    where = f"branch '{args.branch}'" if args.branch else "main"
    print(f"Provisioning {len(targets)} device(s) from {where}:")
    failures = provision(targets, args.branch, args.dry_run)

    if failures:
        print(f"\n{failures} of {len(targets)} device(s) failed.", file=sys.stderr)
        return 1
    if not args.dry_run:
        print(f"\nAll {len(targets)} device(s) now match Infrahub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

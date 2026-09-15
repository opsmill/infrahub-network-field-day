"""Run the deployment reconciler: one cycle, a dry run, or the loop.

The gap this closes is between a merge landing on `main` and the devices
matching it. Until now that gap was a human typing `uv run invoke provision`.

    uv run python scripts/reconcile.py --converge          # cycle until every device is confirmed
    uv run python scripts/reconcile.py --once              # one cycle, then stop
    uv run python scripts/reconcile.py --dry-run --branch X  # report, change nothing
    uv run python scripts/reconcile.py                     # the loop

Normally invoked as `uv run invoke reconcile`.

**The loop pushes without being asked**, including correcting drift someone
introduced by hand. Two controls bound that and both are deliberate: a device
whose `DeploymentState.suspend` is set is skipped entirely, and the interval has
a hard floor the service refuses to start below.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from infrahub_sdk import Config, InfrahubClient

from solution_arista_avd.deployment.devices import INFRAHUB_ADDRESS, INFRAHUB_API_TOKEN
from solution_arista_avd.deployment.reconcile import (
    DEFAULT_INTERVAL,
    ConfigurationError,
    converge,
    run_cycle,
    run_forever,
    validate_interval,
)


def _client() -> InfrahubClient:
    return InfrahubClient(address=INFRAHUB_ADDRESS, config=Config(api_token=INFRAHUB_API_TOKEN))


async def _run(args: argparse.Namespace) -> int:
    client = _client()

    if args.dry_run:
        report = await run_cycle(client, branch=args.branch, dry_run=True)
        where = f"branch '{args.branch}'" if args.branch else "main"
        print(f"Dry run against {where}: {report.summary()}")
        for device in report.differed:
            print(f"  differs  {device}")
        if not report.differed:
            print("  every device already matches its rendered configuration")
        print("\nNothing was pushed and no deployment state was written.")
        return 0

    if args.converge:
        report = await converge(client)
        unconfirmed = sorted(set(report.differed) | set(report.failed))
        if unconfirmed:
            print(f"Did not converge. Unconfirmed: {', '.join(unconfirmed)}")
            return 1
        print(f"Converged: {report.summary()}")
        print("Every device is confirmed to match its rendered configuration.")
        return 0

    if args.once:
        report = await run_cycle(client)
        print(f"Cycle complete: {report.summary()}")
        return 1 if report.failed else 0

    await run_forever(client, args.interval)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true", help="Run a single cycle and stop")
    parser.add_argument(
        "--converge",
        action="store_true",
        help="Cycle until every device is confirmed, then stop. Used to bootstrap a cold fabric.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report differences, change nothing")
    parser.add_argument("--branch", default="", help="Compare against this branch (dry run only)")
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("NFD41_RECONCILE_INTERVAL", str(DEFAULT_INTERVAL))),
        help=f"Seconds between cycles (default {DEFAULT_INTERVAL})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if not INFRAHUB_API_TOKEN:
        print("INFRAHUB_API_TOKEN is not set; Infrahub will reject the artifact download.", file=sys.stderr)
        return 2

    if args.branch and not args.dry_run:
        print("--branch is only valid with --dry-run: deploys happen on main only.", file=sys.stderr)
        return 2

    try:
        validate_interval(args.interval)
    except ConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 2

    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())

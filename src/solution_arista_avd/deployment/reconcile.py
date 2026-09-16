"""The cycle: compare every device, push the ones that differ, record what happened.

One loop, no internal concurrency. The design review's conclusion was that a
600-second loop *is* the retry -- every push is a replace and the next cycle
recomputes the difference from scratch -- so there is nothing here to schedule,
resume or queue.

Four things about the shape of a cycle, each of which was a decision rather than
a default:

1. **It sweeps before it works.** `try/finally` does not survive SIGKILL, which
   is how a container is stopped, so a cycle cannot rely on its predecessor
   having tidied up. EOS holds a finite number of configuration sessions; a
   comparator that dies often enough removes the ability to deploy at all.
2. **The firewall is checked on one cycle in four, and last.** Comparing it
   takes an exclusive configuration lock, and at the default interval a
   per-cycle check would take that lock 144 times a day on the device someone
   needs during an incident.
3. **Suspension is read before the device is reached.** A suspended device is
   never connected to, and its record is left exactly as it was -- a moving
   timestamp on a device nobody looked at would be a lie.
4. **Cycles do not overlap.** A sequential loop cannot overlap itself; the
   interval is measured from the end of one cycle, so a slow cycle delays the
   next rather than stacking against it.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from solution_arista_avd.deployment import compare as cmp
from solution_arista_avd.deployment import devices as dv
from solution_arista_avd.deployment import inventory as inv
from solution_arista_avd.deployment.state import (
    STATUS_DRIFTED,
    STATUS_FAILED,
    STATUS_IN_SYNC,
    STATUS_PENDING,
    Outcome,
    StateStore,
)

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

log = logging.getLogger("infrahub.reconcile")

DEFAULT_INTERVAL = 600
"""Matches Vidra's `requeueResourcesAfter`, so both reconcilers in the
environment drift at the same rate and an operator learns one number."""

MINIMUM_INTERVAL = 60
"""A floor, enforced by refusing to start rather than by clamping. Comparing
takes locks and leaves state on devices; a tight loop turns that into a denial
of service against the fabric's own control plane."""

FIREWALL_EVERY = 4
"""Cycles between firewall comparisons. Its comparison takes an exclusive lock."""


class ConfigurationError(ValueError):
    """The service was asked to run in a way that is not safe."""


@dataclass
class CycleReport:
    """What one cycle did. This is what gets logged (FR-060)."""

    compared: list[str] = field(default_factory=list)
    differed: list[str] = field(default_factory=list)
    pushed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    suspended: list[str] = field(default_factory=list)
    not_due: list[str] = field(default_factory=list)
    swept: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"compared={len(self.compared)} differed={len(self.differed)} "
            f"pushed={len(self.pushed)} failed={len(self.failed)} "
            f"suspended={len(self.suspended)} not-due={len(self.not_due)}"
        )


def validate_interval(seconds: int) -> int:
    """Refuse an unsafe interval instead of quietly correcting it.

    Clamping would mean an operator who set 5 seconds gets 60 and never learns
    the number they chose was rejected.
    """
    if seconds < MINIMUM_INTERVAL:
        raise ConfigurationError(
            f"interval {seconds}s is below the {MINIMUM_INTERVAL}s floor. Comparing takes "
            "configuration locks on the devices; a tighter loop would hold them continuously."
        )
    return seconds


def _due(target: dv.Target, cycle: int) -> bool:
    """Whether this device is compared on this cycle."""
    if target.artifact_name == dv.ARTIFACT_JUNOS:
        return cycle % FIREWALL_EVERY == 0
    return True


def _order(targets: list[dv.Target]) -> list[dv.Target]:
    """Firewall last, so a held lock outlives as little of the cycle as possible."""
    return sorted(targets, key=lambda t: t.artifact_name == dv.ARTIFACT_JUNOS)


def sweep(targets: list[dv.Target]) -> list[str]:
    """Clear this service's own leftovers from a previous cycle."""
    cleared: list[str] = []
    for target in targets:
        try:
            if target.artifact_name == dv.ARTIFACT_EOS:
                cleared.extend(f"{target.device}:{name}" for name in cmp.sweep_eos(target))
            elif target.artifact_name == dv.ARTIFACT_JUNOS and cmp.sweep_junos(target):
                cleared.append(f"{target.device}:lock")
        except Exception as error:  # noqa: BLE001 - a failed sweep must not stop the cycle
            log.warning("sweep failed for %s: %s", target.device, error)
    return cleared


async def run_cycle(
    client: InfrahubClient,
    cycle: int = 0,
    *,
    branch: str = "",
    dry_run: bool = False,
    all_due: bool = False,
) -> CycleReport:
    """One pass over the fabric.

    `dry_run` reports differences and writes nothing -- not to a device and not
    to Infrahub. Deployment state is a fact about `main`, so a comparison
    against a branch must not leave a trace.
    """
    report = CycleReport()
    store = StateStore(client)
    targets = _order(dv.discover(branch))

    if not dry_run:
        report.swept = sweep(targets)

    # Device work runs through Nornir: the fabric in parallel, the firewall on
    # its own afterwards because comparing it takes an exclusive lock.
    #
    # NOTHING in a Nornir task touches Infrahub. Its hosts run in a
    # ThreadPoolExecutor while the SDK's client context is a contextvar bound to
    # the async task, so a write from inside one would need that context
    # hand-propagated into worker threads -- which the design review measured
    # and recorded as not surviving contact. The tasks return plain data and the
    # state writes happen below, sequentially, in this coroutine.
    by_name = {t.device: t for t in targets}
    due = {name: t for name, t in by_name.items() if all_due or _due(t, cycle)}
    report.not_due = sorted(set(by_name) - set(due))

    suspended: set[str] = set()
    if not dry_run:
        for name in due:
            if await store.is_suspended(name):
                suspended.add(name)
    report.suspended = sorted(suspended)
    runnable = {name: t for name, t in due.items() if name not in suspended}

    fabric, firewalls = inv.split_firewalls(inv.build_inventory(branch))
    outcomes = inv.run_over(fabric, runnable, branch=branch, dry_run=dry_run)
    outcomes += inv.run_over(firewalls, runnable, branch=branch, dry_run=dry_run)

    for outcome in sorted(outcomes, key=lambda o: o.device):
        if outcome.failed:
            log.error("device %s failed: %s", outcome.device, outcome.error)
            report.failed.append(outcome.device)
            if not dry_run:
                await store.record(Outcome(device=outcome.device, status=STATUS_FAILED, error=outcome.error))
            continue

        report.compared.append(outcome.device)

        if not outcome.differs:
            if not dry_run:
                await store.record(
                    Outcome(
                        device=outcome.device,
                        status=STATUS_IN_SYNC,
                        confirmed=True,
                        checksum=outcome.checksum,
                    )
                )
            continue

        report.differed.append(outcome.device)
        if dry_run:
            continue

        # `pending` vs `drifted` is the ONLY use of the artifact checksum in this
        # design. It does not decide whether to push -- the device's own diff did
        # that -- it records which of two structurally different causes applies.
        previous = await store.last_checksum(outcome.device)
        status = STATUS_PENDING if previous is not None and previous != outcome.checksum else STATUS_DRIFTED

        if outcome.pushed:
            report.pushed.append(outcome.device)
        await store.record(
            Outcome(
                device=outcome.device,
                status=status,
                diff=outcome.diff,
                pushed=outcome.pushed,
                checksum=outcome.checksum,
            )
        )

    if not dry_run:
        await store.sweep_orphans({t.device for t in targets})

    log.info("cycle %s: %s", cycle, report.summary())
    return report


async def run_forever(client: InfrahubClient, interval: int = DEFAULT_INTERVAL) -> None:
    """The service. Refuses to start below the floor."""
    validate_interval(interval)
    log.info("reconciler starting: interval=%ss firewall every %s cycles", interval, FIREWALL_EVERY)
    cycle = 0
    while True:
        try:
            await run_cycle(client, cycle)
        except Exception:
            log.exception("cycle %s failed entirely", cycle)
        cycle += 1
        # Measured from the end of the cycle, so a slow cycle delays the next one
        # rather than stacking against it.
        await asyncio.sleep(interval)


MAX_CONVERGE_CYCLES = 6


async def converge(client: InfrahubClient, max_cycles: int = MAX_CONVERGE_CYCLES) -> CycleReport:
    """Reconcile repeatedly until every device is confirmed, or give up loudly.

    Bootstrapping is the case a single cycle cannot serve. A cold device differs,
    so the first cycle **pushes** it -- and `last_confirmed_at` deliberately does
    not move on a push. Confirmation needs a second comparison that finds no
    difference. One cycle therefore leaves a freshly built fabric correct but
    unconfirmed, which is exactly the ambiguity this model exists to remove.

    Every device is compared on every cycle here, firewall included: the
    one-in-four cadence is a steady-state economy, and during a build the
    exclusive lock costs nothing because nobody else is using the box.
    """
    report = CycleReport()
    for cycle in range(max_cycles):
        report = await run_cycle(client, cycle, all_due=True)
        log.info("converge cycle %s: %s", cycle, report.summary())
        if not report.differed and not report.failed:
            log.info("converged after %s cycle(s): every device confirmed", cycle + 1)
            return report
    log.error(
        "did not converge in %s cycles: differed=%s failed=%s",
        max_cycles,
        report.differed,
        report.failed,
    )
    return report

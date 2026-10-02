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

**The interval is a maximum, not a fixed sleep.** Between cycles the loop polls
the artifacts' checksums and starts early once a moved set has held still (see
`wake`), and a cycle that pushed is followed by one confirming comparison after
`CONFIRM_DELAY` rather than a whole interval later. Neither changes what a cycle
decides: confirmation still needs a comparison that finds no difference, and the
firewall's one-in-N cadence counts only the interval's own cycles -- an early
cycle compares the firewall only when the firewall's own intent moved, or it was
just pushed.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from solution_arista_avd.deployment import compare as cmp
from solution_arista_avd.deployment import devices as dv
from solution_arista_avd.deployment import inventory as inv
from solution_arista_avd.deployment import wake
from solution_arista_avd.deployment.state import (
    STATUS_DRIFTED,
    STATUS_FAILED,
    STATUS_IN_SYNC,
    STATUS_PENDING,
    Outcome,
    StateStore,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Collection

    from infrahub_sdk import InfrahubClient

log = logging.getLogger("infrahub.reconcile")

DEFAULT_INTERVAL = 600
"""Matches Vidra's `requeueResourcesAfter`, so both reconcilers in the
environment drift at the same rate and an operator learns one number."""

MINIMUM_INTERVAL = 60
"""A floor, enforced by refusing to start rather than by clamping. Comparing
takes locks and leaves state on devices; a tight loop turns that into a denial
of service against the fabric's own control plane."""

FIREWALL_EVERY = int(os.getenv("OTTERNET_RECONCILE_FIREWALL_EVERY", "4"))
"""Cycles between firewall comparisons. Its comparison takes an exclusive lock.

Tunable because the default is a steady-state economy, not a correctness bound:
one in four keeps the vSRX's exclusive lock out of the way of anybody using the
box. During a demo nobody else is using it and the firewall is the payoff, so
`OTTERNET_RECONCILE_FIREWALL_EVERY=1` compares it every cycle."""


CONFIRM_DELAY = MINIMUM_INTERVAL
"""After a cycle that pushed, the next one -- comparing what was pushed -- is
due this soon rather than a whole interval later, because `last_confirmed_at`
only moves on a comparison that finds no difference. It is the floor, so it
never compares more often than the loop is allowed to, and a device gets it once
per push: one that is pushed again by the confirming cycle waits for the
interval like any other, rather than being pushed every minute."""


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
    # The checksums this cycle read: the baseline the wait between cycles
    # compares against, so intent that moves DURING a cycle still wakes the next.
    checksums: wake.Snapshot = field(default_factory=dict)

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


def validate_poll(seconds: float) -> float:
    """Refuse a checksum poll tighter than its floor, for the interval's reason."""
    if seconds < wake.MINIMUM_POLL:
        raise ConfigurationError(f"poll {seconds}s is below the {wake.MINIMUM_POLL}s floor")
    return seconds


def _due(
    target: dv.Target,
    cycle: int,
    force: Collection[str] = (),
    *,
    scheduled: bool = True,
) -> bool:
    """Whether this device is compared on this cycle.

    `force` names devices whose intent moved or that were just pushed; they are
    compared whatever the cadence says. `scheduled` is False for a cycle the
    interval did not start, which never takes the firewall's lock on its own
    account.
    """
    if target.device in force:
        return True
    if target.artifact_name == dv.ARTIFACT_JUNOS:
        return scheduled and cycle % FIREWALL_EVERY == 0
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
            elif target.artifact_name == dv.ARTIFACT_SRL:
                cleared.extend(f"{target.device}:{name}" for name in cmp.sweep_srl(target))
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
    force: Collection[str] = (),
    scheduled: bool = True,
) -> CycleReport:
    """One pass over the fabric.

    `dry_run` reports differences and writes nothing -- not to a device and not
    to Infrahub. Deployment state is a fact about `main`, so a comparison
    against a branch must not leave a trace.
    """
    report = CycleReport()
    store = StateStore(client)
    targets = _order(dv.discover(branch))
    report.checksums = wake.snapshot(targets)

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
    due = {name: t for name, t in by_name.items() if all_due or _due(t, cycle, force, scheduled=scheduled)}
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


def _observe() -> wake.Snapshot:
    """The poll between cycles: the cycle's own discovery query, nothing more."""
    return wake.snapshot(dv.discover())


def _cycle_arguments(reason: wake.Wake, follow_up: frozenset[str]) -> tuple[bool, dict[str, Any]]:
    """Whether a cycle counts towards the cadence, and what it compares.

    * the interval (or the first cycle) with nothing to confirm: everything the
      cadence makes due, and only these advance the firewall's one-in-N count;
    * artifacts that moved and held still: the fabric, plus the devices whose
      intent moved, so a firewall change is compared without waiting its turn;
    * the confirmation after a push: the fabric, plus the pushed devices;
    * a request (`invoke reconcile --now`): every device, firewall included.
    """
    if reason.reason == wake.WAKE_REQUESTED:
        return False, {"all_due": True}
    scheduled = reason.reason in {wake.WAKE_START, wake.WAKE_INTERVAL} and not follow_up
    return scheduled, {"force": frozenset(reason.moved | follow_up), "scheduled": scheduled}


async def run_forever(
    client: InfrahubClient,
    interval: int = DEFAULT_INTERVAL,
    *,
    poll_seconds: float = wake.POLL_SECONDS,
    observe: Callable[[], wake.Snapshot] = _observe,
    trigger: Callable[[], bool] | None = None,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
    cycle_fn: Callable[..., Awaitable[CycleReport]] = run_cycle,
    max_cycles: int | None = None,
) -> None:
    """The service. Refuses to start below either floor.

    `max_cycles` exists for the tests; the service passes None and never returns.
    """
    validate_interval(interval)
    validate_poll(poll_seconds)
    if trigger is None:
        trigger = wake.FileTrigger().consume
    # A request left from before this process started is answered by the first
    # cycle, which runs now anyway.
    trigger()
    log.info(
        "reconciler starting: interval=%ss (the maximum) poll=%ss firewall every %s cycles",
        interval,
        poll_seconds,
        FIREWALL_EVERY,
    )

    scheduled_cycles = 0  # interval-started cycles, which alone drive the firewall's cadence
    ran = 0
    reason = wake.Wake(wake.WAKE_START)
    follow_up: frozenset[str] = frozenset()  # pushed last cycle, awaiting a confirming comparison
    while max_cycles is None or ran < max_cycles:
        scheduled, arguments = _cycle_arguments(reason, follow_up)
        label = "confirmation" if follow_up and reason.reason == wake.WAKE_INTERVAL else reason.reason
        moved_note = f", intent moved on {', '.join(sorted(reason.moved))}" if reason.moved else ""
        log.info("starting cycle %s (%s%s)", scheduled_cycles, label, moved_note)

        report: CycleReport | None = None
        try:
            report = await cycle_fn(client, scheduled_cycles, **arguments)
        except Exception:
            log.exception("cycle %s failed entirely", scheduled_cycles)
        ran += 1
        if scheduled:
            scheduled_cycles += 1

        baseline: wake.Snapshot | None
        if report is not None:
            baseline = report.checksums
        else:
            try:
                baseline = observe()
            except Exception:  # noqa: BLE001 - the wait copes with no baseline
                baseline = None

        # Each push earns ONE early confirmation. A device pushed again by the
        # cycle that was confirming it waits for the interval.
        follow_up = frozenset(report.pushed) - follow_up if report is not None else frozenset()
        if max_cycles is not None and ran >= max_cycles:
            return

        # Measured from the end of the cycle, so a slow cycle delays the next one
        # rather than stacking against it.
        reason = await wake.wait_for_wake(
            baseline,
            CONFIRM_DELAY if follow_up else interval,
            observe=observe,
            trigger=trigger,
            sleep=sleep,
            clock=clock,
            poll_seconds=poll_seconds,
        )


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

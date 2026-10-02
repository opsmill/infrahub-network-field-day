"""When the loop starts its next cycle: the interval, or sooner when intent moved.

The loop used to sleep its whole interval between cycles, so a merge landed and
then nothing happened for up to that long -- two minutes at demo cadence, ten in
steady state -- and confirmation took a second interval on top. The interval is
still the **maximum**. Between cycles the loop now polls the one thing a cycle
acts on, the configuration artifacts' checksums on `main`, with the same
discovery query the cycle itself runs, and starts early when they move.

Three rules shape the wait, and each is a lesson already paid for elsewhere:

1. **A checksum that moved is not yet one to act on.** A merge re-renders the
   artifacts one after another, so the first poll after it sees some moved and
   others not yet. Waking on the first movement would compare the devices
   against a half-rendered fabric. The moved set must be observed unchanged on
   `STABLE_POLLS` consecutive polls, and any further movement resets the count
   -- the same rule as `tasks.py::_wait_for_artifacts`.
2. **The wake only ever fires on movement away from what the last cycle read.**
   `_wait_for_artifacts` learned that two agreeing samples can agree on the OLD
   checksums when the render has not begun. That cannot wake this loop early: a
   snapshot equal to the baseline is "nothing happened", and the full interval
   still applies. The worst case is the old behaviour, never a stale push.
3. **A render still moving at the deadline holds the cycle, but not forever.**
   `SETTLE_LIMIT` bounds it, so a fabric that keeps re-rendering cannot starve
   the drift check the interval exists for.

An empty artifact is still refused where it always was, in
`compare.read_intent`. Nothing here decides what to push or what counts as
confirmed; it decides only *when* the next cycle looks.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

    from solution_arista_avd.deployment.devices import Target

log = logging.getLogger("infrahub.reconcile")

Snapshot = dict[tuple[str, str], str]
"""(artifact name, device) -> checksum, for every configuration artifact."""

POLL_SECONDS = int(os.getenv("OTTERNET_RECONCILE_POLL", "10"))
"""Seconds between checksum polls. One GraphQL query over fourteen artifacts;
nothing reaches a device."""

MINIMUM_POLL = 5
"""A floor for the poll, refused rather than clamped like the interval's."""

STABLE_POLLS = 2
"""Consecutive polls that must see the same moved snapshot before it is acted on."""

SETTLE_LIMIT = 300
"""Seconds past the deadline a still-moving render may hold the next cycle."""

TICK = 1.0
"""How often the wait checks the trigger file and the clock."""

TRIGGER_PATH = Path(os.getenv("OTTERNET_RECONCILE_TRIGGER", "/tmp/otternet-reconcile-now"))  # noqa: S108
"""Touch this file and the loop starts a cycle within `TICK`. `invoke reconcile
--now` touches it inside the container; the loop deletes it when it acts."""

WAKE_START = "start"
WAKE_INTERVAL = "interval"
WAKE_ARTIFACTS = "artifacts"
WAKE_REQUESTED = "requested"


@dataclass(frozen=True)
class Wake:
    """Why the next cycle starts, and which devices' intent moved."""

    reason: str
    moved: frozenset[str] = field(default_factory=frozenset)


def snapshot(targets: Iterable[Target]) -> Snapshot:
    """The checksums a cycle acts on, keyed so an added or removed artifact counts."""
    return {(t.artifact_name, t.device): t.checksum for t in targets}


def moved(before: Snapshot, after: Snapshot) -> frozenset[str]:
    """Devices whose artifact appeared, disappeared or changed checksum."""
    return frozenset(key[1] for key in set(before) | set(after) if before.get(key) != after.get(key))


class FileTrigger:
    """A request for an immediate cycle, made from outside the process."""

    def __init__(self, path: Path = TRIGGER_PATH) -> None:
        self.path = path

    def request(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch()

    def consume(self) -> bool:
        """True once per request: the file is removed as it is read."""
        try:
            self.path.unlink()
        except FileNotFoundError:
            return False
        return True


async def wait_for_wake(
    baseline: Snapshot | None,
    delay: float,
    *,
    observe: Callable[[], Snapshot],
    trigger: Callable[[], bool],
    sleep: Callable[[float], Awaitable[object]],
    clock: Callable[[], float],
    poll_seconds: float = POLL_SECONDS,
    stable_polls: int = STABLE_POLLS,
    settle_limit: float = SETTLE_LIMIT,
) -> Wake:
    """Block until the next cycle is due, and say why.

    `baseline` is what the previous cycle read; `None` when it could not read
    anything, in which case the first successful poll becomes the baseline and
    only the deadline or a request can wake the loop.
    """
    start = clock()
    deadline = start + delay
    hard_deadline = deadline + settle_limit
    next_poll = start + poll_seconds
    pending: Snapshot | None = None  # a snapshot that moved and has not yet held still
    agreeing = 0

    while True:
        now = clock()
        if trigger():
            return Wake(WAKE_REQUESTED)

        # Poll BEFORE judging the deadline, so a render that began just before
        # it is seen and holds the cycle rather than being compared half-done.
        if now >= next_poll:
            next_poll = now + poll_seconds
            try:
                current: Snapshot | None = observe()
            except Exception as error:  # noqa: BLE001 - a failed poll must not stop the loop
                log.warning("checksum poll failed: %s", error)
                current = None
            if current is not None:
                if baseline is None:
                    baseline = current
                elif current == baseline:
                    # Moved and moved back, or never moved: nothing to act on.
                    pending, agreeing = None, 0
                elif current == pending:
                    agreeing += 1
                else:
                    pending, agreeing = current, 1
                if pending is not None and agreeing >= stable_polls:
                    return Wake(WAKE_ARTIFACTS, moved(baseline, pending))

        if now >= deadline and (pending is None or now >= hard_deadline):
            if pending is not None and baseline is not None:
                log.warning("artifacts still moving %ss past the deadline; cycling anyway", int(now - deadline))
                return Wake(WAKE_INTERVAL, moved(baseline, pending))
            return Wake(WAKE_INTERVAL)

        await sleep(TICK)

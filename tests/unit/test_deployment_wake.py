"""Tests for when the loop starts its next cycle.

The interval used to be a fixed sleep, so a merge waited it out before any
device changed and a second one before confirmation. The loop now wakes early
when the artifacts it acts on move and hold still. Four properties matter, and
each has a test that fails if it is lost:

* **it wakes on a change** -- otherwise this is the old dead air;
* **it does not wake when nothing changed** -- otherwise it is a tight loop
  against the fabric's control plane, which the interval floor exists to refuse;
* **it does not wake while a render is still moving** -- otherwise it compares
  devices against a half-rendered fabric, the lesson `_wait_for_artifacts` paid
  for twice;
* **the interval is still honoured** as the maximum, and the firewall's cadence
  still counts only the interval's own cycles.

Every test runs on a fake clock: `sleep` advances it, nothing really waits.
"""

from __future__ import annotations

from operator import itemgetter
from typing import TYPE_CHECKING, Any

import pytest

from solution_arista_avd.deployment import devices as dv
from solution_arista_avd.deployment import wake
from solution_arista_avd.deployment.reconcile import (
    CONFIRM_DELAY,
    ConfigurationError,
    CycleReport,
    _due,  # noqa: PLC2701 - the cadence rule is part of what an early cycle must respect
    run_forever,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

LEAF = (dv.ARTIFACT_EOS, "leaf-1")
BORDER = (dv.ARTIFACT_EOS, "border-1")
FW = (dv.ARTIFACT_JUNOS, "fw1")
BASE: wake.Snapshot = {LEAF: "a", BORDER: "b", FW: "f"}


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept = 0.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        self.slept += seconds


class _Timeline:
    """What a poll returns at a given moment: the latest entry at or before it."""

    def __init__(self, clock: _Clock, steps: list[tuple[float, wake.Snapshot]]) -> None:
        self.clock = clock
        self.steps = sorted(steps, key=itemgetter(0))
        self.polls: list[float] = []

    def __call__(self) -> wake.Snapshot:
        self.polls.append(self.clock.now)
        current = self.steps[0][1]
        for at, snap in self.steps:
            if at <= self.clock.now:
                current = snap
        return dict(current)


def _never() -> bool:
    return False


async def _wait(
    clock: _Clock,
    observe: Callable[[], wake.Snapshot],
    delay: float = 120,
    trigger: Callable[[], bool] = _never,
    baseline: wake.Snapshot | None = None,
) -> wake.Wake:
    return await wake.wait_for_wake(
        dict(BASE) if baseline is None else baseline,
        delay,
        observe=observe,
        trigger=trigger,
        sleep=clock.sleep,
        clock=clock,
        poll_seconds=10,
        stable_polls=2,
        settle_limit=300,
    )


class TestWakeOnChange:
    @pytest.mark.asyncio
    async def test_a_moved_checksum_wakes_the_loop_early(self) -> None:
        clock = _Clock()
        moved = {**BASE, BORDER: "b2", FW: "f2"}
        observe = _Timeline(clock, [(0, BASE), (25, moved)])

        result = await _wait(clock, observe)

        assert result.reason == wake.WAKE_ARTIFACTS
        assert result.moved == {"border-1", "fw1"}
        # First seen on the poll at 30, held still on the poll at 40.
        assert clock.now == pytest.approx(40)

    @pytest.mark.asyncio
    async def test_an_added_artifact_counts_as_moved(self) -> None:
        clock = _Clock()
        added = {**BASE, (dv.ARTIFACT_EOS, "leaf-new"): "n"}
        result = await _wait(clock, _Timeline(clock, [(0, added)]))
        assert result.reason == wake.WAKE_ARTIFACTS
        assert result.moved == {"leaf-new"}


class TestNoWakeWhenUnchanged:
    @pytest.mark.asyncio
    async def test_unchanged_checksums_wait_out_the_whole_interval(self) -> None:
        clock = _Clock()
        observe = _Timeline(clock, [(0, BASE)])

        result = await _wait(clock, observe, delay=120)

        assert result == wake.Wake(wake.WAKE_INTERVAL)
        assert clock.now == pytest.approx(120)
        # It did poll -- cheaply -- and every poll said "nothing happened".
        assert len(observe.polls) >= 10

    @pytest.mark.asyncio
    async def test_a_change_that_reverts_before_settling_does_not_wake(self) -> None:
        """Moved and moved back is nothing to act on."""
        clock = _Clock()
        observe = _Timeline(clock, [(0, BASE), (10, {**BASE, LEAF: "x"}), (20, BASE)])
        result = await _wait(clock, observe, delay=120)
        assert result.reason == wake.WAKE_INTERVAL

    @pytest.mark.asyncio
    async def test_a_failing_poll_falls_back_to_the_interval(self) -> None:
        clock = _Clock()

        def broken() -> wake.Snapshot:
            raise RuntimeError("infrahub is restarting")

        result = await _wait(clock, broken, delay=120)
        assert result.reason == wake.WAKE_INTERVAL
        assert clock.now == pytest.approx(120)

    @pytest.mark.asyncio
    async def test_with_no_baseline_the_first_poll_becomes_it(self) -> None:
        """After a cycle that failed entirely there is nothing to compare with;
        the first poll must not read as 'everything moved'."""
        clock = _Clock()
        result = await wake.wait_for_wake(
            None,
            120,
            observe=_Timeline(clock, [(0, BASE)]),
            trigger=_never,
            sleep=clock.sleep,
            clock=clock,
            poll_seconds=10,
        )
        assert result.reason == wake.WAKE_INTERVAL


class TestDebounceWhileMoving:
    @pytest.mark.asyncio
    async def test_it_waits_for_a_rolling_render_to_hold_still(self) -> None:
        """Artifacts re-render one after another after a merge. Waking on the
        first movement would compare against a half-rendered fabric."""
        clock = _Clock()
        steps = [
            (0, BASE),
            (5, {**BASE, LEAF: "a2"}),
            (15, {**BASE, LEAF: "a2", BORDER: "b2"}),
            (25, {**BASE, LEAF: "a2", BORDER: "b2", FW: "f2"}),
        ]
        result = await _wait(clock, _Timeline(clock, steps))

        assert result.reason == wake.WAKE_ARTIFACTS
        assert result.moved == {"leaf-1", "border-1", "fw1"}
        # Moving at 10, 20 and 30; held still only from 30 to 40.
        assert clock.now == pytest.approx(40)

    @pytest.mark.asyncio
    async def test_a_render_moving_at_the_deadline_holds_the_cycle(self) -> None:
        clock = _Clock()
        steps = [(0, BASE), (55, {**BASE, LEAF: "a2"}), (65, {**BASE, LEAF: "a3"})]
        result = await _wait(clock, _Timeline(clock, steps), delay=60)
        # Not at 60 mid-render: once a3 has held still, at 80.
        assert result.reason == wake.WAKE_ARTIFACTS
        assert clock.now == pytest.approx(80)

    @pytest.mark.asyncio
    async def test_a_render_that_never_settles_is_bounded(self) -> None:
        clock = _Clock()

        def churning() -> wake.Snapshot:
            return {**BASE, LEAF: str(clock.now)}

        result = await _wait(clock, churning, delay=60)
        assert result.reason == wake.WAKE_INTERVAL
        assert result.moved == {"leaf-1"}
        assert clock.now == pytest.approx(60 + 300)


class TestRequest:
    @pytest.mark.asyncio
    async def test_a_request_wakes_within_a_tick(self) -> None:
        clock = _Clock()
        result = await _wait(clock, _Timeline(clock, [(0, BASE)]), trigger=lambda: clock.now >= 33)
        assert result.reason == wake.WAKE_REQUESTED
        assert clock.now == pytest.approx(33)

    def test_the_file_trigger_is_consumed_once(self, tmp_path: Path) -> None:
        trigger = wake.FileTrigger(tmp_path / "now")
        assert trigger.consume() is False
        trigger.request()
        assert trigger.consume() is True
        assert trigger.consume() is False


class _FakeCycles:
    """Records how each cycle was asked to run, and replays reports."""

    def __init__(self, clock: _Clock, reports: list[CycleReport]) -> None:
        self.clock = clock
        self.reports = reports
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, _client: object, cycle: int, **kwargs: Any) -> CycleReport:
        self.calls.append({"at": self.clock.now, "cycle": cycle, **kwargs})
        report = self.reports.pop(0) if self.reports else CycleReport()
        if not report.checksums:
            report.checksums = dict(BASE)
        return report


async def _serve(clock: _Clock, observe: Callable[[], wake.Snapshot], cycles: _FakeCycles, count: int) -> None:
    await run_forever(
        object(),  # type: ignore[arg-type]
        120,
        poll_seconds=10,
        observe=observe,
        trigger=_never,
        sleep=clock.sleep,
        clock=clock,
        cycle_fn=cycles,
        max_cycles=count,
    )


class TestTheLoop:
    @pytest.mark.asyncio
    async def test_the_interval_is_still_honoured_when_nothing_moves(self) -> None:
        clock = _Clock()
        cycles = _FakeCycles(clock, [])
        await _serve(clock, _Timeline(clock, [(0, BASE)]), cycles, 3)
        assert [c["at"] for c in cycles.calls] == pytest.approx([0, 120, 240])
        assert all(c["scheduled"] for c in cycles.calls)
        assert [c["cycle"] for c in cycles.calls] == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_a_merge_starts_a_cycle_forcing_the_devices_it_moved(self) -> None:
        clock = _Clock()
        moved = {**BASE, FW: "f2"}
        cycles = _FakeCycles(clock, [CycleReport(), CycleReport(checksums=moved)])
        await _serve(clock, _Timeline(clock, [(0, BASE), (25, moved)]), cycles, 2)

        early = cycles.calls[1]
        assert early["at"] == pytest.approx(40)
        assert early["force"] == {"fw1"}
        # Not a cycle the interval started, so it does not advance the cadence.
        assert early["scheduled"] is False
        assert early["cycle"] == 1

    @pytest.mark.asyncio
    async def test_a_push_is_confirmed_after_the_floor_not_the_interval(self) -> None:
        clock = _Clock()
        cycles = _FakeCycles(clock, [CycleReport(pushed=["fw1", "border-1"]), CycleReport(), CycleReport()])
        await _serve(clock, _Timeline(clock, [(0, BASE)]), cycles, 3)

        confirm = cycles.calls[1]
        assert confirm["at"] == pytest.approx(CONFIRM_DELAY)
        assert confirm["force"] == {"fw1", "border-1"}
        assert confirm["scheduled"] is False
        # And then the interval again.
        assert cycles.calls[2]["at"] == pytest.approx(CONFIRM_DELAY + 120)
        assert cycles.calls[2]["scheduled"] is True

    @pytest.mark.asyncio
    async def test_a_device_pushed_again_while_confirming_waits_for_the_interval(self) -> None:
        """One early confirmation per push, never a push every minute."""
        clock = _Clock()
        cycles = _FakeCycles(clock, [CycleReport(pushed=["leaf-1"]), CycleReport(pushed=["leaf-1"])])
        await _serve(clock, _Timeline(clock, [(0, BASE)]), cycles, 3)
        assert cycles.calls[2]["at"] == pytest.approx(CONFIRM_DELAY + 120)

    @pytest.mark.asyncio
    async def test_a_request_compares_every_device(self) -> None:
        clock = _Clock()
        cycles = _FakeCycles(clock, [])
        await run_forever(
            object(),  # type: ignore[arg-type]
            120,
            poll_seconds=10,
            observe=_Timeline(clock, [(0, BASE)]),
            trigger=lambda: clock.now >= 7,
            sleep=clock.sleep,
            clock=clock,
            cycle_fn=cycles,
            max_cycles=2,
        )
        assert cycles.calls[1] == {"at": pytest.approx(7), "cycle": 1, "all_due": True}

    @pytest.mark.asyncio
    async def test_the_poll_has_a_floor(self) -> None:
        with pytest.raises(ConfigurationError):
            await run_forever(object(), 120, poll_seconds=1, max_cycles=1)  # type: ignore[arg-type]


class TestEarlyCyclesAndTheFirewallCadence:
    def _fw(self) -> dv.Target:
        return dv.Target(device="fw1", artifact_name=dv.ARTIFACT_JUNOS, artifact_id="i", status="Ready", mgmt_ip=None)

    def test_an_early_cycle_leaves_the_firewall_alone(self) -> None:
        """Its comparison takes an exclusive lock; waking early for a leaf's
        change must not take it on the firewall's behalf."""
        assert _due(self._fw(), 0, scheduled=False) is False

    def test_an_early_cycle_compares_the_firewall_when_its_intent_moved(self) -> None:
        assert _due(self._fw(), 1, {"fw1"}, scheduled=False) is True

    def test_the_scheduled_cadence_is_unchanged(self) -> None:
        assert _due(self._fw(), 0) is True

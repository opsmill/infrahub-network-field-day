"""Tests for the cycle's decisions and what it writes.

Three of these encode promises that are invisible until they are broken on a
real fabric:

* **`last_confirmed_at` moves only on a confirmed match.** If it moved on a
  push, the record would be a claim about what this service did rather than
  about the network, and the whole "confirmed, not sent" distinction from the
  design review would be lost.
* **A suspended device is not written to at all.** Not even its timestamp: a
  moving `last_checked_at` on a device nobody looked at is a lie, and the record
  must still show what the device was doing when someone took it out of the loop.
* **The interval floor is a refusal, not a clamp.** Silently correcting 5s to
  60s means an operator never learns their number was rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from solution_arista_avd.deployment import devices as dv
from solution_arista_avd.deployment.compare import Comparison
from solution_arista_avd.deployment.reconcile import (
    DEFAULT_INTERVAL,
    FIREWALL_EVERY,
    MINIMUM_INTERVAL,
    ConfigurationError,
    _due,  # noqa: PLC2701 - the cadence rules are the point of this file
    _order,  # noqa: PLC2701
    validate_interval,
)
from solution_arista_avd.deployment.state import (
    STATUS_DRIFTED,
    STATUS_IN_SYNC,
    STATUS_PENDING,
    Outcome,
    StateStore,
)


def _target(device: str, artifact: str, checksum: str = "abc") -> dv.Target:
    return dv.Target(
        device=device,
        artifact_name=artifact,
        artifact_id="i" * 32,
        status="Ready",
        mgmt_ip="172.20.41.21" if artifact == dv.ARTIFACT_EOS else None,
        checksum=checksum,
    )


@dataclass
class _FakeAttr:
    value: Any = None


class _FakeRecord:
    def __init__(self, **fields: Any) -> None:
        for name in (
            "name",
            "status",
            "last_confirmed_at",
            "last_checked_at",
            "last_attempt_at",
            "last_error",
            "last_artifact_checksum",
            "suspend",
        ):
            setattr(self, name, _FakeAttr(fields.get(name)))
        self.saved = False
        self.deleted = False

    async def save(self) -> None:
        self.saved = True

    async def delete(self) -> None:
        self.deleted = True


class _FakeClient:
    """Just enough SDK to see which fields a cycle writes."""

    def __init__(self, existing: dict[str, _FakeRecord] | None = None) -> None:
        self.existing = existing or {}
        self.created: list[dict[str, Any]] = []

    async def get(self, *, hfid: list[str], raise_when_missing: bool = True, **_: Any) -> Any:
        return self.existing.get(hfid[0])

    async def create(self, **kwargs: Any) -> _FakeRecord:
        self.created.append(kwargs)
        record = _FakeRecord(**kwargs)
        self.existing[kwargs["name"]] = record
        return record

    async def all(self, **_: Any) -> list[_FakeRecord]:
        return list(self.existing.values())


class TestIntervalFloor:
    def test_the_default_is_vidras_number(self) -> None:
        """Both reconcilers in the environment drift at the same rate, so an
        operator learns one number rather than two."""
        assert DEFAULT_INTERVAL == 600

    def test_the_default_is_accepted(self) -> None:
        assert validate_interval(DEFAULT_INTERVAL) == DEFAULT_INTERVAL

    def test_the_floor_itself_is_accepted(self) -> None:
        assert validate_interval(MINIMUM_INTERVAL) == MINIMUM_INTERVAL

    @pytest.mark.parametrize("seconds", [0, 1, 30, MINIMUM_INTERVAL - 1])
    def test_below_the_floor_is_refused_not_clamped(self, seconds: int) -> None:
        with pytest.raises(ConfigurationError) as error:
            validate_interval(seconds)
        assert str(MINIMUM_INTERVAL) in str(error.value)


class TestFirewallCadence:
    def test_the_firewall_is_compared_one_cycle_in_four(self) -> None:
        firewall = _target("fw1", dv.ARTIFACT_JUNOS)
        due = [cycle for cycle in range(12) if _due(firewall, cycle)]
        assert due == [0, 4, 8]

    def test_every_other_family_is_compared_every_cycle(self) -> None:
        for artifact in (dv.ARTIFACT_EOS, dv.ARTIFACT_FRR):
            target = _target("d", artifact)
            assert all(_due(target, cycle) for cycle in range(FIREWALL_EVERY * 2))

    def test_the_firewall_is_compared_last(self) -> None:
        """Its comparison holds an exclusive lock, so it should outlive as
        little of the cycle as possible."""
        targets = [
            _target("fw1", dv.ARTIFACT_JUNOS),
            _target("leaf-1", dv.ARTIFACT_EOS),
            _target("rtr-1", dv.ARTIFACT_FRR),
        ]
        assert _order(targets)[-1].device == "fw1"


class TestDiffersIsNormalised:
    def test_an_empty_normalised_result_means_in_sync(self) -> None:
        c = Comparison(target=_target("d", dv.ARTIFACT_FRR), raw="Lines To Add\nline vty\n", normalised=[])
        assert c.differs is False

    def test_raw_output_never_decides(self) -> None:
        """The raw text is non-empty for an in-sync FRR router and firewall."""
        c = Comparison(target=_target("d", dv.ARTIFACT_FRR), raw="", normalised=["ip route 1.2.3.0/24 Null0"])
        assert c.differs is True


class TestWhatGetsWritten:
    @pytest.mark.asyncio
    async def test_a_confirmed_match_moves_last_confirmed_at(self) -> None:
        client = _FakeClient()
        await StateStore(client).record(Outcome(device="leaf-1", status=STATUS_IN_SYNC, confirmed=True, checksum="abc"))
        written = client.created[0]
        assert written["status"] == STATUS_IN_SYNC
        assert written["last_confirmed_at"]
        assert written["last_checked_at"]
        assert written["last_artifact_checksum"] == "abc"

    @pytest.mark.asyncio
    async def test_a_push_does_not_move_last_confirmed_at(self) -> None:
        """ "Confirmed" means the device said it matched, never that we sent it
        something. This is the distinction the whole record exists to make."""
        client = _FakeClient()
        await StateStore(client).record(Outcome(device="leaf-1", status=STATUS_DRIFTED, pushed=True, checksum="abc"))
        written = client.created[0]
        assert "last_confirmed_at" not in written
        assert written["last_attempt_at"]
        assert written["last_checked_at"]

    @pytest.mark.asyncio
    async def test_a_failure_records_the_error_and_still_moves_last_checked_at(self) -> None:
        client = _FakeClient()
        await StateStore(client).record(Outcome(device="leaf-1", status="failed", error="boom"))
        written = client.created[0]
        assert written["last_error"] == "boom"
        assert written["last_checked_at"]
        assert "last_confirmed_at" not in written

    @pytest.mark.asyncio
    async def test_a_later_success_clears_the_previous_error(self) -> None:
        client = _FakeClient({"leaf-1": _FakeRecord(name="leaf-1", status="failed", last_error="boom")})
        await StateStore(client).record(Outcome(device="leaf-1", status=STATUS_IN_SYNC, confirmed=True))
        assert client.existing["leaf-1"].last_error.value is None

    @pytest.mark.asyncio
    async def test_an_existing_record_is_updated_not_duplicated(self) -> None:
        client = _FakeClient({"leaf-1": _FakeRecord(name="leaf-1", status=STATUS_IN_SYNC)})
        await StateStore(client).record(Outcome(device="leaf-1", status=STATUS_PENDING))
        assert client.created == []
        assert client.existing["leaf-1"].saved is True
        assert client.existing["leaf-1"].status.value == STATUS_PENDING


class TestSuspension:
    @pytest.mark.asyncio
    async def test_a_suspended_device_is_reported_suspended(self) -> None:
        client = _FakeClient({"fw1": _FakeRecord(name="fw1", suspend=True)})
        assert await StateStore(client).is_suspended("fw1") is True

    @pytest.mark.asyncio
    async def test_a_device_with_no_record_is_not_suspended(self) -> None:
        assert await StateStore(_FakeClient()).is_suspended("leaf-9") is False

    @pytest.mark.asyncio
    async def test_suspension_is_never_written_by_this_service(self) -> None:
        """The operator's field. A reconciler that can clear its own break-glass
        is not a break-glass."""
        client = _FakeClient()
        await StateStore(client).record(Outcome(device="fw1", status=STATUS_IN_SYNC, confirmed=True))
        assert "suspend" not in client.created[0]
        assert "suspend_reason" not in client.created[0]


class TestOrphanSweep:
    @pytest.mark.asyncio
    async def test_a_record_whose_device_is_gone_is_deleted(self) -> None:
        client = _FakeClient({"leaf-1": _FakeRecord(name="leaf-1"), "retired": _FakeRecord(name="retired")})
        removed = await StateStore(client).sweep_orphans({"leaf-1"})
        assert removed == ["retired"]
        assert client.existing["retired"].deleted is True
        assert client.existing["leaf-1"].deleted is False

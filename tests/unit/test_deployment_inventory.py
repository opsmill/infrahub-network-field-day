"""Tests for the Nornir layer, and for the boundary that makes it safe.

The load-bearing property here is not "does it run in parallel" — it is
**where the thread boundary sits**. Nornir runs hosts in a `ThreadPoolExecutor`;
the Infrahub SDK is async and its client context is a contextvar bound to the
running task. The design review measured this and recorded that a per-host
heartbeat written from inside a Nornir task "does not survive contact".

So the invariant is: a Nornir task does device I/O and returns plain data, and
nothing else. `test_the_nornir_layer_never_touches_infrahub` asserts that
structurally rather than by convention, because the failure it prevents is not a
crash — it is state writes that work on a developer's machine and drop silently
under concurrency.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from solution_arista_avd.deployment import devices as dv
from solution_arista_avd.deployment import inventory as inv

if TYPE_CHECKING:
    import pytest

MODULE = Path("src/solution_arista_avd/deployment/inventory.py")


def _target(device: str, artifact: str = dv.ARTIFACT_EOS, checksum: str = "c1") -> dv.Target:
    return dv.Target(
        device=device,
        artifact_name=artifact,
        artifact_id="i" * 32,
        status="Ready",
        mgmt_ip="172.20.41.21",
        checksum=checksum,
    )


@dataclass
class _FakeHost:
    name: str


class _FakeTask:
    def __init__(self, name: str) -> None:
        self.host = _FakeHost(name)


class _FakeComparison:
    def __init__(self, normalised: list[str]) -> None:
        self.normalised = normalised

    @property
    def differs(self) -> bool:
        return bool(self.normalised)


class TestTheThreadBoundary:
    def test_the_nornir_layer_never_touches_infrahub(self) -> None:
        """Structural, not conventional.

        A write from inside a worker thread would need the SDK's client context
        hand-propagated into it. Rather than trust a comment, this fails if the
        module ever imports the SDK or the state store.
        """
        tree = ast.parse((Path(__file__).resolve().parents[2] / MODULE).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        forbidden = {name for name in imported if "infrahub_sdk" in name or name.endswith("deployment.state")}
        assert not forbidden, (
            f"the Nornir layer must not reach Infrahub from a worker thread; found {sorted(forbidden)}"
        )

    def test_the_outcome_is_plain_data(self) -> None:
        """What crosses the thread boundary has to be inert."""
        outcome = inv.DeviceOutcome(device="leaf-1")
        assert (outcome.differs, outcome.pushed, outcome.failed, outcome.error) == (False, False, False, None)


class TestReconcileHost:
    def test_a_device_with_no_artifact_is_not_this_services_business(self) -> None:
        result = inv.reconcile_host(_FakeTask("some-server"), targets={}, branch="", dry_run=False)
        assert result.result is None

    def test_a_matching_device_is_not_pushed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(inv.cmp, "read_intent", lambda *_a, **_k: "config")
        monkeypatch.setattr(inv.cmp, "compare", lambda *_a: _FakeComparison([]))
        pushed: list[str] = []
        monkeypatch.setitem(dv.PUSHERS, dv.ARTIFACT_EOS, lambda t, _c: pushed.append(t.device))

        result = inv.reconcile_host(
            _FakeTask("leaf-1"), targets={"leaf-1": _target("leaf-1")}, branch="", dry_run=False
        )
        outcome: Any = result.result
        assert outcome.differs is False
        assert outcome.pushed is False
        assert pushed == []

    def test_a_differing_device_is_pushed_and_carries_its_diff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(inv.cmp, "read_intent", lambda *_a, **_k: "config")
        monkeypatch.setattr(inv.cmp, "compare", lambda *_a: _FakeComparison(["+ip host x 1.2.3.4"]))
        pushed: list[str] = []
        monkeypatch.setitem(dv.PUSHERS, dv.ARTIFACT_EOS, lambda t, _c: pushed.append(t.device))

        result = inv.reconcile_host(
            _FakeTask("leaf-1"), targets={"leaf-1": _target("leaf-1")}, branch="", dry_run=False
        )
        outcome: Any = result.result
        assert outcome.differs is True
        assert outcome.pushed is True
        assert "1.2.3.4" in outcome.diff
        assert pushed == ["leaf-1"]

    def test_a_dry_run_reports_the_difference_and_pushes_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(inv.cmp, "read_intent", lambda *_a, **_k: "config")
        monkeypatch.setattr(inv.cmp, "compare", lambda *_a: _FakeComparison(["+something"]))
        pushed: list[str] = []
        monkeypatch.setitem(dv.PUSHERS, dv.ARTIFACT_EOS, lambda t, _c: pushed.append(t.device))

        result = inv.reconcile_host(_FakeTask("leaf-1"), targets={"leaf-1": _target("leaf-1")}, branch="", dry_run=True)
        outcome: Any = result.result
        assert outcome.differs is True
        assert outcome.pushed is False
        assert pushed == []

    def test_a_failed_comparison_is_reported_against_its_device(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a: Any, **_k: Any) -> str:
            raise dv.ProvisionError("device unreachable")

        monkeypatch.setattr(inv.cmp, "read_intent", boom)
        result = inv.reconcile_host(
            _FakeTask("leaf-1"), targets={"leaf-1": _target("leaf-1")}, branch="", dry_run=False
        )
        outcome: Any = result.result
        assert outcome.failed is True
        assert "unreachable" in (outcome.error or "")

    def test_a_failed_push_still_records_the_difference(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The device differed, the push failed. Both facts matter: the next
        cycle retries, and the record must not read as in sync meanwhile."""
        monkeypatch.setattr(inv.cmp, "read_intent", lambda *_a, **_k: "config")
        monkeypatch.setattr(inv.cmp, "compare", lambda *_a: _FakeComparison(["+something"]))

        def boom(*_a: Any) -> str:
            raise dv.ProvisionError("eAPI rejected the configuration")

        monkeypatch.setitem(dv.PUSHERS, dv.ARTIFACT_EOS, boom)
        result = inv.reconcile_host(
            _FakeTask("leaf-1"), targets={"leaf-1": _target("leaf-1")}, branch="", dry_run=False
        )
        outcome: Any = result.result
        assert outcome.failed is True
        assert outcome.differs is True
        assert outcome.pushed is False


class TestGroups:
    def test_the_group_names_match_what_objects_seed(self) -> None:
        """`objects/00_groups.yml` is what makes the inventory group itself, so a
        rename there silently produces an inventory with no firewall filter."""
        seeded = (Path(__file__).resolve().parents[2] / "objects/00_groups.yml").read_text(encoding="utf-8")
        for group in (inv.GROUP_EOS, inv.GROUP_FRR, inv.GROUP_JUNOS):
            assert f"name: {group}" in seeded, f"{group} is not seeded in objects/00_groups.yml"

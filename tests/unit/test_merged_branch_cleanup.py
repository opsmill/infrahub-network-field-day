"""`invoke avd --merge` (and so `invoke bootstrap`) deletes the branch it merged.

Before this, every bootstrap left `build-fabric` behind: a branch whose whole
content was already on main, sitting in every branch picker and reading as work
in progress. The rules held here are the ones that make deleting it safe:

* it happens only after the merge AND the artifact wait returned;
* a branch already gone is skipped, so a re-run is harmless;
* when Infrahub cannot list branches the branch is left, never deleted on a guess;
* the default branch is never deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

import tasks


@dataclass
class _Result:
    stdout: str = ""


class _Ctx:
    """Records every command; raises on any command containing `fail_on`."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.commands: list[str] = []
        self.fail_on = fail_on

    def run(self, command: str, **_: Any) -> _Result:
        self.commands.append(command)
        if self.fail_on and self.fail_on in command:
            msg = f"simulated failure: {command}"
            raise RuntimeError(msg)
        return _Result()


def _deletes(ctx: _Ctx) -> list[str]:
    return [c for c in ctx.commands if c.startswith("infrahubctl branch delete")]


@pytest.fixture
def branches(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"value": {"main": True, "build-fabric": False}}
    monkeypatch.setattr(tasks, "_branches", lambda: state["value"])
    return state


def test_a_merged_branch_is_deleted(branches: dict[str, Any]) -> None:
    ctx = _Ctx()
    tasks._delete_merged_branch(ctx, "build-fabric")  # type: ignore[arg-type]

    assert _deletes(ctx) == ["infrahubctl branch delete build-fabric"]


def test_a_branch_already_gone_is_skipped(branches: dict[str, Any]) -> None:
    branches["value"] = {"main": True}
    ctx = _Ctx()
    tasks._delete_merged_branch(ctx, "build-fabric")  # type: ignore[arg-type]

    assert _deletes(ctx) == []


def test_an_unreachable_infrahub_leaves_the_branch(branches: dict[str, Any]) -> None:
    branches["value"] = None
    ctx = _Ctx()
    tasks._delete_merged_branch(ctx, "build-fabric")  # type: ignore[arg-type]

    assert _deletes(ctx) == []


def test_the_default_branch_is_never_deleted(branches: dict[str, Any]) -> None:
    branches["value"] = {"trunk": True}
    ctx = _Ctx()
    tasks._delete_merged_branch(ctx, "trunk")  # type: ignore[arg-type]

    assert _deletes(ctx) == []


def test_branches_reads_the_default_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tasks,
        "_graphql",
        lambda *_a, **_k: {"Branch": [{"name": "main", "is_default": True}, {"name": "b", "is_default": False}]},
    )
    assert tasks._branches() == {"main": True, "b": False}

    monkeypatch.setattr(tasks, "_graphql", lambda *_a, **_k: {})
    assert tasks._branches() is None


def _drive_avd(monkeypatch: pytest.MonkeyPatch, ctx: _Ctx, order: list[str]) -> None:
    monkeypatch.setattr(tasks, "_wait_for_artifacts", lambda _ctx: order.append("wait"))
    monkeypatch.setattr(tasks, "_delete_merged_branch", lambda _ctx, branch: order.append(f"delete {branch}"))
    tasks.avd.body(ctx, branch="build-fabric", artifacts=False, merge=True)  # type: ignore[arg-type]


def test_avd_merge_deletes_after_the_merge_and_the_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _Ctx()
    order: list[str] = []
    _drive_avd(monkeypatch, ctx, order)

    assert any(c.startswith("infrahubctl branch merge build-fabric") for c in ctx.commands)
    assert order == ["wait", "delete build-fabric"]


def test_a_failed_merge_deletes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _Ctx(fail_on="branch merge")
    order: list[str] = []
    with pytest.raises(RuntimeError):
        _drive_avd(monkeypatch, ctx, order)

    assert order == []


def test_avd_without_merge_keeps_the_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _Ctx()
    order: list[str] = []
    monkeypatch.setattr(tasks, "_delete_merged_branch", lambda _ctx, branch: order.append(f"delete {branch}"))
    tasks.avd.body(ctx, branch="review-me", artifacts=False, merge=False)  # type: ignore[arg-type]

    assert order == []

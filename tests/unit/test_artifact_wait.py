"""Unit tests for the artifact wait in `tasks.py`.

This function has been wrong twice, in the same way both times, and neither
failure raised anything -- so both are encoded here as tests rather than left
to a comment.

**What it is for.** Artifact generation is asynchronous: the REST endpoint
returns 200 and the rendering happens afterwards, and a merge kicks off another
round through Infrahub's branch-merge-post-process flow. `invoke provision` and
the reconciler read those artifacts, so returning too early means comparing a
device against output that predates the merge -- which reports no difference,
pushes nothing, and looks exactly like success.

**The two failures.** First the wait required only that every artifact be
non-empty, and an artifact still holding its pre-merge content is non-empty.
Then it required two consecutive agreeing checksum samples, and the two samples
agreed on the *old* checksums because the render had not begun ten seconds after
the merge. Both produced `compared=14 differed=0` with a just-deleted interface
still on both leaves.
"""

from __future__ import annotations

from typing import Any

import pytest

import tasks

ARTIFACT_NAME = "AVD EOS Configuration"


class _Response:
    def __init__(self, payload: dict[str, Any] | None = None, text: str = "config") -> None:
        self._payload = payload
        self.text = text

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload or {}


def _payload(checksums: dict[str, str]) -> dict[str, Any]:
    return {
        "data": {
            "CoreArtifact": {
                "edges": [
                    {"node": {"id": aid, "name": {"value": ARTIFACT_NAME}, "checksum": {"value": value}}}
                    for aid, value in checksums.items()
                ]
            }
        }
    }


@pytest.fixture
def _driver(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Drive the wait from a scripted list of checksum samples."""

    state: dict[str, Any] = {"samples": [], "index": 0, "slept": 0, "empty": False}

    def fake_post(*_args: Any, **_kwargs: Any) -> _Response:
        samples = state["samples"]
        index = min(state["index"], len(samples) - 1)
        state["index"] += 1
        return _Response(_payload(samples[index]))

    def fake_get(*_args: Any, **_kwargs: Any) -> _Response:
        return _Response(text="" if state["empty"] else "config")

    def fake_sleep(_seconds: float) -> None:
        state["slept"] += 1
        # A test that hung would be indistinguishable from a slow one.
        if state["slept"] > 100:
            msg = "the wait never returned"
            raise AssertionError(msg)

    monkeypatch.setattr(tasks.httpx, "post", fake_post)
    monkeypatch.setattr(tasks.httpx, "get", fake_get)
    monkeypatch.setattr(tasks, "sleep", fake_sleep)
    # A real deadline would make this test depend on wall-clock time.
    monkeypatch.setattr(tasks.time, "time", lambda: 0.0)
    return state


def test_one_quiet_interval_is_not_enough(_driver: Any, capsys: pytest.CaptureFixture[str]) -> None:
    """THE SECOND MEASURED FAILURE, as a test.

    Two samples agree on the pre-merge checksum, and only then does the render
    land. A wait satisfied by two agreeing samples returns on the stale pair --
    which is what left a deleted interface on both leaves while the reconciler
    reported no difference.
    """
    stale = {"a": "old"}
    fresh = {"a": "new"}
    _driver["samples"] = [stale, stale, fresh, *([fresh] * tasks.STABLE_SAMPLES)]

    tasks._wait_for_artifacts(None)  # type: ignore[arg-type]

    # It must not have stopped while the answer was still `old`.
    assert _driver["index"] > 3
    assert "populated and stable" in capsys.readouterr().out


def test_movement_resets_the_count(_driver: Any) -> None:
    """Any change restarts the window, so a render that arrives in instalments
    cannot be mistaken for a finished one."""
    churn = [{"a": str(n)} for n in range(tasks.STABLE_SAMPLES)]
    settled = [{"a": "final"}] * (tasks.STABLE_SAMPLES + 1)
    _driver["samples"] = [*churn, *settled]

    tasks._wait_for_artifacts(None)  # type: ignore[arg-type]

    # Every churning sample plus a full stable window after the last of them.
    assert _driver["index"] >= len(churn) + tasks.STABLE_SAMPLES


def test_a_stable_window_returns(_driver: Any, capsys: pytest.CaptureFixture[str]) -> None:
    """The positive case, without which the negatives above prove nothing."""
    _driver["samples"] = [{"a": "same"}] * (tasks.STABLE_SAMPLES + 2)

    tasks._wait_for_artifacts(None)  # type: ignore[arg-type]

    assert "populated and stable" in capsys.readouterr().out


def test_empty_artifacts_never_satisfy_it(_driver: Any, capsys: pytest.CaptureFixture[str]) -> None:
    """THE FIRST MEASURED FAILURE's other half.

    A stable checksum over an empty artifact is still empty, and pushing one
    would replace a switch's configuration with nothing.
    """
    _driver["empty"] = True
    _driver["samples"] = [{"a": "same"}] * 50

    tasks._wait_for_artifacts(None, timeout=-1)  # type: ignore[arg-type]

    assert "still empty" in capsys.readouterr().out


def test_the_window_is_long_enough_to_outlast_a_render_starting_late() -> None:
    """The floor is empirical, so it is asserted rather than left in a comment.

    The post-merge render began more than one sample after the merge and was the
    reason a two-sample wait failed. A minute is the measured floor.
    """
    assert tasks.STABLE_SAMPLES * tasks.SAMPLE_SECONDS >= 60

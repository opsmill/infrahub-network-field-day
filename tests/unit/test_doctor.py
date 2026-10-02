"""`invoke doctor`: the decisions, held against a healthy and a failing fixture each."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from solution_arista_avd import doctor as d
from solution_arista_avd.doctor import Result, Status

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def test_parse_timestamp_handles_docker_nanoseconds_and_git_offsets() -> None:
    assert d.parse_timestamp("2026-10-01T12:00:00.123456789Z") == T0.replace(microsecond=123456)
    assert d.parse_timestamp("2026-10-01T14:00:00+02:00") == T0


def test_image_newer_than_source_passes() -> None:
    assert d.decide_image_staleness(T0, T0 - timedelta(hours=1)).status is Status.PASS


def test_image_behind_source_warns_then_fails() -> None:
    warn = d.decide_image_staleness(T0, T0 + timedelta(hours=1))
    fail = d.decide_image_staleness(T0, T0 + timedelta(days=3))
    assert warn.status is Status.WARN
    assert fail.status is Status.FAIL
    assert "invoke build" in warn.fix


PGREP = """\
4242 python scripts/reconcile.py
4300 /usr/bin/python3 scripts/reconcile.py --interval 60
4400 pgrep -af scripts/reconcile.py
4402 tini -g -- python scripts/reconcile.py
4401 zsh -c pgrep -af scripts/reconcile.py
"""


def test_parse_pgrep_drops_pgrep_and_shell_wrappers() -> None:
    assert d.parse_pgrep(PGREP) == [4242, 4300]
    assert d.parse_pgrep(PGREP, own_pid=4242) == [4300]
    assert d.parse_pgrep("") == []


def test_one_reconciler_passes_and_a_stray_fails_naming_pids() -> None:
    assert d.decide_reconcile_processes([], True).status is Status.PASS
    assert d.decide_reconcile_processes([7], False).status is Status.PASS
    assert d.decide_reconcile_processes([], False).status is Status.PASS
    bad = d.decide_reconcile_processes([7, 9], True)
    assert bad.status is Status.FAIL
    assert "7, 9" in bad.detail
    assert "container" in bad.detail


def test_schema_freshness_ignores_argument_and_field_order_only() -> None:
    a = "type T {\n  f(x: Int, y: String): Int\n  g: Int\n}"
    reordered = "type T {\n  g: Int\n  f(y: String, x: Int): Int\n}"
    changed = "type T {\n  g: Int\n  f(y: String, x: Int, z: ID): Int\n}"
    assert d.decide_schema_freshness(a, reordered).status is Status.PASS
    assert d.decide_schema_freshness(a, changed).status is Status.WARN


def test_schema_freshness_ignores_interface_order_but_not_membership() -> None:
    a = "type T implements A & B & C {\n  f: Int\n}"
    reordered = "type T implements C & A & B {\n  f: Int\n}"
    dropped = "type T implements A & B {\n  f: Int\n}"
    assert d.decide_schema_freshness(a, reordered).status is Status.PASS
    assert d.decide_schema_freshness(a, dropped).status is Status.WARN


def test_image_staleness_ignores_the_doctor_itself() -> None:
    assert ":(exclude)src/solution_arista_avd/doctor.py" in d.IMAGE_PATH_EXCLUDES


def test_schema_freshness() -> None:
    assert d.decide_schema_freshness("a", "a").status is Status.PASS
    stale = d.decide_schema_freshness("a", "b")
    assert stale.status is Status.WARN
    assert "export-schema" in stale.fix


def _repo(**over: str) -> dict[str, str]:
    row = {"name": "test-repository", "commit": "a" * 40, "sync_status": "in-sync", "operational_status": "online"}
    row.update(over)
    return row


def test_repository_in_sync_passes() -> None:
    assert d.decide_repository_sync([_repo()], lambda _c: True).status is Status.PASS


def test_repository_error_import_fails() -> None:
    result = d.decide_repository_sync([_repo(sync_status="error-import")], lambda _c: True)
    assert result.status is Status.FAIL
    assert "new commit" in result.fix


def test_repository_diverged_commit_fails_with_merge_recovery() -> None:
    result = d.decide_repository_sync([_repo()], lambda _c: False)
    assert result.status is Status.FAIL
    assert "not an ancestor" in result.detail
    assert "merge -s ours" in result.fix


def test_operational_error_fails_even_while_sync_reads_in_sync() -> None:
    result = d.decide_repository_sync([_repo(operational_status="error")], lambda _c: True)
    assert result.status is Status.FAIL


def test_no_repository_fails() -> None:
    assert d.decide_repository_sync([], lambda _c: True).status is Status.FAIL


def test_parse_repositories() -> None:
    data = {
        "CoreRepository": {
            "edges": [
                {
                    "node": {
                        "name": {"value": "r"},
                        "commit": {"value": "abc"},
                        "sync_status": {"value": "in-sync"},
                        "operational_status": {"value": "online"},
                    }
                }
            ]
        }
    }
    assert d.parse_repositories(data) == [
        {"name": "r", "commit": "abc", "sync_status": "in-sync", "operational_status": "online"}
    ]
    assert d.parse_repositories({}) == []


GOOD_INSTANCE = {"id": "1", "name": {"value": "gen: ok"}, "object": {"node": {"id": "x"}}}
BAD_INSTANCE = {"id": "2", "name": {"value": "gen: gone"}, "object": {"node": None}}


def test_dangling_instances() -> None:
    assert d.decide_dangling_instances([GOOD_INSTANCE]).status is Status.PASS
    assert d.decide_dangling_instances([]).status is Status.PASS
    result = d.decide_dangling_instances([GOOD_INSTANCE, BAD_INSTANCE, {"id": "3", "name": None, "object": None}])
    assert result.status is Status.FAIL
    assert "gen: gone" in result.detail
    assert "gen: ok" not in result.detail
    assert "3" in result.detail


def test_branches() -> None:
    main = {"name": "main", "is_default": True, "sync_with_git": True}
    clean = {"name": "req-1", "is_default": False, "sync_with_git": False}
    stray = {"name": "feat-x", "is_default": False, "sync_with_git": True}
    assert d.decide_branches([main, clean]).status is Status.PASS
    result = d.decide_branches([main, clean, stray])
    assert result.status is Status.WARN
    assert "feat-x" in result.detail
    assert "req-1" not in result.detail


def test_bridge() -> None:
    assert d.decide_bridge(True, True).status is Status.PASS
    assert d.decide_bridge(False, True).status is Status.WARN
    assert d.decide_bridge(False, False).status is Status.SKIP


def test_unreachable_stack_skips_rather_than_crashes() -> None:
    env = d.Environment(root=Path(), address="http://127.0.0.1:9", token="")

    def needs_stack(e: d.Environment) -> Result:
        e.graphql("{ Branch { name } }")
        raise AssertionError("unreachable")

    def broken(_e: d.Environment) -> Result:
        msg = "boom"
        raise RuntimeError(msg)

    results = d.run_checks(env, (("a", needs_stack), ("b", broken)))
    assert [r.status for r in results] == [Status.SKIP, Status.SKIP]
    assert "did not answer" in results[0].detail
    assert d.exit_code(results) == 0


def test_exit_code_only_fails_on_fail() -> None:
    ok = Result("a", Status.PASS)
    warn = Result("b", Status.WARN)
    bad = Result("c", Status.FAIL)
    assert d.exit_code([ok, warn]) == 0
    assert d.exit_code([ok, bad]) == 1


def test_render_shows_the_fix_only_for_warn_and_fail() -> None:
    assert "->" in Result("n", Status.FAIL, "x", "do it").render()
    assert "->" not in Result("n", Status.PASS, "x", "do it").render()

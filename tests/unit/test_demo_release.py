"""Pins `invoke demo-release`'s naming, import filter and repository modes.

The names are load-bearing: the staged branch must never be a branch Infrahub follows
(it can sit on the remote for days), and the released one must always be. In read-write
mode the repository's default branch is `demo-main`, which is what keeps a merge from
ever pushing to the real `main`. A release is a push, and a pulled commit is never
rewritten, so two releases of the same work may not share a name.
"""

from __future__ import annotations

import re
import subprocess  # noqa: S404 - one fixed-argv git call
from pathlib import Path

import pytest
import yaml

from solution_arista_avd import demo_release as dr

REPO = Path(__file__).resolve().parents[2]
DEFAULT_FILTER = ["main"]


def test_the_demo_filter_imports_a_released_branch_and_nothing_else_here() -> None:
    patterns = dr.parse_patterns(dr.DEMO_IMPORT_FILTER)

    assert dr.is_imported(patterns, dr.demo_branch("internet-access", 1))
    for branch in (dr.stage_branch("internet-access"), "main", dr.DEFAULT_DEMO_BRANCH, "feat/x", "xdemo/x"):
        assert not dr.is_imported(patterns, branch), branch


def test_the_default_filter_imports_neither_branch() -> None:
    """Without the demo override nothing here syncs."""
    assert not dr.is_imported(["main"], dr.stage_branch("internet-access"))
    assert not dr.is_imported(["main"], dr.demo_branch("internet-access", 1))


@pytest.mark.parametrize("raw", ["main", '"main"', "{}", "[1]", ""])
def test_a_filter_that_is_not_a_json_array_of_strings_is_refused(raw: str) -> None:
    with pytest.raises(dr.DemoReleaseError):
        dr.parse_patterns(raw)


def test_the_refspec_publishes_the_staged_branch_under_the_synced_name() -> None:
    assert dr.refspec("internet-access", 2) == "stage/internet-access:demo/internet-access-2"


def test_each_run_has_its_own_branch_name() -> None:
    assert dr.demo_branch("x", 1) != dr.demo_branch("x", 2)


@pytest.mark.parametrize("name", ["", "Upper", "has space", "a/b", "-lead", "semi;colon", "$(x)"])
def test_unusable_names_are_refused(name: str) -> None:
    with pytest.raises(dr.DemoReleaseError):
        dr.stage_branch(name)


@pytest.mark.parametrize("run", [0, -1])
def test_run_numbers_start_at_one(run: int) -> None:
    with pytest.raises(dr.DemoReleaseError):
        dr.demo_branch("x", run)


def test_the_repository_object_file_names_the_remote() -> None:
    document = yaml.safe_load(dr.render_repository("https://github.com/opsmill/infrahub-network-field-day.git"))
    (entry,) = document["spec"]["data"]

    assert document["spec"]["kind"] == "CoreReadOnlyRepository"
    assert entry["name"] == "test-repository"
    assert entry["ref"] == "main"
    assert entry["location"] == "https://github.com/opsmill/infrahub-network-field-day.git"
    assert "credential" not in entry


def test_the_repository_is_read_only_so_infrahub_never_pushes_or_makes_a_branch() -> None:
    """The reason for the kind: a CoreRepository turns each remote branch into an Infrahub branch and pushes it."""
    rendered = dr.render_repository("https://github.com/o/r.git", ref="demo/x-1")

    assert yaml.safe_load(rendered)["spec"]["kind"] == "CoreReadOnlyRepository"
    assert yaml.safe_load(rendered)["spec"]["data"][0]["ref"] == "demo/x-1"


@pytest.mark.parametrize("ref", ["", "  "])
def test_a_repository_without_a_ref_is_refused(ref: str) -> None:
    with pytest.raises(dr.DemoReleaseError):
        dr.render_repository("https://github.com/o/r.git", ref=ref)


def test_the_ref_mutation_names_the_repository_and_quotes_the_ref() -> None:
    mutation = dr.set_ref_mutation("abc-123", "demo/x-1")

    assert "CoreReadOnlyRepositoryUpdate" in mutation
    assert 'id: "abc-123"' in mutation
    assert 'ref: { value: "demo/x-1" }' in mutation


def test_the_absent_schema_marks_exactly_one_node_absent() -> None:
    document = yaml.safe_load(dr.absent_schema("Service", "InternetAccess"))

    assert document["nodes"] == [{"name": "InternetAccess", "namespace": "Service", "state": "absent"}]


def test_the_read_write_repository_pushes_to_demo_main_never_to_main() -> None:
    """Infrahub maps its own `main` onto `default_branch` when it pushes (`_get_mapped_remote_branch`)."""
    rendered = dr.render_repository("https://github.com/o/r.git", mode="readwrite", credential="demo-remote")
    (entry,) = yaml.safe_load(rendered)["spec"]["data"]

    assert yaml.safe_load(rendered)["spec"]["kind"] == "CoreRepository"
    assert entry["default_branch"] == "demo-main"
    assert entry["default_branch"] != "main"
    assert entry["credential"] == "demo-remote"
    assert "ref" not in entry


def test_a_read_write_repository_without_a_credential_is_refused() -> None:
    with pytest.raises(dr.DemoReleaseError):
        dr.render_repository("https://github.com/o/r.git", mode="readwrite")


@pytest.mark.parametrize("mode", ["", "rw", "READONLY"])
def test_an_unknown_mode_is_refused(mode: str) -> None:
    with pytest.raises(dr.DemoReleaseError):
        dr.render_repository("https://github.com/o/r.git", mode=mode)


def test_the_repository_object_file_refers_to_a_credential_by_name_only() -> None:
    rendered = dr.render_repository("https://github.com/o/r.git", credential="demo-remote")

    assert yaml.safe_load(rendered)["spec"]["data"][0]["credential"] == "demo-remote"


@pytest.mark.parametrize("url", ["/upstream", "github.com/o/r", ""])
def test_a_location_that_is_not_a_remote_url_is_refused(url: str) -> None:
    with pytest.raises(dr.DemoReleaseError):
        dr.render_repository(url)


def test_the_credential_is_only_ever_rendered_for_a_temporary_file() -> None:
    """Nothing committed carries a secret: the helper takes it as an argument."""
    assert "password" not in (REPO / "repository.yml").read_text(encoding="utf-8")
    secret = "not-a-real-token"  # noqa: S105 - a placeholder, to see it round-trip
    assert yaml.safe_load(dr.render_credential("n", "u", secret))["spec"]["data"][0]["password"] == secret


def test_the_proposed_change_mutation_targets_main_and_escapes_its_text() -> None:
    mutation = dr.proposed_change_mutation("demo/x-1", 'a "quoted" name', "line\nbreak")

    assert 'destination_branch: { value: "main" }' in mutation
    assert re.search(r'source_branch: \{ value: "demo/x-1" \}', mutation)
    assert '\\"quoted\\"' in mutation
    assert "\n" not in mutation


def test_the_defaults_still_hold() -> None:
    """The override is demo-time only: the repository default and the filter are unchanged."""
    repository = yaml.safe_load((REPO / "repository.yml").read_text(encoding="utf-8"))
    assert repository["spec"]["data"][0]["location"] == "/upstream"
    override = (REPO / "docker-compose.override.yml").read_text(encoding="utf-8")
    assert '${INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES:-["main"]}' in override


_SETTLED = {
    "expected_commit": "a" * 40,
    "commit": "a" * 40,
    "sync_status": "in-sync",
    "kind_present": True,
    "object_count": 1,
    "active_tasks": 0,
    "failed_tasks": [],
}


def test_a_branch_is_settled_only_when_every_condition_holds() -> None:
    assert dr.decide_settled(**_SETTLED) == (True, "")


@pytest.mark.parametrize(
    ("change", "waiting_for"),
    [
        ({"commit": "b" * 40}, "the import of"),
        ({"commit": ""}, "nothing"),
        ({"sync_status": "syncing"}, "in-sync"),
        ({"kind_present": False}, "schema"),
        ({"object_count": 0}, "objects"),
        ({"active_tasks": 3}, "3 task(s)"),
    ],
)
def test_each_missing_condition_keeps_the_branch_unsettled_and_says_why(change: dict, waiting_for: str) -> None:
    settled, waiting = dr.decide_settled(**{**_SETTLED, **change})

    assert settled is False
    assert waiting_for in waiting


def test_a_failed_task_is_reported_even_when_everything_else_looks_settled() -> None:
    settled, waiting = dr.decide_settled(**{**_SETTLED, "failed_tasks": ["Import objects"]})

    assert settled is False
    assert waiting.startswith("failed tasks")
    assert "Import objects" in waiting


def test_the_task_states_that_count_as_active_and_as_failed_do_not_overlap() -> None:
    assert not set(dr.ACTIVE_TASK_STATES) & set(dr.FAILED_TASK_STATES)
    assert {"RUNNING", "PENDING"} <= set(dr.ACTIVE_TASK_STATES)
    assert {"FAILED", "CRASHED"} <= set(dr.FAILED_TASK_STATES)


def test_a_branch_that_takes_the_capability_back_out_does_not_wait_for_it() -> None:
    """A reset branch has no schema or objects of its own, so their absence is not a reason to wait."""
    taken_out = {**_SETTLED, "kind_present": False, "object_count": 0}

    assert dr.decide_settled(**taken_out)[0] is False
    assert dr.decide_settled(**taken_out, require_capability=False) == (True, "")


def test_require_capability_off_still_waits_for_the_commit_and_the_queue() -> None:
    assert dr.decide_settled(**{**_SETTLED, "commit": "b" * 40}, require_capability=False)[0] is False
    assert dr.decide_settled(**{**_SETTLED, "active_tasks": 2}, require_capability=False)[0] is False


def test_a_branch_is_not_settled_until_every_worker_has_pulled_the_commit() -> None:
    """The race behind a reset that merged the data and left the code: a merge reads the worker's
    local branch, which a periodic pull updates after the graph records the import."""
    settled, waiting = dr.decide_settled(**_SETTLED, workers_synced=False)

    assert settled is False
    assert "worker" in waiting


def test_the_workers_check_defaults_to_satisfied_for_modes_that_do_not_merge_git() -> None:
    assert dr.decide_settled(**_SETTLED) == (True, "")


_INFRAHUB_YML = "---\nmenus:\n  - menus/menu.yml\nqueries:\n  - name: q\n"


def test_declaring_the_import_adds_schemas_and_objects_and_keeps_the_rest() -> None:
    out = dr.declare_schemas_and_objects(_INFRAHUB_YML, ["schemas/b.yml", "schemas/a.yml"], ["objects/37.yml"])
    document = yaml.safe_load(out)

    assert out.startswith(_INFRAHUB_YML.rstrip("\n"))
    assert document["schemas"] == ["schemas/a.yml", "schemas/b.yml"]
    assert document["objects"] == ["objects/37.yml"]
    assert document["menus"] == ["menus/menu.yml"]


@pytest.mark.parametrize("already", ["schemas:\n  - a.yml\n", "objects:\n  - o.yml\n"])
def test_a_file_that_already_declares_the_import_is_refused(already: str) -> None:
    with pytest.raises(dr.DemoReleaseError):
        dr.declare_schemas_and_objects(_INFRAHUB_YML + already, ["schemas/a.yml"], ["objects/o.yml"])


@pytest.mark.parametrize(("schemas", "objects"), [([], ["o.yml"]), (["s.yml"], [])])
def test_both_schema_files_and_object_files_are_required(schemas: list[str], objects: list[str]) -> None:
    with pytest.raises(dr.DemoReleaseError):
        dr.declare_schemas_and_objects(_INFRAHUB_YML, schemas, objects)


def test_main_declares_neither_schemas_nor_objects_so_only_a_staged_branch_carries_them() -> None:
    """Skipped on the staged branch itself, which is the one place they are meant to be declared."""
    declared = re.search(r"^(schemas|objects):", (REPO / ".infrahub.yml").read_text(encoding="utf-8"), re.MULTILINE)
    if declared and (REPO / ".git").exists() and "stage/" in _current_branch():
        pytest.skip("this is a staged branch")

    assert declared is None


def _current_branch() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO,
    ).stdout.strip()

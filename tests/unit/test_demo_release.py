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


def _validator(label: str, state: str = "completed", conclusion: str = "success") -> dict[str, str]:
    return {"label": label, "state": state, "conclusion": conclusion}


def test_validators_pass_when_all_are_completed_and_successful() -> None:
    validators = [_validator("Repository Validator"), _validator("Check: wan-service-consistency")]

    assert dr.decide_validators(validators) == ("passed", "2 validators passed")


def test_validators_are_pending_until_a_user_defined_check_has_started() -> None:
    state, detail = dr.decide_validators([_validator("Repository Validator")])

    assert state == "pending"
    assert "checks" in detail


def test_validators_are_pending_while_any_is_still_running() -> None:
    validators = [_validator("Check: a"), _validator("Artifact Validator", "in_progress", "unknown")]

    state, detail = dr.decide_validators(validators)

    assert state == "pending"
    assert "Artifact Validator" in detail


def test_a_failed_validator_is_reported_by_name_even_while_others_run() -> None:
    validators = [
        _validator("Check: zone-advertisement", conclusion="failure"),
        _validator("Check: allocation-consistency", conclusion="failure"),
        _validator("Artifact Validator", "in_progress", "unknown"),
    ]

    state, detail = dr.decide_validators(validators)

    assert state == "failed"
    assert "Check: allocation-consistency, Check: zone-advertisement" in detail


def test_no_validators_at_all_is_pending() -> None:
    assert dr.decide_validators([])[0] == "pending"


def test_only_the_latest_run_of_a_validator_counts() -> None:
    """The release asks for the checks twice; a first pass that raced the import must not fail the gate."""
    validators = [
        {**_validator("Check: a", conclusion="failure"), "started_at": "2026-10-03T10:00:00Z"},
        {**_validator("Check: a"), "started_at": "2026-10-03T10:05:00Z"},
    ]

    assert dr.decide_validators(validators)[0] == "passed"


def test_a_validator_not_started_yet_is_newer_than_a_finished_one() -> None:
    validators = [
        {**_validator("Check: a"), "started_at": "2026-10-03T10:00:00Z"},
        {"label": "Check: a", "state": "queued", "conclusion": "unknown", "started_at": ""},
    ]

    assert dr.decide_validators(validators)[0] == "pending"


@pytest.mark.parametrize(
    ("current", "head", "tip", "needs"),
    [
        ("main", "a" * 40, "a" * 40, True),  # on the wrong branch
        ("demo-main", "a" * 40, "b" * 40, True),  # behind or beside the remote
        ("demo-main", "a" * 40, "a" * 40, False),  # aligned
        ("", "a" * 40, "b" * 40, False),  # detached or unreadable: leave it
    ],
)
def test_a_worker_needs_realigning_unless_it_is_on_the_default_branch_at_the_remote_tip(
    current: str, head: str, tip: str, needs: bool
) -> None:
    assert dr.worker_needs_realignment(current, "demo-main", head, tip) is needs


# --- capability_is_merged ---------------------------------------------------


def test_a_stale_stage_branch_is_not_a_merged_capability() -> None:
    """`main` moved since staging, so the trees differ; the capability's own files are still absent."""
    added = ["schemas/internet_access.yml", "generators/generate_internet_access.py", ".infrahub.yml"]
    default_files = {"schemas/other.yml", "generators/generate_pod.py", ".infrahub.yml", "docs/new-page.md"}
    assert dr.capability_is_merged(added, default_files) is False


def test_a_capability_whose_files_are_on_the_default_branch_is_merged() -> None:
    added = ["schemas/internet_access.yml", ".infrahub.yml"]
    assert dr.capability_is_merged(added, {"schemas/internet_access.yml", ".infrahub.yml"}) is True


def test_the_import_bookkeeping_file_alone_cannot_say_whether_it_is_merged() -> None:
    """`.infrahub.yml` is on the default branch either way, so the caller must judge another way."""
    assert dr.capability_is_merged([".infrahub.yml"], {".infrahub.yml"}) is None
    assert dr.capability_is_merged([], {".infrahub.yml"}) is None


# --- restoring only the capability --------------------------------------------

BASE_YML = "queries:\n  - name: a\n    file_path: a.gql\nmenus:\n  - menus/m.yml\n"
STAGE_YML = (
    "queries:\n  - name: a\n    file_path: a.gql\n  - name: internet\n    file_path: internet.gql\n"
    "menus:\n  - menus/m.yml\nschemas:\n  - schemas/internet.yml\nobjects:\n  - objects/internet.yml\n"
)


def test_parse_tree_listing_reads_git_ls_tree_output() -> None:
    listing = "100644 blob abc123\tschemas/a.yml\n100644 blob def456\tpath with space.md\n"

    assert dr.parse_tree_listing(listing) == {"schemas/a.yml": "abc123", "path with space.md": "def456"}


def test_capability_paths_are_what_the_stage_changes_against_its_cut_point() -> None:
    base = {"a.yml": "1", "q.gql": "1", ".infrahub.yml": "1"}
    stage = {"a.yml": "1", "q.gql": "2", "schemas/internet.yml": "9", ".infrahub.yml": "2"}

    assert dr.capability_paths(base, stage) == ["q.gql", "schemas/internet.yml"]


def test_plan_removes_capability_files_and_restores_changed_ones() -> None:
    base = {"q.gql": "1", "keep.md": "1"}
    stage = {"q.gql": "2", "schemas/internet.yml": "9", "keep.md": "1"}
    default = {"q.gql": "2", "schemas/internet.yml": "9", "keep.md": "1"}

    plan = dr.plan_restore(base, stage, default)

    assert plan.remove == ["schemas/internet.yml"]
    assert plan.restore == ["q.gql"]
    assert plan.diverged == []


def test_plan_leaves_a_default_branch_newer_than_the_staging_point_alone() -> None:
    # demo-main is older than main: it lacks triggers.yml and new.md, which main gained after staging.
    base = {"triggers.yml": "2", "new.md": "1", "q.gql": "1"}
    stage = {"triggers.yml": "2", "new.md": "1", "q.gql": "2", "schemas/internet.yml": "9"}
    default = {"triggers.yml": "1", "q.gql": "2", "schemas/internet.yml": "9"}

    plan = dr.plan_restore(base, stage, default)

    assert "triggers.yml" not in plan.remove + plan.restore
    assert "new.md" not in plan.remove + plan.restore
    assert plan.remove == ["schemas/internet.yml"]
    assert plan.restore == ["q.gql"]


def test_plan_keeps_files_changed_on_the_default_branch_after_staging() -> None:
    base = {"tasks.py": "1", "q.gql": "1"}
    stage = {"tasks.py": "1", "q.gql": "2", "schemas/internet.yml": "9"}
    default = {"tasks.py": "5", "q.gql": "2", "schemas/internet.yml": "9"}

    plan = dr.plan_restore(base, stage, default)

    assert "tasks.py" not in plan.remove + plan.restore


def test_plan_reports_a_capability_file_edited_after_staging() -> None:
    base = {"q.gql": "1"}
    stage = {"q.gql": "2"}
    default = {"q.gql": "3"}

    plan = dr.plan_restore(base, stage, default)

    assert plan.restore == ["q.gql"]
    assert plan.diverged == ["q.gql"]


def test_plan_does_nothing_when_the_capability_is_not_on_the_default_branch() -> None:
    base = {"q.gql": "1"}
    stage = {"q.gql": "2", "schemas/internet.yml": "9"}

    plan = dr.plan_restore(base, stage, {"q.gql": "1"})

    assert plan == dr.RestorePlan()


def test_plan_with_a_stage_that_has_no_capability_files_is_empty() -> None:
    files = {"a.yml": "1", ".infrahub.yml": "1"}

    assert dr.plan_restore(files, {**files, ".infrahub.yml": "2"}, files) == dr.RestorePlan()


def test_declarations_of_the_capability_are_removed_and_other_entries_kept() -> None:
    default = (
        "queries:\n  - name: a\n    file_path: a.gql\n  - name: internet\n    file_path: internet.gql\n"
        "  - name: later\n    file_path: later.gql\n"
        "menus:\n  - menus/m.yml\nschemas:\n  - schemas/internet.yml\nobjects:\n  - objects/internet.yml\n"
    )

    text, unresolved = dr.revert_declarations(BASE_YML, STAGE_YML, default)

    assert (
        text
        == "queries:\n  - name: a\n    file_path: a.gql\n  - name: later\n    file_path: later.gql\nmenus:\n  - menus/m.yml\n"
    )
    assert unresolved == []


def test_declarations_are_untouched_when_the_capability_is_not_there() -> None:
    default = BASE_YML + "triggers:\n  - triggers.yml\n"

    text, unresolved = dr.revert_declarations(BASE_YML, STAGE_YML, default)

    assert text == default
    assert unresolved == []


def test_declarations_on_a_default_branch_that_lacks_newer_entries_do_not_gain_them() -> None:
    newer_base = BASE_YML + "triggers:\n  - triggers.yml\n"
    default = STAGE_YML  # demo-main has the capability but not the later `triggers:` entry

    text, _ = dr.revert_declarations(BASE_YML, STAGE_YML, default)

    assert text == BASE_YML
    assert "triggers" not in text
    assert newer_base != text


def test_a_stage_with_no_capability_file_is_refused_before_a_release_waits_for_a_schema() -> None:
    with pytest.raises(dr.DemoReleaseError, match=r"changes no file besides \.infrahub\.yml"):
        dr.require_capability_files([".infrahub.yml"], "stage/x")
    with pytest.raises(dr.DemoReleaseError):
        dr.require_capability_files([], "stage/x")
    dr.require_capability_files([".infrahub.yml", "schemas/internet.yml"], "stage/x")

"""Pins `invoke demo-release`'s naming and filter rules.

The names are load-bearing in both directions: the staged branch must never be
imported by Infrahub (it can sit on the remote for days), and the released one
must always be. A release is a push, and a pulled commit is never rewritten, so
two releases of the same work may not share a name.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from solution_arista_avd import demo_release as dr

REPO = Path(__file__).resolve().parents[2]
DEFAULT_FILTER = ["main"]


def test_the_staged_branch_is_never_imported_and_the_released_one_always_is() -> None:
    patterns = json.loads(dr.demo_filter(DEFAULT_FILTER))

    assert not dr.is_imported(patterns, dr.stage_branch("internet-access"))
    assert dr.is_imported(patterns, dr.demo_branch("internet-access", 1))


def test_the_default_filter_imports_neither() -> None:
    """The point of `["main"]`: without the demo override nothing here syncs."""
    assert not dr.is_imported(DEFAULT_FILTER, dr.stage_branch("internet-access"))
    assert not dr.is_imported(DEFAULT_FILTER, dr.demo_branch("internet-access", 1))


def test_the_override_keeps_what_was_already_allowed_and_is_idempotent() -> None:
    once = json.loads(dr.demo_filter(DEFAULT_FILTER))
    twice = json.loads(dr.demo_filter(once))

    assert once[0] == "main"
    assert once == twice
    assert dr.is_imported(once, "main")


def test_the_override_does_not_let_ordinary_feature_branches_in() -> None:
    patterns = json.loads(dr.demo_filter(DEFAULT_FILTER))

    for branch in ("feat/anything", "worktree-agent-a33a06fb0bf52bdb1", "main-backup", "stage/x", "xdemo/x"):
        assert not dr.is_imported(patterns, branch), branch


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


@pytest.mark.parametrize("raw", ["main", '"main"', "{}", "[1]", ""])
def test_a_filter_that_is_not_a_json_array_of_strings_is_refused(raw: str) -> None:
    with pytest.raises(dr.DemoReleaseError):
        dr.parse_patterns(raw)


def test_the_repository_object_file_names_the_remote() -> None:
    document = yaml.safe_load(dr.render_repository("https://github.com/opsmill/infrahub-network-field-day.git"))
    (entry,) = document["spec"]["data"]

    assert document["spec"]["kind"] == "CoreRepository"
    assert entry["name"] == "test-repository"
    assert entry["location"] == "https://github.com/opsmill/infrahub-network-field-day.git"
    assert "credential" not in entry


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

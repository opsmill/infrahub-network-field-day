"""Pins `invoke demo-release`'s naming and the read-only repository it relies on.

Infrahub tracks one ref of a read-only repository and creates no branch from Git,
so the names matter only to the remote: the staged branch is never a ref Infrahub
follows until a release says so. A release is a push, and a pulled commit is never
rewritten, so two releases of the same work may not share a name.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from solution_arista_avd import demo_release as dr

REPO = Path(__file__).resolve().parents[2]
DEFAULT_FILTER = ["main"]


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

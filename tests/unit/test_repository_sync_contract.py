"""Contract: Infrahub imports only ``main`` from the repository it clones.

The CoreRepository in ``repository.yml`` clones ``/upstream``, which
``docker-compose.override.yml`` binds to this checkout. Left at its default,
Infrahub turns every local git branch of that checkout into an Infrahub branch
-- each agent worktree and each feature branch -- and every Infrahub branch
registers its own Prefect automations and imports the repository again. A few
worktrees were measured taking the task manager to 100% CPU, 3,868 automations
and ``set_state`` 500s that failed real generator runs.

``INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES`` is Infrahub 1.10.6's own filter for
that import (``infrahub.git.base.get_filtered_remote_branches``): a JSON list of
names or regexes, each tried with ``re.fullmatch``. Nothing fails loudly if it
is dropped -- the storm simply comes back the next time someone opens a
worktree -- so these tests hold the value and the mount it applies to.

This file reads only YAML; it needs no running Infrahub.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
VARIABLE = "INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES"

# The services whose Infrahub settings must carry the filter: the task workers
# run the git sync, and the server holds the same configuration.
SERVICES = ("infrahub-server", "task-worker")

# Shapes of branch the filter exists to keep out of Infrahub.
UNWANTED = (
    "worktree-agent-a33a06fb0bf52bdb1",
    "fix/infrahub-main-only-upstream",
    "feature/portal-demo-polish",
    "034-grafana-observability",
    "main-backup",
    "old-main",
)


def _override() -> dict:
    return yaml.safe_load((REPO / "docker-compose.override.yml").read_text(encoding="utf-8"))


def compose_default(value: str) -> str:
    """The fallback of a ``${NAME:-default}`` compose expression, or the value itself."""
    match = re.fullmatch(r"\$\{(?P<name>\w+):-(?P<default>.*)\}", value)
    return match.group("default") if match else value


def _patterns(service: str) -> list[str]:
    environment = _override()["services"][service]["environment"]
    assert VARIABLE in environment, (
        f"{service} has no {VARIABLE}: Infrahub would import every local git branch as an Infrahub branch"
    )
    value = environment[VARIABLE]
    assert value.startswith(f"${{{VARIABLE}:-"), f"{service}: {VARIABLE} should stay overridable from .env"
    patterns = json.loads(compose_default(value))
    assert isinstance(patterns, list), f"{service}: Infrahub parses {VARIABLE} as a JSON list"
    return patterns


def _imported(patterns: list[str], branch: str) -> bool:
    """Infrahub's own test, ``infrahub.git.utils.branch_name_in_import_sync_branches``."""
    return any(re.fullmatch(pattern, branch) or pattern == branch for pattern in patterns)


def test_compose_default_extracts_the_fallback() -> None:
    assert compose_default('${X:-["main"]}') == '["main"]'
    assert not compose_default("${X:-}")
    assert compose_default("literal") == "literal"


@pytest.mark.parametrize("service", SERVICES)
def test_only_main_is_imported(service: str) -> None:
    patterns = _patterns(service)
    assert patterns == ["main"]
    assert _imported(patterns, "main")


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("branch", UNWANTED)
def test_agent_and_feature_branches_are_not_imported(service: str, branch: str) -> None:
    assert not _imported(_patterns(service), branch)


def test_the_filter_applies_to_the_checkout_infrahub_clones() -> None:
    """The filter is only meaningful for the source it guards: ``/upstream``, the checkout."""
    repository = yaml.safe_load((REPO / "repository.yml").read_text(encoding="utf-8"))
    (definition,) = repository["spec"]["data"]
    assert repository["spec"]["kind"] == "CoreRepository"
    assert definition["location"] == "/upstream"

    worker = _override()["services"]["task-worker"]
    assert "./:/upstream" in worker["volumes"]


def test_the_base_file_does_not_pin_a_value() -> None:
    """docker-compose.yml passes the variable through bare, so the override decides."""
    base = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    for service in SERVICES:
        assert base["services"][service]["environment"].get(VARIABLE) is None

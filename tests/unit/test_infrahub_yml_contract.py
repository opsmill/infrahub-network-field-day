"""Contract on `.infrahub.yml`'s wiring.

Everything here fails at **repository sync or run time**, never at load time, and
the errors name the wrong thing when they arrive. A generator whose `query:` is
not registered imports fine and fails when it runs; a `class_name` that does not
exist fails the same way; a `targets:` group nobody seeds produces a definition
that simply never runs, against no objects, reporting nothing.

That last one is the worst of them, because a generator with no targets and a
generator that ran and found nothing to do are indistinguishable in the logs --
and this repository already documents a partial repository import leaving a
`CoreGraphQLQuery` registered without the `CoreGeneratorDefinition` beside it.

`tests/unit/test_deployment_schema_contract.py` also reads this file, for a
different and narrower rule: that nothing generates from a deployment kind.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parents[2]
CONFIG = REPO_ROOT / ".infrahub.yml"
GROUPS = REPO_ROOT / "objects/00_groups.yml"

DEFINITION_KEYS = ("generator_definitions", "check_definitions", "python_transforms", "artifact_definitions")


def _config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _entries(key: str) -> list[dict[str, Any]]:
    return _config().get(key) or []


def _all_definitions() -> list[tuple[str, dict[str, Any]]]:
    return [(key, entry) for key in DEFINITION_KEYS for entry in _entries(key)]


def _ids(pair: tuple[str, dict[str, Any]]) -> str:
    return f"{pair[0]}/{pair[1].get('name')}"


def _seeded_groups() -> set[str]:
    names: set[str] = set()
    for document in yaml.safe_load_all(GROUPS.read_text(encoding="utf-8")):
        if document and document.get("spec", {}).get("kind") == "CoreStandardGroup":
            names |= {row["name"] for row in document["spec"]["data"]}
    return names


# ---------------------------------------------------------------------------
# The corpus is real
# ---------------------------------------------------------------------------


def test_there_is_something_to_check() -> None:
    """Every rule below is parametrised, and a parametrised rule over an empty
    list passes while asserting nothing."""
    assert len(_all_definitions()) > 20
    assert len(_entries("queries")) > 20
    assert len(_seeded_groups()) > 5


# ---------------------------------------------------------------------------
# Files, queries, classes, groups
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", _entries("queries"), ids=lambda e: str(e.get("name")))
def test_every_registered_query_file_exists(entry: dict[str, Any]) -> None:
    assert (REPO_ROOT / entry["file_path"]).is_file(), f"{entry['name']} points at a missing file"


@pytest.mark.parametrize("pair", _all_definitions(), ids=_ids)
def test_every_definition_file_exists(pair: tuple[str, dict[str, Any]]) -> None:
    _, entry = pair
    file_path = entry.get("file_path")
    if file_path is None:
        return
    assert (REPO_ROOT / file_path).is_file(), f"{entry.get('name')} points at a missing file"


@pytest.mark.parametrize("pair", _all_definitions(), ids=_ids)
def test_every_named_query_is_registered(pair: tuple[str, dict[str, Any]]) -> None:
    """An unregistered query name is accepted by the file and fails when the
    definition runs."""
    _, entry = pair
    query = entry.get("query")
    if query is None:
        return
    registered = {item["name"] for item in _entries("queries")}
    assert query in registered, f"{entry.get('name')} names query {query!r}, which .infrahub.yml does not register"


@pytest.mark.parametrize("pair", _all_definitions(), ids=_ids)
def test_every_class_name_exists_in_its_file(pair: tuple[str, dict[str, Any]]) -> None:
    """A typo here imports cleanly and fails when the definition is executed."""
    _, entry = pair
    class_name = entry.get("class_name")
    file_path = entry.get("file_path")
    if class_name is None or file_path is None:
        return
    tree = ast.parse((REPO_ROOT / file_path).read_text(encoding="utf-8"))
    defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert class_name in defined, f"{entry.get('name')} names class {class_name!r}, absent from {file_path}"


@pytest.mark.parametrize("pair", _all_definitions(), ids=_ids)
def test_every_target_group_is_seeded(pair: tuple[str, dict[str, Any]]) -> None:
    """THE QUIET ONE.

    A definition targeting a group nobody creates does not error. It runs
    against nothing, which in the logs is indistinguishable from running and
    finding nothing to do.
    """
    _, entry = pair
    targets = entry.get("targets")
    if targets is None:
        return
    assert targets in _seeded_groups(), (
        f"{entry.get('name')} targets group {targets!r}, which objects/00_groups.yml does not seed -- "
        "the definition will run against nothing and report nothing"
    )


@pytest.mark.parametrize("entry", _entries("artifact_definitions"), ids=lambda e: str(e.get("name")))
def test_every_artifact_names_a_declared_transform(entry: dict[str, Any]) -> None:
    declared = {item["name"] for item in _entries("python_transforms")}
    assert entry["transformation"] in declared, (
        f"artifact {entry['name']} renders through {entry['transformation']!r}, which is not a declared transform"
    )


# ---------------------------------------------------------------------------
# Uniqueness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["queries", *DEFINITION_KEYS])
def test_names_are_unique_within_their_section(key: str) -> None:
    """A duplicate silently wins or loses depending on import order, and the
    repository sync reports neither."""
    names = [entry.get("name") for entry in _entries(key)]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"{key} declares these names more than once: {duplicates}"

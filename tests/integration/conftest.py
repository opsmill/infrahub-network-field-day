import shutil
import subprocess  # noqa: S404 -- one fixed git invocation
from pathlib import Path
from typing import Any

import pytest
from infrahub_sdk.yaml import SchemaFile

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


@pytest.fixture
def root_directory() -> Path:
    """The repository root."""
    return CURRENT_DIRECTORY.parent.parent


@pytest.fixture
def repository_source(root_directory: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The repository as git would ship it: tracked files, plus untracked ones not ignored.

    The SDK's `GitRepo` copies its whole `src_directory` and commits it, ignoring
    only `.git` -- its `directories_to_ignore` field is never read. Pointed at the
    checkout, that copied `.venv`, `docs/node_modules` and `backstage/node_modules`
    (3.3GB) and committed them again, per test, into /tmp. Two such tests filled
    the host's 62GB RAM-backed /tmp and took the lab's tooling down with ENOSPC
    (cycle 034, measured). The tracked tree is 22MB, and it is what Infrahub would
    clone from a real remote anyway.
    """
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],  # noqa: S607
        cwd=root_directory,
        capture_output=True,
        check=True,
    ).stdout.decode()
    destination = tmp_path_factory.mktemp("repository-source")
    for relative in filter(None, listed.split("\0")):
        source = root_directory / relative
        if not source.is_file():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return destination


@pytest.fixture
def schemas_directory(root_directory: Path) -> Path:
    return root_directory / "schemas"


@pytest.fixture
def schemas(schemas_directory: Path) -> list[dict[str, Any]]:
    schema_files = SchemaFile.load_from_disk(paths=[schemas_directory])
    return [item.content for item in schema_files if item.content]

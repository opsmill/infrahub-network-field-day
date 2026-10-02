"""The credential scripts read and write the MAIN checkout's `.env`.

docker compose reads `.env` from its project directory, and `tasks.py` pins that
to the main checkout even from a git worktree. `provision_mcp_agent.py` and
`provision_metrics_exporter.py` used to resolve `.env` next to themselves, so
run from a worktree they generated a password into a file compose never reads,
and `--check` reported the real credential missing.

These build a real repository and a real worktree in a temporary directory,
because the behaviour under test is git's answer, not a string manipulation.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess  # noqa: S404 - fixed-argv git calls only
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from solution_arista_avd.envfile import env_file, main_checkout

if TYPE_CHECKING:
    from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = ("provision_mcp_agent", "provision_metrics_exporter")

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def checkout_and_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "commit", "-q", "--allow-empty", "-m", "root")
    worktree = tmp_path / "elsewhere" / "wt"
    _git(main, "worktree", "add", "-q", str(worktree))
    return main.resolve(), worktree.resolve()


@requires_git
def test_a_worktree_resolves_to_its_main_checkout(checkout_and_worktree: tuple[Path, Path]) -> None:
    main, worktree = checkout_and_worktree
    assert main_checkout(worktree) == main
    assert env_file(worktree) == main / ".env"


@requires_git
def test_a_subdirectory_of_a_worktree_resolves_to_the_main_checkout(
    checkout_and_worktree: tuple[Path, Path],
) -> None:
    main, worktree = checkout_and_worktree
    scripts = worktree / "scripts"
    scripts.mkdir()
    assert main_checkout(scripts) == main


@requires_git
def test_a_main_checkout_resolves_to_itself(checkout_and_worktree: tuple[Path, Path]) -> None:
    main, _ = checkout_and_worktree
    assert main_checkout(main) == main
    assert env_file(main) == main / ".env"


def test_outside_a_repository_the_directory_is_kept(tmp_path: Path) -> None:
    """A source tarball has no git directory; its `.env` is the one beside it."""
    assert main_checkout(tmp_path) == tmp_path
    assert env_file(tmp_path) == tmp_path / ".env"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", SCRIPTS)
def test_the_provisioning_scripts_use_the_main_checkouts_env(name: str) -> None:
    """Whichever checkout runs the test, the script names the same `.env` compose reads."""
    assert env_file(REPO) == _load(name).ENV_FILE


@requires_git
@pytest.mark.parametrize("name", SCRIPTS)
def test_a_provisioning_script_copied_into_a_worktree_writes_to_the_main_checkout(
    name: str, checkout_and_worktree: tuple[Path, Path]
) -> None:
    """The regression itself: run from a worktree, the script must not pick the worktree's `.env`."""
    main, worktree = checkout_and_worktree
    (worktree / "scripts").mkdir()
    copy = worktree / "scripts" / f"{name}.py"
    shutil.copy(REPO / "scripts" / f"{name}.py", copy)

    spec = importlib.util.spec_from_file_location(f"{name}_in_worktree", copy)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert main / ".env" == module.ENV_FILE
    assert worktree / ".env" != module.ENV_FILE

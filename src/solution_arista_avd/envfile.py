"""Read and write the repository's gitignored `.env`.

Three callers keep generated credentials there -- `tasks.py` and the two
`scripts/provision_*.py` scripts -- and each used to carry its own copy of these
two functions. The copies drifted: one deleted the old `NAME=` line but kept the
comment above it, so every re-mint left another orphaned comment behind.

Host-side only. Nothing that runs in the Infrahub image imports this.

**Which `.env` is the one that matters.** docker compose reads `.env` from its
project directory, and `tasks.py` pins that to the MAIN checkout even when run
from a git worktree (see `compose_root`). A caller that resolved `.env` next to
its own file would, from a worktree, write a credential into a file compose never
reads -- and, on `--check`, report the real one missing. `main_checkout` is the
one place that decides, and `env_file` is what every caller should use.
"""

from __future__ import annotations

import re
import subprocess  # noqa: S404 - one fixed-argv git call, never a shell string
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping


def main_checkout(start: Path) -> Path:
    """The main checkout of the repository containing `start`.

    From a normal checkout this is the checkout itself; from a git worktree it is
    the checkout the worktree was made from. `git rev-parse --git-common-dir`
    names the shared git directory in both cases, and its parent is the answer.
    Outside a git repository -- or when git is unavailable -- `start` is returned
    unchanged, so a source tarball still finds the `.env` beside it.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            cwd=start,
        )
    except OSError:
        return start
    if result.returncode == 0 and result.stdout.strip():
        common = Path(result.stdout.strip())
        if not common.is_absolute():
            common = (start / common).resolve()
        if common.name == ".git":
            return common.parent
    return start


def env_file(start: Path) -> Path:
    """The `.env` docker compose reads: the main checkout's, never a worktree's."""
    return main_checkout(start) / ".env"


def read_env(path: Path, name: str) -> str:
    """The value of `name` in `path`, or the empty string."""
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip()
    return ""


def upsert_env(path: Path, name: str, value: str, comment: str) -> None:
    """Set `name=value` in `path`, under `# comment`, replacing any earlier entry.

    The earlier entry goes WITH its comment block: the contiguous comment lines
    directly above it, plus any other line identical to the new comment, which
    is what an earlier writer left orphaned.
    """
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    header = f"# {comment}"
    kept: list[str] = []
    for line in lines:
        if line.startswith(f"{name}="):
            while kept and kept[-1].startswith("#"):
                kept.pop()
            continue
        if line == header:
            continue
        kept.append(line)

    # Collapse the blank runs the removals leave, so the file does not grow.
    compact: list[str] = []
    for line in kept:
        if not line.strip() and (not compact or not compact[-1].strip()):
            continue
        compact.append(line)
    while compact and not compact[-1].strip():
        compact.pop()

    compact += ["", header, f"{name}={value}"]
    path.write_text("\n".join(compact).lstrip("\n") + "\n", encoding="utf-8")


# The credentials this project generates into `.env`: the account passwords and the API tokens of
# the MCP agent and its users, the portal, the exporter, and the network-admin account.
GENERATED_CREDENTIAL = re.compile(r"^INFRAHUB_(MCP|PORTAL|EXPORTER|NETWORK_ADMIN)_(TOKEN|PASSWORD)(_[A-Z0-9_]+)?$")


def stale_credentials(environ: Mapping[str, str], path: Path) -> list[str]:
    """Names of generated credentials the process environment holds with a value `.env` does not.

    A shell that loaded `.env` before `bootstrap --fresh` keeps the old tokens, and a process
    environment wins over `.env` both for `docker compose` and for `scripts/deploy_tooling.sh`. The
    portal was then deployed with a token the new database had never seen, and every request it made
    was refused with 401, so its catalogue was empty. Names only, never values.
    """
    return sorted(
        name for name, value in environ.items() if GENERATED_CREDENTIAL.match(name) and value != read_env(path, name)
    )


def use_dotenv_credentials(environ: MutableMapping[str, str], path: Path) -> list[str]:
    """Drop the stale generated credentials from `environ`, so `.env` is the one source. Returns the names dropped."""
    names = stale_credentials(environ, path)
    for name in names:
        del environ[name]
    return names

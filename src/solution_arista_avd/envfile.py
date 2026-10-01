"""Read and write the repository's gitignored `.env`.

Three callers keep generated credentials there -- `tasks.py` and the two
`scripts/provision_*.py` scripts -- and each used to carry its own copy of these
two functions. The copies drifted: one deleted the old `NAME=` line but kept the
comment above it, so every re-mint left another orphaned comment behind.

Host-side only. Nothing that runs in the Infrahub image imports this.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


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

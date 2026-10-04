"""`invoke demo-restore`: what to take out of the lab to return it to the seeded baseline.

The seeded baseline is whatever the object files under ``objects/`` declare. Anything else of the
kinds a demo creates (an application and the access grants to it) was made by a presenter, so the
restore withdraws it. Only pure functions live here; ``tasks.py`` does the I/O. Host-side only.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable

# Kinds a demo creates, grants first: a grant names its application, so it is withdrawn before it.
DEMO_KINDS = ("ServiceAppAccess", "ServiceFabricApp")
# The seeded applications share this prefix; a name that starts with it is baseline whatever the files say.
SEEDED_PREFIX = "otternet-"
# A branch the restore itself creates, so an interrupted run can find and remove it.
RESTORE_BRANCH_PREFIX = "restore-"


def seeded_names(documents: Iterable[str], kinds: Iterable[str] = DEMO_KINDS) -> dict[str, set[str]]:
    """The object names the seed files declare, per kind in ``kinds``."""
    wanted = tuple(kinds)
    names: dict[str, set[str]] = {kind: set() for kind in wanted}
    for text in documents:
        for doc in yaml.safe_load_all(text):
            spec = (doc or {}).get("spec") if isinstance(doc, dict) else None
            if not isinstance(spec, dict) or spec.get("kind") not in names:
                continue
            for item in spec.get("data") or []:
                if isinstance(item, dict) and item.get("name"):
                    names[spec["kind"]].add(str(item["name"]))
    return names


def demo_created(existing: Iterable[str], seeded: set[str]) -> list[str]:
    """Names on ``main`` that a presenter created: not in the seed files and not an ``otternet-`` baseline name."""
    return sorted(name for name in existing if name not in seeded and not name.startswith(SEEDED_PREFIX))


def generator_records_for(names: set[str], records: Iterable[tuple[str, str, str]]) -> list[tuple[str, str]]:
    """``(kind, id)`` of the generator instances and tracking groups that belong to ``names``.

    ``records`` are ``(kind, id, label)`` rows: an instance is labelled ``<generator>: <name>`` and its
    tracking group by a description ``name: <name>``. Deleting a service leaves both behind, and an
    instance whose object is gone breaks the generator for every later proposed change.
    """
    found = []
    for kind, node_id, label in records:
        if any(label.endswith((f": {n}", f"(name: {n})")) for n in names):
            found.append((kind, node_id))
    return found


def is_restore_branch(name: str) -> bool:
    return name.startswith(RESTORE_BRANCH_PREFIX)


_RUN = re.compile(r"(\d+)")


def used_runs(name: str, branch_names: Iterable[str]) -> list[int]:
    """The release numbers already taken for ``name``, from any list of branch or ref names.

    A release branch is ``demo/<name>-<run>``. A reset branch (``-reset-<time>``) is not a release.
    """
    pattern = re.compile(rf"(?:refs/heads/)?demo/{re.escape(name)}-(\d+)")
    return sorted({int(m.group(1)) for b in branch_names if (m := pattern.fullmatch(b))})


def next_run(name: str, branch_names: Iterable[str]) -> int:
    """The first release number that no branch, ref or worker clone has used."""
    runs = used_runs(name, branch_names)
    return (runs[-1] + 1) if runs else 1


def latest_run(name: str, branch_names: Iterable[str]) -> int:
    """The most recent release number in use, or 1 when there is none."""
    runs = used_runs(name, branch_names)
    return runs[-1] if runs else 1

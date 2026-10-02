"""`invoke demo-release`: bring a staged capability branch into Infrahub on cue.

The demo needs a branch that arrives from the Git remote, is synced into
Infrahub, and is ready for a proposed change, without the branch existing in
Infrahub beforehand. Three facts shape it:

* Infrahub only imports remote branches whose names match
  ``INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES``. The prepared work lives on
  ``stage/<name>``, which never matches, so it can sit on the remote unsynced.
  Pushing it to ``demo/<name>-<run>`` is the trigger.
* ``.infrahub.yml`` carries no ``schemas:`` or ``objects:`` section, so a Git
  push delivers code (queries, transforms, checks, menus) and nothing else.
  Schema and data are loaded onto the Infrahub branch directly.
* A commit Infrahub has pulled is never rewritten, so every release uses a new
  ``-<run>`` suffix.

Only pure functions live here; ``tasks.py`` does the I/O. Host-side only.
"""

from __future__ import annotations

import json
import re

STAGE_PREFIX = "stage/"
DEMO_PREFIX = "demo/"

# Only characters that are safe in a Git ref, an Infrahub branch name and a shell word.
_SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


class DemoReleaseError(ValueError):
    """A release that cannot be built from the arguments it was given."""


def _checked(name: str) -> str:
    if not _SAFE_NAME.fullmatch(name):
        msg = f"{name!r} is not a usable demo name: lowercase letters, digits and hyphens, starting with one"
        raise DemoReleaseError(msg)
    return name


def stage_branch(name: str) -> str:
    """The local (and optionally remote) branch holding the prepared work."""
    return f"{STAGE_PREFIX}{_checked(name)}"


def demo_branch(name: str, run: int) -> str:
    """The remote branch whose creation makes Infrahub import the work."""
    if run < 1:
        msg = f"run must be 1 or more, got {run}"
        raise DemoReleaseError(msg)
    return f"{DEMO_PREFIX}{_checked(name)}-{run}"


def refspec(name: str, run: int) -> str:
    """``git push origin <refspec>``: the staged branch, published under the synced name."""
    return f"{stage_branch(name)}:{demo_branch(name, run)}"


def parse_patterns(raw: str) -> list[str]:
    """The JSON array ``INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES`` holds."""
    try:
        patterns = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES is not a JSON array: {raw!r}"
        raise DemoReleaseError(msg) from exc
    if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
        msg = f"INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES is not a JSON array of strings: {raw!r}"
        raise DemoReleaseError(msg)
    return patterns


def is_imported(patterns: list[str], branch: str) -> bool:
    """Infrahub's own rule: a name or regex, tried with ``re.fullmatch``."""
    return any(re.fullmatch(pattern, branch) for pattern in patterns)


def demo_filter(existing: list[str]) -> str:
    """The override that lets ``demo/`` branches in, keeping whatever was already allowed."""
    patterns = list(existing)
    if f"{DEMO_PREFIX}.*" not in patterns:
        patterns.append(f"{DEMO_PREFIX}.*")
    return json.dumps(patterns, separators=(",", ":"))


def render_repository(url: str, *, repository_name: str = "test-repository", credential: str | None = None) -> str:
    """The ``CoreRepository`` object file for a remote, as ``infrahubctl object load`` reads it.

    ``credential`` is the name of a ``CoreCredential`` that already exists on the
    stack. The secret itself is never written here.
    """
    if not url.startswith(("https://", "http://", "ssh://", "git@")):
        msg = f"{url!r} does not look like a Git remote URL"
        raise DemoReleaseError(msg)
    lines = [
        "---",
        "apiVersion: infrahub.app/v1",
        "kind: Object",
        "spec:",
        "  kind: CoreRepository",
        "  data:",
        f"    - name: {repository_name}",
        f"      location: {json.dumps(url)}",
    ]
    if credential:
        lines.append(f"      credential: {json.dumps(credential)}")
    return "\n".join(lines) + "\n"


def render_credential(name: str, username: str, password: str) -> str:
    """A username and token credential object file, for the caller to load and delete."""
    return (
        "---\n"
        "apiVersion: infrahub.app/v1\n"
        "kind: Object\n"
        "spec:\n"
        "  kind: CorePasswordCredential\n"
        "  data:\n"
        f"    - name: {json.dumps(name)}\n"
        f"      username: {json.dumps(username)}\n"
        f"      password: {json.dumps(password)}\n"
    )


def proposed_change_mutation(source_branch: str, name: str, description: str) -> str:
    """The GraphQL that opens a proposed change into ``main``."""
    return (
        "mutation { CoreProposedChangeCreate(data: {"
        f" name: {{ value: {json.dumps(name)} }}"
        f" description: {{ value: {json.dumps(description)} }}"
        f" source_branch: {{ value: {json.dumps(source_branch)} }}"
        ' destination_branch: { value: "main" }'
        " }) { object { id } } }"
    )

"""`invoke demo-release`: bring a staged capability branch into Infrahub on cue.

The demo needs prepared work that arrives from the Git remote and is reviewed as
a proposed change, without Infrahub ever holding the branch. Four facts shape it:

* The repository is a ``CoreReadOnlyRepository``. It tracks one ``ref`` and
  imports it into Infrahub's default branch, so no Infrahub branch is created
  from Git and Infrahub never pushes. A ``CoreRepository`` does both, which
  needs a write credential on the remote. Changing ``ref`` is the whole trigger.
* The prepared work lives on ``stage/<name>``; releasing it publishes it as
  ``demo/<name>-<run>`` so the ref can name something on the remote.
* ``.infrahub.yml`` carries no ``schemas:`` or ``objects:`` section, so moving
  the ref delivers code (queries, transforms, checks, menus) and nothing else.
  Schema and data are loaded onto a plain Infrahub branch and reviewed there.
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


def render_repository(
    url: str, *, ref: str = "main", repository_name: str = "test-repository", credential: str | None = None
) -> str:
    """The read-only repository object file for a remote, as ``infrahubctl object load`` reads it.

    ``credential`` is the name of a ``CoreCredential`` that already exists on the
    stack. The secret itself is never written here.
    """
    if not url.startswith(("https://", "http://", "ssh://", "git@")):
        msg = f"{url!r} does not look like a Git remote URL"
        raise DemoReleaseError(msg)
    if not ref.strip():
        msg = "a repository ref is required"
        raise DemoReleaseError(msg)
    lines = [
        "---",
        "apiVersion: infrahub.app/v1",
        "kind: Object",
        "spec:",
        "  kind: CoreReadOnlyRepository",
        "  data:",
        f"    - name: {repository_name}",
        f"      location: {json.dumps(url)}",
        f"      ref: {json.dumps(ref)}",
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


def set_ref_mutation(repository_id: str, ref: str) -> str:
    """The GraphQL that points the read-only repository at another ref."""
    return (
        "mutation { CoreReadOnlyRepositoryUpdate(data: {"
        f" id: {json.dumps(repository_id)} ref: {{ value: {json.dumps(ref)} }}"
        " }) { ok } }"
    )


def absent_schema(namespace: str, name: str) -> str:
    """A schema file that marks one node absent: how a loaded kind is taken back out."""
    return (
        'version: "1.0"\n'
        "nodes:\n"
        f"  - name: {json.dumps(name)}\n"
        f"    namespace: {json.dumps(namespace)}\n"
        "    state: absent\n"
    )

"""Ask Infrahub to re-render one target's artifact, on the generator's own branch.

Shared by every generator that changes something an artifact renders from. Two
measured traps are why this exists rather than `Node.artifact_generate`:

* **The SDK helper omits `?branch=`.** It posts to
  `/api/artifact/generate/{id}` with no branch, and that endpoint regenerates
  against `main` when none is given. On a branch the objects were written, the
  generator logged that it had asked for a re-render, and the branch's artifact
  kept its old checksum -- a proposed change showing the data and no
  configuration diff. `_post` is private, and is what the SDK's own `generate()`
  uses; there is no public call that takes a branch.
* **`nodes` names the ARTIFACT, not its target.** Passing the target's id is
  accepted, returns 200, and regenerates nothing.

It lives beside the generators rather than in `src/solution_arista_avd/`
because the task workers import that package from the image, so a new module
there is invisible to them until the image is rebuilt.

The caller decides what a failure means. Every caller so far treats it as best
effort -- its objects are already written, and raising would skip the tracking
context's `update_group` -- so callers wrap this in their own `try`.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote


async def request_artifact_render(
    client: Any,
    *,
    artifact_name: str,
    target_id: str,
    branch: str | None,
    first_render: bool = False,
) -> bool:
    """POST a render request for `artifact_name` on `target_id`; return whether one was sent.

    Before the first render no `CoreArtifact` exists for the target. With
    `first_render` the request is sent with an empty `nodes` list, which asks
    for every member of the definition's group -- the first render. Without it
    nothing is sent and False is returned, because the artifact definition will
    render it when it first runs and a whole-group render is not this caller's
    to ask for.

    Raises on any client or HTTP failure, including a non-2xx response.
    """
    definition = await client.get(
        kind="CoreArtifactDefinition",
        artifact_name__value=artifact_name,
        branch=branch,
    )
    artifacts = await client.filters(
        kind="CoreArtifact",
        name__value=artifact_name,
        object__ids=[target_id],
        branch=branch,
    )
    if not artifacts and not first_render:
        return False

    url = f"{client.address}/api/artifact/generate/{definition.id}"
    if branch:
        url = f"{url}?branch={quote(branch, safe='')}"
    response = await client._post(url, payload={"nodes": [artifact.id for artifact in artifacts]})  # noqa: SLF001
    response.raise_for_status()
    return True

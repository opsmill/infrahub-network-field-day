"""Read and write the deployment state cycle 029 modelled.

This service is the only writer of `DeploymentState`, with two exceptions it
must never touch: **`suspend` and `suspend_reason` belong to the operator.** A
reconciler that clears its own break-glass is not a break-glass.

The semantics that matter, both settled under challenge in the design review:

* **`last_confirmed_at` moves only when the device itself reported no
  difference.** Never because a push was sent. The record is a claim about the
  network, not about what this service did.
* **`last_checked_at` moves on every comparison**, including ones that find a
  difference and ones that fail. Without it a stale `last_confirmed_at` is
  ambiguous between "this device is fine" and "the loop died a week ago".

Write cadence (spec FR-028, decided in research R8): `last_checked_at` every
cycle, everything else only when it changes. Infrahub versions every mutation,
so writing all seven fields every cycle would be roughly 2,000 versioned writes
a day across this fabric to say nothing new.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from solution_arista_avd.protocols import DeploymentState

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

KIND_STATE = "DeploymentState"
KIND_DIFF = "DeploymentDiffFile"

STATUS_NEVER = "never_deployed"
STATUS_IN_SYNC = "in_sync"
STATUS_PENDING = "pending"
STATUS_DRIFTED = "drifted"
STATUS_FAILED = "failed"


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Outcome:
    """What one cycle decided about one device."""

    device: str
    status: str
    confirmed: bool = False
    error: str | None = None
    diff: str | None = None
    pushed: bool = False
    checksum: str | None = None


class StateStore:
    """The `Deployment` kinds, as this service uses them.

    Always on `main`: deployment state is a fact about the physical world, and
    the kinds are branch-agnostic so there is nothing to scope anyway.
    """

    def __init__(self, client: InfrahubClient) -> None:
        self._client = client

    async def record(self, outcome: Outcome) -> None:
        """Upsert one device's record.

        Upsert on `name`, never create: the graph enforces uniqueness on `name`
        rather than on the device relationship, so creating blindly would either
        fail or -- worse, if the constraint were ever relaxed -- leave two
        records disagreeing about the same device.
        """
        existing = await self._client.get(
            kind=DeploymentState, hfid=[outcome.device], branch="main", raise_when_missing=False
        )
        fields: dict[str, Any] = {"last_checked_at": _now()}

        if outcome.confirmed:
            fields["last_confirmed_at"] = _now()
        if outcome.pushed:
            fields["last_attempt_at"] = _now()
        if outcome.error is not None:
            fields["last_error"] = outcome.error
        if outcome.checksum is not None:
            fields["last_artifact_checksum"] = outcome.checksum

        if existing is None:
            node = await self._client.create(
                kind=DeploymentState, branch="main", name=outcome.device, status=outcome.status, **fields
            )
            await node.save()
            return

        # Only write what actually changed, plus the heartbeat.
        if existing.status.value != outcome.status:
            existing.status.value = outcome.status
        if outcome.error is None and existing.last_error.value:
            existing.last_error.value = None  # a success clears the last failure
        for name, value in fields.items():
            getattr(existing, name).value = value
        await existing.save()

    async def last_checksum(self, device: str) -> str | None:
        """The artifact checksum this device was last reconciled against.

        Absent for a device never reconciled, which is why an unexplained
        difference is reported as drift rather than as a pending change.
        """
        record = await self._client.get(kind=DeploymentState, hfid=[device], branch="main", raise_when_missing=False)
        return str(record.last_artifact_checksum.value) if record and record.last_artifact_checksum.value else None

    async def is_suspended(self, device: str) -> bool:
        """Whether the operator has taken this device out of the loop.

        Read before the device is reached, so a suspended device is never
        connected to -- no session opened, no lock taken.
        """
        record = await self._client.get(kind=DeploymentState, hfid=[device], branch="main", raise_when_missing=False)
        return bool(record and record.suspend.value)

    async def sweep_orphans(self, live_devices: set[str]) -> list[str]:
        """Delete records whose device no longer exists.

        Cycle 029 measured why this is the service's job and not the schema's: a
        mandatory device relationship makes any device that has ever held a
        record permanently undeletable, so the relationship is optional and
        orphans are possible by design.
        """
        removed: list[str] = []
        for record in await self._client.all(kind=DeploymentState, branch="main"):
            if record.name.value not in live_devices:
                await record.delete()
                removed.append(str(record.name.value))
        return removed

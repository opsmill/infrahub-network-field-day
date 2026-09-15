"""Integration coverage for what the reconciler writes to Infrahub.

Boots a real Infrahub via ``infrahub-testcontainers``, loads this repo's schemas,
and drives ``StateStore`` against it. The device half of the cycle cannot be
covered here -- a testcontainer has no ContainerLab fabric to reach -- so it is
covered instead by unit tests over **real captured device output** in
``tests/unit/test_deployment_normalise.py`` plus live validation against the lab.

What this file pins is the half that unit tests with a fake client cannot prove:
that the semantics survive contact with a real graph.

- ``last_confirmed_at`` moves only on a confirmed match, never on a push. That
  distinction is the whole reason deployment state lives in Infrahub rather than
  in the executor.
- Upserting on ``name`` produces one record per device across repeated cycles.
  The graph enforces uniqueness on ``name`` rather than on the device
  relationship (cycle 029), so a second cycle creating a duplicate would be a
  real possibility if the writer got it wrong.
- ``suspend`` is read and never written.
- A record whose device is gone is swept.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

from solution_arista_avd.deployment.state import (
    STATUS_DRIFTED,
    STATUS_IN_SYNC,
    Outcome,
    StateStore,
)

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient


class TestReconcilerState(TestInfrahubDockerClient):
    async def _schema_loaded(self, client: InfrahubClient, default_branch: str, schemas: list[dict[str, Any]]) -> None:
        await client.schema.load(schemas=schemas, branch=default_branch, wait_until_converged=True)

    @pytest.fixture(scope="class")
    async def store(self, client: InfrahubClient) -> StateStore:
        return StateStore(client)

    async def test_a_confirmed_match_records_confirmation(
        self, default_branch: str, client: InfrahubClient, schemas: list[dict[str, Any]]
    ) -> None:
        await self._schema_loaded(client, default_branch, schemas)
        store = StateStore(client)

        await store.record(Outcome(device="leaf-int-1", status=STATUS_IN_SYNC, confirmed=True, checksum="c1"))

        record = await client.get(kind="DeploymentState", hfid=["leaf-int-1"], branch="main")
        assert record.status.value == STATUS_IN_SYNC
        assert record.last_confirmed_at.value is not None
        assert record.last_checked_at.value is not None
        assert record.last_artifact_checksum.value == "c1"

    async def test_a_push_moves_checked_but_not_confirmed(
        self, default_branch: str, client: InfrahubClient, schemas: list[dict[str, Any]]
    ) -> None:
        """The record is a claim about the network, not about what we did."""
        await self._schema_loaded(client, default_branch, schemas)
        store = StateStore(client)

        await store.record(Outcome(device="leaf-int-2", status=STATUS_DRIFTED, pushed=True, checksum="c1"))

        record = await client.get(kind="DeploymentState", hfid=["leaf-int-2"], branch="main")
        assert record.status.value == STATUS_DRIFTED
        assert record.last_confirmed_at.value is None
        assert record.last_checked_at.value is not None
        assert record.last_attempt_at.value is not None

    async def test_repeated_cycles_produce_one_record_per_device(
        self, default_branch: str, client: InfrahubClient, schemas: list[dict[str, Any]]
    ) -> None:
        await self._schema_loaded(client, default_branch, schemas)
        store = StateStore(client)

        for _ in range(3):
            await store.record(Outcome(device="leaf-int-3", status=STATUS_IN_SYNC, confirmed=True, checksum="c1"))

        records = await client.all(kind="DeploymentState", branch="main")
        assert len([r for r in records if r.name.value == "leaf-int-3"]) == 1

    async def test_suspension_is_read_and_never_written(
        self, default_branch: str, client: InfrahubClient, schemas: list[dict[str, Any]]
    ) -> None:
        await self._schema_loaded(client, default_branch, schemas)
        store = StateStore(client)

        await store.record(Outcome(device="fw-int", status=STATUS_IN_SYNC, confirmed=True))
        record = await client.get(kind="DeploymentState", hfid=["fw-int"], branch="main")
        record.suspend.value = True
        record.suspend_reason.value = "integration"
        await record.save()

        assert await store.is_suspended("fw-int") is True

        # A later cycle must not clear the operator's break-glass.
        await store.record(Outcome(device="fw-int", status=STATUS_IN_SYNC, confirmed=True))
        after = await client.get(kind="DeploymentState", hfid=["fw-int"], branch="main")
        assert after.suspend.value is True
        assert after.suspend_reason.value == "integration"

    async def test_a_record_whose_device_is_gone_is_swept(
        self, default_branch: str, client: InfrahubClient, schemas: list[dict[str, Any]]
    ) -> None:
        await self._schema_loaded(client, default_branch, schemas)
        store = StateStore(client)

        await store.record(Outcome(device="retired-int", status=STATUS_IN_SYNC, confirmed=True))
        removed = await store.sweep_orphans({"leaf-int-1"})

        assert "retired-int" in removed
        gone = await client.get(kind="DeploymentState", hfid=["retired-int"], branch="main", raise_when_missing=False)
        assert gone is None

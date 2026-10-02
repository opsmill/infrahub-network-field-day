from pathlib import Path

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import CoreGenericRepository
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo

from .helpers import REPO_SYNC_INTERVAL, REPO_SYNC_RETRIES


class TestInfrahub(TestInfrahubDockerClient):
    @pytest.mark.asyncio
    async def test_load_schema(self, default_branch: str, client: InfrahubClient, schemas: list[dict]) -> None:
        await client.schema.wait_until_converged(branch=default_branch)

        resp = await client.schema.load(schemas=schemas, branch=default_branch, wait_until_converged=True)
        await client.schema.wait_until_converged(branch=default_branch)
        assert resp.errors == {}

    @pytest.mark.asyncio
    async def test_load_objects(
        self,
        default_branch: str,
        client: InfrahubClient,
        schemas: list[dict],
        infrahub_port: int,
    ) -> None:
        """Load schemas then load all object files via infrahubctl object load."""
        await client.schema.wait_until_converged(branch=default_branch)

        resp = await client.schema.load(schemas=schemas, branch=default_branch, wait_until_converged=True)
        assert resp.errors == {}, f"Schema load errors: {resp.errors}"
        await client.schema.wait_until_converged(branch=default_branch)

        infrahub_address = f"http://localhost:{infrahub_port}"
        result = self.execute_command(
            address=infrahub_address,
            command="infrahubctl object load objects/",
        )
        print(result.stdout, flush=True)
        if result.stderr:
            print(result.stderr, flush=True)
        assert result.returncode == 0, f"infrahubctl object load failed:\n{result.stdout}\n{result.stderr}"

        # Verify key objects were created with the new kind names
        manufacturers = await client.all(kind="OrganizationManufacturer")
        assert len(manufacturers) > 0, "No manufacturers loaded"

        device_types = await client.all(kind="DcimDeviceType")
        assert len(device_types) > 0, "No device types loaded"

    @pytest.mark.asyncio
    async def test_load_repository(
        self,
        client: InfrahubClient,
        remote_repos_dir: Path,
        repository_source: Path,
    ) -> None:
        """Add the local directory as a repository in Infrahub and wait for the import to be complete"""

        repo = GitRepo(
            name="local-repository",
            src_directory=repository_source,
            dst_directory=remote_repos_dir,
        )
        await repo.add_to_infrahub(client=client)
        # The SDK's default budget is 6 x 5s. Importing this repository's
        # queries, generators, transforms, checks and artifact definitions
        # measured 35-66s on 1.10.6, so the default reported a healthy import as
        # a failure. A real `error-import` still returns False at once.
        in_sync = await repo.wait_for_sync_to_complete(
            client=client, interval=REPO_SYNC_INTERVAL, retries=REPO_SYNC_RETRIES
        )
        if not in_sync:
            synced = await client.get(kind=CoreGenericRepository, name__value=repo.name)
            msg = f"repository '{repo.name}' did not reach in-sync; status={synced.sync_status.value}"
            raise AssertionError(msg)

        repos = await client.all(kind=CoreGenericRepository)

        # A breakpoint can be added to pause the tests from running and keep the test containers active
        # breakpoint()

        assert repos

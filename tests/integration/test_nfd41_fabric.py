"""End-to-end test that Infrahub reproduces the deployed NFD41 lab exactly.

Boots a real Infrahub stack via ``infrahub-testcontainers``, loads this
repository's schemas and seed objects, registers the repository, and runs the
generator chain against the ``NFD41_FABRIC`` design. It then renders the AVD EOS
configuration artifact for each of the seven switches and asserts it matches the
configuration the running lab is deployed with, byte for byte
(``tests/integration/golden/nfd41``).

That is the claim the fork exists to prove: the source of truth moves from
static AVD ``group_vars`` into Infrahub and nothing on the wire changes. A diff
here is a real regression -- either the data model lost something, or the
generator stopped emitting it.

The stack is class-scoped and the tests are ordered, so each stage's failure
message points at the stage that broke. Running one test in isolation fails,
because it depends on the state the earlier ones built.

Heavy: select with ``-m e2e``, exclude with ``-m "not e2e"``.
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import CoreGenericRepository
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo

from .helpers import (
    ARTIFACT_AVD_EOS_CONFIG,
    ARTIFACT_TIMEOUT,
    GENERATOR_FABRIC,
    GENERATOR_TIMEOUT,
    POLL_INTERVAL,
    REPO_SYNC_INTERVAL,
    REPO_SYNC_RETRIES,
    wait_until,
)

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

REPO_NAME = "nfd41-repository"
# The trigger cascade only fires off `main`, so the generators run on a branch —
# which is also how a real change to this fabric would be made.
PIPELINE_BRANCH = "nfd41-pipeline"
FABRIC_NAME = "NFD41_FABRIC"
POD_NAME = "nfd41-pod1"

GOLDEN_DIR = Path(__file__).parent / "golden" / "nfd41"

# What transforms/avd_eos_config.py renders when the device has no stored
# structured config yet. The trigger cascade renders the artifact once as soon
# as the device exists, so a stale copy carrying this marker is present before
# the AVD stages finish -- waiting only for "an artifact exists" would compare
# against that instead of the real configuration.
NO_STRUCTURED_CONFIG_MARKER = "! No structured config available"

SPINES = ["spine1", "spine2"]
LEAVES = ["k8s-leaf1", "k8s-leaf2", "app-leaf1", "app-leaf2", "border-leaf1"]
DEVICES = [*SPINES, *LEAVES]

# The uplink each leaf takes on each spine, from lab/nfd41.clab.yml. Pinned here
# because it decides which spine port carries which /31, so a fabric that cables
# itself differently renders a different spine configuration even though every
# address is still correct.
EXPECTED_UPLINKS = {
    "k8s-leaf1": ["Ethernet1", "Ethernet1"],
    "k8s-leaf2": ["Ethernet2", "Ethernet2"],
    "app-leaf1": ["Ethernet3", "Ethernet3"],
    "app-leaf2": ["Ethernet4", "Ethernet4"],
    "border-leaf1": ["Ethernet5", "Ethernet5"],
}

# ASNs are per MLAG pair, not per switch.
EXPECTED_ASNS = {
    "spine1": 65100,
    "spine2": 65100,
    "k8s-leaf1": 65101,
    "k8s-leaf2": 65101,
    "app-leaf1": 65102,
    "app-leaf2": 65102,
    "border-leaf1": 65103,
}

EXPECTED_NODE_IDS = {
    "spine1": 1,
    "spine2": 2,
    "k8s-leaf1": 1,
    "k8s-leaf2": 2,
    "app-leaf1": 3,
    "app-leaf2": 4,
    "border-leaf1": 5,
}


@pytest.mark.e2e
class TestNfd41Fabric(TestInfrahubDockerClient):
    """Design-to-configuration parity with the running NFD41 lab."""

    @pytest.fixture(scope="class", autouse=True)
    def _client_timeout(self) -> None:
        # The fabric generator issues large GraphQL reads/writes that can exceed
        # the 60s default under load.
        os.environ.setdefault("INFRAHUB_TIMEOUT", "300")

    @staticmethod
    def _address(infrahub_port: int) -> str:
        return f"http://localhost:{infrahub_port}"

    # --- stage 1: schema ---------------------------------------------------
    @pytest.mark.asyncio(loop_scope="class")
    async def test_load_schema(self, default_branch: str, client: InfrahubClient, schemas: list[dict]) -> None:
        await client.schema.wait_until_converged(branch=default_branch)
        resp = await client.schema.load(schemas=schemas, branch=default_branch, wait_until_converged=True)
        assert resp.errors == {}, f"schema load errors: {resp.errors}"
        await client.schema.wait_until_converged(branch=default_branch)

    # --- stage 2: seed objects --------------------------------------------
    @pytest.mark.asyncio(loop_scope="class")
    async def test_load_objects(self, default_branch: str, client: InfrahubClient, infrahub_port: int) -> None:
        result = self.execute_command(command="infrahubctl object load objects/", address=self._address(infrahub_port))
        print(result.stdout, flush=True)
        if result.stderr:
            print(result.stderr, flush=True)
        assert result.returncode == 0, f"object load failed:\n{result.stdout}\n{result.stderr}"

        fabrics = await client.filters(kind="NetworkFabric", name__value=FABRIC_NAME, branch=default_branch)
        assert fabrics, f"{FABRIC_NAME} was not loaded"

    # --- stage 3: the pinned device identity survived the load ------------
    @pytest.mark.asyncio(loop_scope="class")
    async def test_seeded_devices_carry_lab_identity(self, default_branch: str, client: InfrahubClient) -> None:
        """The seven switches load with the hostname, node ID and ASN the lab runs.

        This is asserted before the generators run so a later mismatch is
        unambiguously the generators overwriting pinned data rather than bad seed
        data.
        """
        report = await _device_identity_report(client, default_branch)
        assert sorted(report) == sorted(DEVICES), f"seeded devices: {sorted(report)}"
        assert {name: entry["node_id"] for name, entry in report.items()} == EXPECTED_NODE_IDS
        assert {name: entry["asn"] for name, entry in report.items()} == EXPECTED_ASNS

    # --- stage 4: repository ----------------------------------------------
    @pytest.mark.asyncio(loop_scope="class")
    async def test_register_repository(
        self, default_branch: str, client: InfrahubClient, root_directory: Path, remote_repos_dir: Path
    ) -> None:
        repo = GitRepo(name=REPO_NAME, src_directory=root_directory, dst_directory=remote_repos_dir)
        await repo.add_to_infrahub(client=client)
        in_sync = await repo.wait_for_sync_to_complete(
            client=client, interval=REPO_SYNC_INTERVAL, retries=REPO_SYNC_RETRIES
        )
        if not in_sync:
            synced = await client.get(kind=CoreGenericRepository, name__value=REPO_NAME, branch=default_branch)
            msg = f"repository '{REPO_NAME}' did not reach in-sync; status={synced.sync_status.value}"
            raise AssertionError(msg)

    # --- stage 5: trigger rules -------------------------------------------
    @pytest.mark.asyncio(loop_scope="class")
    async def test_load_triggers(self, infrahub_port: int) -> None:
        """Load the event rules that cascade pod -> rack -> hostvars -> structured config.

        After the repository sync: the trigger actions reference generators by
        name, which only exist once the repository has registered them.
        """
        result = self.execute_command(
            command="infrahubctl object load triggers.yml", address=self._address(infrahub_port)
        )
        print(result.stdout, flush=True)
        if result.stderr:
            print(result.stderr, flush=True)
        assert result.returncode == 0, f"trigger load failed:\n{result.stdout}\n{result.stderr}"

    # --- stage 6: branch --------------------------------------------------
    @pytest.mark.asyncio(loop_scope="class")
    async def test_create_branch(self, client: InfrahubClient) -> None:
        await client.branch.create(branch_name=PIPELINE_BRANCH, sync_with_git=False)
        fabrics = await client.filters(kind="NetworkFabric", name__value=FABRIC_NAME, branch=PIPELINE_BRANCH)
        assert fabrics, f"{FABRIC_NAME} is not present on {PIPELINE_BRANCH}"

    # --- stage 7: run the generator chain ---------------------------------
    @pytest.mark.asyncio(loop_scope="class")
    async def test_fabric_generator_cascade(self, client: InfrahubClient, infrahub_port: int) -> None:
        """Kick off the fabric generator; the rest cascades through triggers."""
        result = self.execute_command(
            command=f"infrahubctl generator {GENERATOR_FABRIC} --branch {PIPELINE_BRANCH}",
            address=self._address(infrahub_port),
        )
        print(result.stdout, flush=True)
        if result.stderr:
            print(result.stderr, flush=True)
        assert result.returncode == 0, f"fabric generator failed:\n{result.stdout}\n{result.stderr}"

        await wait_until(
            fetch=lambda: _device_names(client, PIPELINE_BRANCH),
            ready=lambda names: set(DEVICES).issubset(names),
            timeout=GENERATOR_TIMEOUT,
            interval=POLL_INTERVAL,
            describe="the seven NFD41 switches after the generator cascade",
        )

    # --- stage 8: the generators did not renumber the fabric --------------
    @pytest.mark.asyncio(loop_scope="class")
    async def test_generators_preserved_lab_identity(self, client: InfrahubClient) -> None:
        """No extra devices, and no renumbering of the pinned identity.

        The naming templates are what make this hold: without them the pod and
        rack generators would create a second set of devices under their own
        default names and leave the pinned ones uncabled.
        """
        report = await _device_identity_report(client, PIPELINE_BRANCH)
        assert sorted(report) == sorted(DEVICES), (
            f"unexpected device set after generation: {sorted(report)} (extras: {sorted(set(report) - set(DEVICES))})"
        )
        assert {name: entry["node_id"] for name, entry in report.items()} == EXPECTED_NODE_IDS
        assert {name: entry["asn"] for name, entry in report.items()} == EXPECTED_ASNS

    # --- stage 9: the fabric cabled itself onto the lab's ports -----------
    @pytest.mark.asyncio(loop_scope="class")
    async def test_uplink_cabling_matches_lab(self, client: InfrahubClient) -> None:
        uplinks = await wait_until(
            fetch=lambda: _uplink_report(client, PIPELINE_BRANCH),
            ready=lambda report: all(len(ports) == 2 for ports in report.values()) and len(report) == len(LEAVES),
            timeout=GENERATOR_TIMEOUT,
            interval=POLL_INTERVAL,
            describe="each leaf cabled to both spines",
        )
        assert uplinks == EXPECTED_UPLINKS

    # --- stage 10: hostvars and structured config exist for every switch --
    @pytest.mark.asyncio(loop_scope="class")
    async def test_hostvars_and_structured_config_generated(self, client: InfrahubClient) -> None:
        """Wait for the AVD stages the EOS artifact renders from.

        The artifact transform reads the *stored* structured config, so
        triggering it before this cascade lands renders
        `! No structured config available for <host>` rather than failing --
        which reads as a data-model bug instead of a race.
        """
        ready = await wait_until(
            fetch=lambda: _avd_artifact_report(client, PIPELINE_BRANCH),
            ready=lambda report: all(
                report.get(hostname, {}).get("hostvars") and report.get(hostname, {}).get("structured_config")
                for hostname in DEVICES
            ),
            timeout=GENERATOR_TIMEOUT,
            interval=POLL_INTERVAL,
            describe="AVD hostvars and structured config for all seven switches",
        )
        missing = {
            hostname: entry
            for hostname, entry in ((hostname, ready.get(hostname, {})) for hostname in DEVICES)
            if not (entry.get("hostvars") and entry.get("structured_config"))
        }
        assert not missing, f"switches without a complete AVD pipeline: {missing}"

    # --- stage 11: rendered configuration matches the running lab ---------
    @pytest.mark.asyncio(loop_scope="class")
    async def test_rendered_config_matches_deployed_lab(self, client: InfrahubClient) -> None:
        """Every switch's rendered EOS configuration equals the lab's, byte for byte."""
        definitions = await client.filters(
            kind="CoreArtifactDefinition", artifact_name__value=ARTIFACT_AVD_EOS_CONFIG, branch=PIPELINE_BRANCH
        )
        assert definitions, f"no artifact definition named {ARTIFACT_AVD_EOS_CONFIG!r}"
        for definition in definitions:
            # The node `.generate()` helper posts without a branch, which targets
            # main -- and main has no generated devices in this flow. Hit the
            # branch-aware endpoint instead.
            resp = await client._post(
                f"{client.address}/api/artifact/generate/{definition.id}?branch={PIPELINE_BRANCH}",
                payload={"nodes": []},
            )
            resp.raise_for_status()

        rendered = await wait_until(
            fetch=lambda: _rendered_configs(client, PIPELINE_BRANCH),
            ready=lambda configs: (
                set(DEVICES).issubset(configs)
                and not any(NO_STRUCTURED_CONFIG_MARKER in content for content in configs.values())
            ),
            timeout=ARTIFACT_TIMEOUT,
            interval=POLL_INTERVAL,
            describe=f"a regenerated {ARTIFACT_AVD_EOS_CONFIG} artifact for all seven switches",
        )

        diffs: dict[str, str] = {}
        for hostname in DEVICES:
            expected = (GOLDEN_DIR / f"{hostname}.cfg").read_text()
            actual = rendered[hostname]
            if actual != expected:
                diffs[hostname] = "\n".join(
                    difflib.unified_diff(
                        expected.splitlines(),
                        actual.splitlines(),
                        fromfile=f"deployed-lab/{hostname}.cfg",
                        tofile=f"infrahub/{hostname}.cfg",
                        lineterm="",
                    )
                )

        if diffs:
            summary = "\n\n".join(f"=== {hostname} ===\n{diff}" for hostname, diff in sorted(diffs.items()))
            msg = f"{len(diffs)} of {len(DEVICES)} switches differ from the deployed lab:\n\n{summary}"
            raise AssertionError(msg)


# --------------------------------------------------------------------- helpers
async def _device_names(client: InfrahubClient, branch: str) -> set[str]:
    pods = await client.filters(kind="NetworkPod", name__value=POD_NAME, branch=branch)
    if not pods:
        return set()
    devices = await client.filters(kind="DcimDevice", pod__ids=[pods[0].id], branch=branch)
    return {device.name.value for device in devices}


async def _device_identity_report(client: InfrahubClient, branch: str) -> dict[str, dict[str, int | None]]:
    """Hostname -> node ID and ASN for every device in the NFD41 pod."""
    pods = await client.filters(kind="NetworkPod", name__value=POD_NAME, branch=branch)
    if not pods:
        return {}
    devices = await client.filters(kind="DcimDevice", pod__ids=[pods[0].id], branch=branch, include=["asn"])

    # `include` gives the relationship's peer id, not a hydrated node, so the
    # RoutingAsn is read on its own. Cached per id: the seven devices share four.
    asn_by_id: dict[str, int | None] = {}
    report: dict[str, dict[str, int | None]] = {}
    for device in devices:
        asn_id = getattr(getattr(device, "asn", None), "id", None)
        if asn_id and asn_id not in asn_by_id:
            asn_node = await client.get(kind="RoutingAsn", id=asn_id, branch=branch)
            asn_by_id[asn_id] = asn_node.asn.value
        report[device.name.value] = {
            "node_id": device.node_id.value,
            "asn": asn_by_id.get(asn_id) if asn_id else None,
        }
    return report


async def _uplink_report(client: InfrahubClient, branch: str) -> dict[str, list[str]]:
    """Leaf hostname -> the spine-side port each of its uplinks lands on, spine order.

    Read in one GraphQL pass over the links rather than per interface: the
    fabric has a few hundred links across all the example designs and a
    per-interface walk times out long before it finishes.
    """
    result = await client.execute_graphql(query=_LINK_ENDPOINTS_QUERY, branch_name=branch)

    report: dict[str, dict[str, str]] = {}
    for edge in result.get("NetworkLink", {}).get("edges", []):
        ends = []
        for endpoint_edge in edge["node"]["connected_endpoints"]["edges"]:
            node = endpoint_edge["node"]
            device = (node.get("device") or {}).get("node") or {}
            if node.get("name") and device.get("name"):
                ends.append((device["name"]["value"], node["name"]["value"]))
        if len(ends) != 2:
            continue
        for near, far in (ends, ends[::-1]):
            leaf_name, leaf_port = near
            spine_name, spine_port = far
            if leaf_name in LEAVES and spine_name in SPINES and leaf_port in {"Ethernet1", "Ethernet2"}:
                report.setdefault(leaf_name, {})[spine_name] = spine_port

    return {leaf: [ports[spine] for spine in SPINES if spine in ports] for leaf, ports in report.items()}


_LINK_ENDPOINTS_QUERY = """
query Nfd41LinkEndpoints {
  NetworkLink {
    edges {
      node {
        id
        connected_endpoints {
          edges {
            node {
              __typename
              # `device` peers the DcimGenericDevice generic, so `name` is
              # selected on the generic rather than through a DcimDevice
              # fragment -- narrowing would drop the server-facing links.
              ... on DcimInterface {
                name { value }
                device { node { name { value } } }
              }
              ... on InterfacePhysical {
                name { value }
                device { node { name { value } } }
              }
            }
          }
        }
      }
    }
  }
}
"""


async def _avd_artifact_report(client: InfrahubClient, branch: str) -> dict[str, dict[str, bool]]:
    """Hostname -> whether its AVD hostvars and structured config exist."""
    query = """
    query Nfd41AvdArtifacts {
      AvdArtifact {
        edges {
          node {
            name { value }
            hostvar_file { node { id } }
            structured_config_file { node { id } }
          }
        }
      }
    }
    """
    resp = await client.execute_graphql(query=query, branch_name=branch)
    report: dict[str, dict[str, bool]] = {}
    for edge in resp["AvdArtifact"]["edges"]:
        node = edge["node"]
        hostname = (node.get("name") or {}).get("value")
        if hostname not in DEVICES:
            continue
        report[hostname] = {
            "hostvars": bool((node.get("hostvar_file") or {}).get("node")),
            "structured_config": bool((node.get("structured_config_file") or {}).get("node")),
        }
    return report


async def _rendered_configs(client: InfrahubClient, branch: str) -> dict[str, str]:
    """Hostname -> rendered EOS configuration, for every artifact that is Ready.

    Content comes straight from the object store, and the target hostname from
    the artifact's `object` relationship, so this does not depend on any
    particular device having produced its artifact yet -- the caller polls.
    """
    query = (
        "query {\n"
        f'  CoreArtifact(name__value: "{ARTIFACT_AVD_EOS_CONFIG}") {{\n'
        "    edges { node {\n"
        "      status { value }\n"
        "      storage_id { value }\n"
        "      object { node { display_label } }\n"
        "    } }\n"
        "  }\n"
        "}"
    )
    resp = await client.execute_graphql(query=query, branch_name=branch)

    configs: dict[str, str] = {}
    for edge in resp["CoreArtifact"]["edges"]:
        node = edge["node"]
        if node.get("status", {}).get("value") != "Ready":
            continue
        storage_id = node.get("storage_id", {}).get("value")
        hostname = ((node.get("object") or {}).get("node") or {}).get("display_label")
        if not storage_id or hostname not in DEVICES:
            continue
        content = await client.object_store.get(identifier=storage_id)
        configs[hostname] = content if isinstance(content, str) else content.decode()
    return configs

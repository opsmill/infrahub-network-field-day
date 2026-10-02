"""Unit tests for AVD device structured config generator."""

import json
from unittest.mock import AsyncMock

import pytest
from pyavd import get_avd_facts, get_device_structured_config, validate_inputs

from generators.generate_avd_device_structured_config import (
    AvdDeviceStructuredConfigGenerator,
)
from generators.generate_avd_inputs_query import (
    GenerateAvdInputsQuery,
    GenerateAvdInputsQueryNetworkFabric,
    GenerateAvdInputsQueryNetworkFabricEdges,
    GenerateAvdInputsQueryNetworkFabricEdgesNode,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildren,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdges,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPod,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevices,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdges,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNode,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNodeAvdArtifact,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNodeAvdArtifactNode,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNodeAvdArtifactNodeHostvarFile,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNodeAvdArtifactNodeHostvarFileNode,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNodeName,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacks,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdges,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNode,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevices,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdges,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitch,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchAvdArtifact,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchAvdArtifactNode,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchAvdArtifactNodeHostvarFile,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchAvdArtifactNodeHostvarFileNode,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchName,
    GenerateAvdInputsQueryNetworkFabricEdgesNodeName,
)
from tests.unit.test_generate_avd_device_hostvar import _mlag_peer_hostvars, _underlay_hostvars

# --- Helpers to build query data ---


def _make_pod_device(
    hostname: str, device_id: str, has_hostvar: bool = False
) -> GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdges:
    """Create a pod-level device edge."""
    hostvar_file = None
    if has_hostvar:
        hostvar_file = GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNodeAvdArtifactNodeHostvarFile(
            node=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNodeAvdArtifactNodeHostvarFileNode(
                id="file-123"
            )
        )

    artifact_node = None
    if has_hostvar:
        artifact_node = (
            GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNodeAvdArtifactNode(
                hostvar_file=hostvar_file
            )
        )

    return GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdges(
        node=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNode(
            id=device_id,
            name=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNodeName(
                value=hostname
            ),
            avd_artifact=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevicesEdgesNodeAvdArtifact(
                node=artifact_node
            ),
        )
    )


def _make_rack_device(
    hostname: str, device_id: str, has_hostvar: bool = False
) -> GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdges:
    """Create a rack-level device edge."""
    hostvar_file = None
    if has_hostvar:
        hostvar_file = GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchAvdArtifactNodeHostvarFile(
            node=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchAvdArtifactNodeHostvarFileNode(
                id="file-456"
            )
        )

    artifact_node = None
    if has_hostvar:
        artifact_node = GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchAvdArtifactNode(
            hostvar_file=hostvar_file
        )

    return GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdges(
        node=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitch(
            __typename="DcimFabricSwitch",
            id=device_id,
            name=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchName(
                value=hostname
            ),
            avd_artifact=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchAvdArtifact(
                node=artifact_node
            ),
        )
    )


def _make_rack(
    devices: list,
) -> GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdges:
    """Create a rack edge with devices."""
    return GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdges(
        node=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNode(
            devices=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacksEdgesNodeDevices(
                edges=devices
            )
        )
    )


def _make_pod(
    pod_devices: list | None = None,
    racks: list | None = None,
) -> GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdges:
    """Create a pod edge with devices and racks."""
    return GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdges(
        node=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPod(
            __typename="NetworkPod",
            devices=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodDevices(
                edges=pod_devices or []
            ),
            racks=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildrenEdgesNodeNetworkPodRacks(edges=racks or []),
        )
    )


def _make_fabric_query(
    pods: list,
) -> GenerateAvdInputsQuery:
    """Build a full query response with given pods."""
    return GenerateAvdInputsQuery(
        NetworkFabric=GenerateAvdInputsQueryNetworkFabric(
            edges=[
                GenerateAvdInputsQueryNetworkFabricEdges(
                    node=GenerateAvdInputsQueryNetworkFabricEdgesNode(
                        id="fabric-1",
                        name=GenerateAvdInputsQueryNetworkFabricEdgesNodeName(value="Fabric-L3LS-MultiPod-A"),
                        children=GenerateAvdInputsQueryNetworkFabricEdgesNodeChildren(edges=pods),
                    )
                )
            ]
        )
    )


def _make_generator() -> AvdDeviceStructuredConfigGenerator:
    """Create a generator instance with a mocked client."""
    gen = AvdDeviceStructuredConfigGenerator.__new__(AvdDeviceStructuredConfigGenerator)
    gen.client = AsyncMock()
    return gen


# --- Tests for _extract_devices_from_fabric ---


class TestExtractDevicesFromFabric:
    def test_empty_fabric(self):
        gen = _make_generator()
        data = GenerateAvdInputsQuery(NetworkFabric=GenerateAvdInputsQueryNetworkFabric(edges=[]))
        result = gen._extract_devices_from_fabric(data)
        assert result == []

    def test_pod_devices_only(self):
        gen = _make_generator()
        data = _make_fabric_query(
            pods=[
                _make_pod(
                    pod_devices=[
                        _make_pod_device("spine-1", "dev-1"),
                        _make_pod_device("spine-2", "dev-2", has_hostvar=True),
                    ]
                )
            ]
        )
        result = gen._extract_devices_from_fabric(data)
        assert len(result) == 2
        hostnames = {d["hostname"] for d in result}
        assert hostnames == {"spine-1", "spine-2"}

        spine2 = next(d for d in result if d["hostname"] == "spine-2")
        assert spine2["has_hostvar"] is True
        assert spine2["id"] == "dev-2"

        spine1 = next(d for d in result if d["hostname"] == "spine-1")
        assert spine1["has_hostvar"] is False

    def test_rack_devices_only(self):
        gen = _make_generator()
        data = _make_fabric_query(
            pods=[
                _make_pod(
                    racks=[
                        _make_rack(
                            devices=[
                                _make_rack_device("leaf-1", "dev-10", has_hostvar=True),
                                _make_rack_device("leaf-2", "dev-11"),
                            ]
                        )
                    ]
                )
            ]
        )
        result = gen._extract_devices_from_fabric(data)
        assert len(result) == 2
        leaf1 = next(d for d in result if d["hostname"] == "leaf-1")
        assert leaf1["has_hostvar"] is True

    def test_mixed_pod_and_rack_devices(self):
        gen = _make_generator()
        data = _make_fabric_query(
            pods=[
                _make_pod(
                    pod_devices=[
                        _make_pod_device("spine-1", "dev-1", has_hostvar=True),
                    ],
                    racks=[
                        _make_rack(
                            devices=[
                                _make_rack_device("leaf-1", "dev-10", has_hostvar=True),
                            ]
                        )
                    ],
                )
            ]
        )
        result = gen._extract_devices_from_fabric(data)
        assert len(result) == 2
        hostnames = {d["hostname"] for d in result}
        assert hostnames == {"spine-1", "leaf-1"}

    def test_deduplication_by_hostname(self):
        """If the same hostname appears in pod and rack, it should be deduped."""
        gen = _make_generator()
        data = _make_fabric_query(
            pods=[
                _make_pod(
                    pod_devices=[
                        _make_pod_device("device-1", "dev-1"),
                    ],
                    racks=[
                        _make_rack(
                            devices=[
                                _make_rack_device("device-1", "dev-1-rack"),
                            ]
                        )
                    ],
                )
            ]
        )
        result = gen._extract_devices_from_fabric(data)
        assert len(result) == 1
        # Rack version overwrites pod version (dict key overwrite)
        assert result[0]["id"] == "dev-1-rack"

    def test_multiple_pods(self):
        gen = _make_generator()
        data = _make_fabric_query(
            pods=[
                _make_pod(
                    pod_devices=[_make_pod_device("spine-1", "dev-1")],
                ),
                _make_pod(
                    pod_devices=[_make_pod_device("spine-2", "dev-2")],
                ),
            ]
        )
        result = gen._extract_devices_from_fabric(data)
        assert len(result) == 2

    def test_devices_are_returned_in_hostname_order(self):
        gen = _make_generator()
        data = _make_fabric_query(
            pods=[
                _make_pod(
                    pod_devices=[
                        _make_pod_device("spine-2", "dev-2"),
                        _make_pod_device("spine-1", "dev-1"),
                    ],
                    racks=[
                        _make_rack(
                            devices=[
                                _make_rack_device("leaf-2", "dev-12"),
                                _make_rack_device("leaf-1", "dev-11"),
                            ]
                        )
                    ],
                )
            ]
        )

        result = gen._extract_devices_from_fabric(data)

        assert [device["hostname"] for device in result] == ["leaf-1", "leaf-2", "spine-1", "spine-2"]


# --- Tests for _fetch_hostvars_from_storage ---


class TestFetchHostvarsFromStorage:
    @pytest.mark.anyio
    async def test_skips_devices_without_hostvars(self):
        gen = _make_generator()
        devices = [
            {"hostname": "spine-1", "id": "dev-1", "has_hostvar": False},
            {"hostname": "spine-2", "id": "dev-2", "has_hostvar": False},
        ]
        result = await gen._fetch_hostvars_from_storage(devices)
        assert result == {}
        gen.client.get.assert_not_called()

    @pytest.mark.anyio
    async def test_fetches_hostvars_for_devices_with_artifacts(self):
        gen = _make_generator()
        hostvars_data = {"hostname": "spine-1", "router_bgp": {"as": "65001"}}

        mock_artifact = AsyncMock()
        mock_artifact.hostvar_file.peer.download_file = AsyncMock(return_value=json.dumps(hostvars_data))
        gen.client.get = AsyncMock(return_value=mock_artifact)

        devices = [
            {"hostname": "spine-1", "id": "dev-1", "has_hostvar": True},
        ]
        result = await gen._fetch_hostvars_from_storage(devices)
        assert "spine-1" in result
        assert result["spine-1"] == hostvars_data

    @pytest.mark.anyio
    async def test_fetches_hostvars_in_hostname_order(self):
        gen = _make_generator()
        artifacts = {
            "leaf-1": json.dumps({"hostname": "leaf-1"}),
            "spine-2": json.dumps({"hostname": "spine-2"}),
        }

        async def get_artifact(_kind: object, *, name__value: str, include: list[str]) -> AsyncMock:
            artifact = AsyncMock()
            artifact.hostvar_file.peer.download_file = AsyncMock(return_value=artifacts[name__value])
            return artifact

        gen.client.get = AsyncMock(side_effect=get_artifact)
        devices = [
            {"hostname": "spine-2", "id": "dev-2", "has_hostvar": True},
            {"hostname": "leaf-1", "id": "dev-1", "has_hostvar": True},
        ]

        result = await gen._fetch_hostvars_from_storage(devices)

        assert list(result) == ["leaf-1", "spine-2"]

    @pytest.mark.anyio
    async def test_handles_fetch_failure_gracefully(self):
        gen = _make_generator()
        gen.client.get = AsyncMock(side_effect=Exception("connection error"))

        devices = [
            {"hostname": "spine-1", "id": "dev-1", "has_hostvar": True},
        ]
        result = await gen._fetch_hostvars_from_storage(devices)
        assert result == {}


# --- Tests for pyavd validate_inputs API ---


class TestValidateInputsAPI:
    """Verify the pyavd validate_inputs API we use in the generator."""

    def test_minimal_valid_inputs_have_no_violations(self):
        """validate_inputs with minimal valid inputs should have no violations."""
        inputs = {"hostname": "test-device", "type": "l3leaf", "fabric_name": "test-fabric"}
        validated = validate_inputs(inputs)
        assert not validated.validation_result.violations

    def test_validated_data_result_has_expected_attributes(self):
        """Ensure the API shape we depend on exists."""
        validated = validate_inputs({})
        assert hasattr(validated, "validation_result")
        assert hasattr(validated, "validated_data")
        assert hasattr(validated.validation_result, "violations")

    def test_validated_data_result_has_no_failed_attribute(self):
        """Confirm the old .failed API no longer exists (regression guard)."""
        validated = validate_inputs({})
        assert not hasattr(validated, "failed")


class TestPyavdLoopbackPools:
    def test_stored_parent_prefix_pools_allow_pyavd_facts(self):
        hostvars = {
            "spine1": _underlay_hostvars(hostname="spine1", role="spine", node_id=1),
            "leaf1": _underlay_hostvars(hostname="leaf1", role="leaf", node_id=3),
        }

        avd_facts = get_avd_facts(hostvars)

        assert avd_facts["spine1"].loopback_ipv4_pool == "10.0.0.0/24"
        assert avd_facts["leaf1"].loopback_ipv4_pool == "10.0.0.0/24"
        assert avd_facts["leaf1"].vtep_loopback_ipv4_pool == "10.2.0.0/24"

    def test_stored_parent_prefix_pools_drive_underlay_prefix_lists(self):
        hostvars = {
            "spine1": _underlay_hostvars(hostname="spine1", role="spine", node_id=1),
            "leaf1": _underlay_hostvars(hostname="leaf1", role="leaf", node_id=3),
        }
        avd_facts = get_avd_facts(hostvars)

        structured_config = get_device_structured_config(
            hostname="leaf1", inputs=hostvars["leaf1"], avd_facts=avd_facts
        )
        prefix_lists = structured_config._as_dict()["prefix_lists"]
        loopbacks = next(
            prefix_list for prefix_list in prefix_lists if prefix_list["name"] == "PL-LOOPBACKS-EVPN-OVERLAY"
        )
        prefixes = [sequence["action"].removeprefix("permit ") for sequence in loopbacks["sequence_numbers"]]

        assert "10.0.0.0/24 eq 32" in prefixes
        assert "10.2.0.0/24 eq 32" in prefixes

    def test_mlag_leafs_keep_unique_router_ids_and_shared_vtep_ip(self):
        hostvars = {
            "leaf1": _mlag_peer_hostvars(hostname="leaf1", node_id=1, device_asn=65099),
            "leaf2": _mlag_peer_hostvars(hostname="leaf2", node_id=2, device_asn=65098),
        }

        avd_facts = get_avd_facts(hostvars)

        assert avd_facts["leaf1"].router_id == "10.0.0.1"
        assert avd_facts["leaf2"].router_id == "10.0.0.2"
        assert avd_facts["leaf1"].vtep_ip == avd_facts["leaf2"].vtep_ip == "10.2.0.3"

        loopback_addresses: dict[str, dict[str, str]] = {}
        for hostname, inputs in hostvars.items():
            structured_config = get_device_structured_config(hostname=hostname, inputs=inputs, avd_facts=avd_facts)
            loopback_addresses[hostname] = {
                iface["name"]: iface["ip_address"] for iface in structured_config._as_dict()["loopback_interfaces"]
            }

        assert loopback_addresses["leaf1"]["Loopback0"] == "10.0.0.1/32"
        assert loopback_addresses["leaf2"]["Loopback0"] == "10.0.0.2/32"
        assert loopback_addresses["leaf1"]["Loopback1"] == "10.2.0.3/32"
        assert loopback_addresses["leaf2"]["Loopback1"] == "10.2.0.3/32"


class TestEvpnGatewayRemotePeerPreflight:
    def test_hostname_only_remote_peer_must_have_aggregated_hostvars(self):
        hostvars = {
            "leaf1": {
                "type": "l3leaf",
                "l3leaf": {
                    "nodes": [
                        {
                            "name": "leaf1",
                            "evpn_gateway": {
                                "remote_peers": [
                                    {"hostname": "leaf2"},
                                    {"hostname": "leaf3", "ip_address": "192.0.2.3", "bgp_as": "65003"},
                                ]
                            },
                        }
                    ]
                },
            },
            "leaf3": {"type": "l3leaf", "l3leaf": {"nodes": [{"name": "leaf3"}]}},
        }

        missing = AvdDeviceStructuredConfigGenerator._missing_evpn_gateway_remote_peers(hostvars)

        assert missing == ["leaf1 -> leaf2"]

    def test_hostname_only_remote_peer_passes_when_peer_hostvars_exist(self):
        hostvars = {
            "leaf1": {
                "type": "l3leaf",
                "l3leaf": {"nodes": [{"name": "leaf1", "evpn_gateway": {"remote_peers": [{"hostname": "leaf2"}]}}]},
            },
            "leaf2": {"type": "l3leaf", "l3leaf": {"nodes": [{"name": "leaf2"}]}},
        }

        missing = AvdDeviceStructuredConfigGenerator._missing_evpn_gateway_remote_peers(hostvars)

        assert missing == []


# --- A run that writes nothing must not report success ---


class TestFailuresAreRaisedNotLogged:
    """Every abort used to `return` after a log line, so in the proposed-change
    pipeline the generator showed green while no structured config was written.
    Missing hostvars stays soft: it is the readiness state the hostvar cascade
    passes through, not a fault."""

    @staticmethod
    def _generator_with(
        monkeypatch: pytest.MonkeyPatch, hostvars: dict[str, dict]
    ) -> AvdDeviceStructuredConfigGenerator:
        import generators.generate_avd_device_structured_config as module

        gen = _make_generator()
        devices = [{"hostname": h, "id": f"id-{h}", "has_hostvar": True} for h in ("leaf-1", "spine-1")]
        monkeypatch.setattr(module, "GenerateAvdInputsQuery", lambda **_: None)
        monkeypatch.setattr(gen, "_extract_devices_from_fabric", lambda _data: devices)
        monkeypatch.setattr(gen, "_fetch_hostvars_from_storage", AsyncMock(return_value=hostvars))
        return gen

    @pytest.mark.anyio
    async def test_an_unreadable_hostvar_file_fails_the_run_instead_of_building_partial_facts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gen = self._generator_with(monkeypatch, {"leaf-1": {"hostname": "leaf-1"}})

        with pytest.raises(RuntimeError, match="spine-1"):
            await gen.generate({})

    @pytest.mark.anyio
    async def test_a_validation_failure_fails_the_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        both = {"leaf-1": {"hostname": "leaf-1"}, "spine-1": {"hostname": "spine-1"}}
        gen = self._generator_with(monkeypatch, both)
        monkeypatch.setattr(gen, "_collect_input_validation_errors", lambda _hv: ["leaf-1: bad (path: x)"])

        with pytest.raises(RuntimeError, match="pyAVD validation failed"):
            await gen.generate({})

    @pytest.mark.anyio
    async def test_missing_hostvars_is_still_a_soft_wait(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import generators.generate_avd_device_structured_config as module

        gen = _make_generator()
        monkeypatch.setattr(module, "GenerateAvdInputsQuery", lambda **_: None)
        monkeypatch.setattr(
            gen, "_extract_devices_from_fabric", lambda _data: [{"hostname": "leaf-1", "id": "x", "has_hostvar": False}]
        )

        await gen.generate({})  # no exception


class TestChangedConfigIsReRenderedOnItsBranch:
    """The proposed-change pipeline validates artifacts while this generator is
    still running, so a switch whose structured config moved kept its OLD
    rendered configuration on the branch: a grant requested through a generated
    template showed the firewall diff and no border-leaf line. The generator now
    asks for those artifacts itself, on its own branch."""

    @staticmethod
    def _generator(
        monkeypatch: pytest.MonkeyPatch, branch: str
    ) -> tuple[AvdDeviceStructuredConfigGenerator, list[tuple[str, str, str | None]]]:
        import generators.generate_avd_device_structured_config as module

        gen = _make_generator()
        gen.branch = branch
        gen._init_client = AsyncMock()
        gen._init_client.default_branch = "main"
        gen.logger = module.logging.getLogger("test")
        calls: list[tuple[str, str, str | None]] = []

        async def fake_render(
            _client: object, *, artifact_name: str, target_id: str, branch: str | None, first_render: bool = False
        ) -> bool:
            calls.append((artifact_name, target_id, branch))
            return not first_render

        monkeypatch.setattr(module, "request_artifact_render", fake_render)
        return gen, calls

    @pytest.mark.anyio
    async def test_every_changed_switch_is_rendered_on_the_branch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gen, calls = self._generator(monkeypatch, "implement_grafana-access")

        await gen._request_renders(["id-leaf"])

        assert {name for name, _, _ in calls} == {
            "AVD EOS Configuration",
            "AVD Device Documentation",
            "AVD ANTA Catalog",
        }
        assert {(target, branch) for _, target, branch in calls} == {("id-leaf", "implement_grafana-access")}

    @pytest.mark.anyio
    async def test_main_is_left_to_the_merge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gen, calls = self._generator(monkeypatch, "main")

        await gen._request_renders(["id-leaf"])

        assert calls == []

    @pytest.mark.anyio
    async def test_nothing_changed_requests_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        gen, calls = self._generator(monkeypatch, "implement_x")

        await gen._request_renders([])

        assert calls == []

    @pytest.mark.anyio
    async def test_a_failed_request_does_not_fail_the_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import generators.generate_avd_device_structured_config as module

        gen, _ = self._generator(monkeypatch, "implement_x")

        async def broken(*_args: object, **_kwargs: object) -> bool:
            msg = "500"
            raise RuntimeError(msg)

        monkeypatch.setattr(module, "request_artifact_render", broken)

        await gen._request_renders(["id-leaf"])  # no exception

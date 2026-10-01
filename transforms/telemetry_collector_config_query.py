from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class TelemetryCollectorConfigQuery(BaseModel):
    monitoring_collector: "TelemetryCollectorConfigQueryMonitoringCollector" = Field(
        alias="MonitoringCollector"
    )
    network_link: "TelemetryCollectorConfigQueryNetworkLink" = Field(
        alias="NetworkLink"
    )


class TelemetryCollectorConfigQueryMonitoringCollector(BaseModel):
    edges: list["TelemetryCollectorConfigQueryMonitoringCollectorEdges"]


class TelemetryCollectorConfigQueryMonitoringCollectorEdges(BaseModel):
    node: Optional["TelemetryCollectorConfigQueryMonitoringCollectorEdgesNode"]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNode(BaseModel):
    id: str
    name: Optional["TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeName"]
    namespace_name: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeNamespaceName"
    ]
    config_map_name: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeConfigMapName"
    ]
    monitoring_profiles: (
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfiles"
    )


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeName(BaseModel):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeNamespaceName(BaseModel):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeConfigMapName(BaseModel):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfiles(
    BaseModel
):
    edges: list[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdges"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdges(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeName"
    ]
    enabled: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeEnabled"
    ]
    interval_seconds: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeIntervalSeconds"
    ]
    device_role: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceRole"
    ]
    measurements: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeMeasurements"
    device_groups: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroups"


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeEnabled(
    BaseModel
):
    value: Optional[bool]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeIntervalSeconds(
    BaseModel
):
    value: Optional[Any]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceRole(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeMeasurements(
    BaseModel
):
    edges: list[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeMeasurementsEdges"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeMeasurementsEdges(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeMeasurementsEdgesNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeMeasurementsEdgesNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeMeasurementsEdgesNodeName"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeMeasurementsEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroups(
    BaseModel
):
    edges: list[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdges"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdges(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeName"
    ]
    members: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembers"


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembers(
    BaseModel
):
    edges: Optional[
        list[
            "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdges"
        ]
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeCoreNode",
                "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServer",
                "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDevice",
                "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitch",
                "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewall",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeCoreNode(
    BaseModel
):
    typename__: Literal[
        "AvdArtifact",
        "AvdEvpn",
        "AvdHostvarFile",
        "AvdStructuredConfigFile",
        "AvdTag",
        "BuiltinTag",
        "CloudvisionWorkspace",
        "ClusterFabricPeering",
        "ClusterKubernetes",
        "CoreAccount",
        "CoreAccountRole",
        "CoreArtifact",
        "CoreArtifactCheck",
        "CoreArtifactDefinition",
        "CoreArtifactThread",
        "CoreArtifactValidator",
        "CoreChangeComment",
        "CoreChangeThread",
        "CoreCheckDefinition",
        "CoreCustomWebhook",
        "CoreDataCheck",
        "CoreDataValidator",
        "CoreEnvKeyValue",
        "CoreFileCheck",
        "CoreFileThread",
        "CoreGeneratorAction",
        "CoreGeneratorCheck",
        "CoreGeneratorDefinition",
        "CoreGeneratorInstance",
        "CoreGeneratorValidator",
        "CoreGlobalPermission",
        "CoreGraphQLQuery",
        "CoreGroupAction",
        "CoreGroupTriggerRule",
        "CoreIPAddressPool",
        "CoreIPPrefixPool",
        "CoreMenuItem",
        "CoreNode",
        "CoreNodeTriggerAttributeMatch",
        "CoreNodeTriggerRelationshipMatch",
        "CoreNodeTriggerRule",
        "CoreNumberPool",
        "CoreObjectPermission",
        "CoreObjectThread",
        "CorePasswordCredential",
        "CoreProposedChange",
        "CoreReadOnlyRepository",
        "CoreRepository",
        "CoreRepositoryValidator",
        "CoreSchemaCheck",
        "CoreSchemaValidator",
        "CoreStandardCheck",
        "CoreStandardWebhook",
        "CoreStaticKeyValue",
        "CoreThreadComment",
        "CoreTransformJinja2",
        "CoreTransformPython",
        "CoreUserValidator",
        "DcimCircuit",
        "DcimCircuitEndpoint",
        "DcimDeviceType",
        "DcimPlatform",
        "DeploymentDiffFile",
        "DeploymentState",
        "EvpnDomain",
        "EvpnGatewayGroup",
        "EvpnL2Vlan",
        "EvpnSvi",
        "EvpnSviNode",
        "EvpnTenant",
        "InterfaceLag",
        "InterfacePhysical",
        "InterfaceVirtual",
        "InternalAccountToken",
        "InternalExternalIdentity",
        "InternalIPPrefixAvailable",
        "InternalIPRangeAvailable",
        "InternalRefreshToken",
        "IpamIPAddress",
        "IpamL2Domain",
        "IpamNamespace",
        "IpamPrefix",
        "IpamRouteTarget",
        "IpamVLAN",
        "IpamVRF",
        "LocationHall",
        "LocationRack",
        "LocationSite",
        "MlagDomain",
        "MlagInterface",
        "MonitoringCollector",
        "MonitoringMeasurement",
        "MonitoringProfile",
        "NetworkDnsServer",
        "NetworkFabric",
        "NetworkFabricDeviceDesign",
        "NetworkLink",
        "NetworkLocalUser",
        "NetworkNtpServer",
        "NetworkPod",
        "NetworkPodDeviceDesign",
        "NetworkRackDeviceDesign",
        "NetworkSpanningTreePriority",
        "OrganizationManufacturer",
        "OrganizationProvider",
        "OrganizationTenant",
        "ProfileAvdArtifact",
        "ProfileAvdEvpn",
        "ProfileAvdHostvarFile",
        "ProfileAvdStructuredConfigFile",
        "ProfileAvdTag",
        "ProfileBuiltinIPAddress",
        "ProfileBuiltinIPPrefix",
        "ProfileBuiltinTag",
        "ProfileCloudvisionWorkspace",
        "ProfileClusterFabricPeering",
        "ProfileClusterGeneric",
        "ProfileClusterGenericComputeUnitNodes",
        "ProfileClusterKubernetes",
        "ProfileComputeGenericUnit",
        "ProfileComputePhysicalServer",
        "ProfileDcimCircuit",
        "ProfileDcimCircuitEndpoint",
        "ProfileDcimConnector",
        "ProfileDcimDevice",
        "ProfileDcimDeviceType",
        "ProfileDcimEndpoint",
        "ProfileDcimFabricSwitch",
        "ProfileDcimGenericDevice",
        "ProfileDcimInterface",
        "ProfileDcimPhysicalDevice",
        "ProfileDcimPlatform",
        "ProfileEvpnDomain",
        "ProfileEvpnGatewayGroup",
        "ProfileEvpnL2Vlan",
        "ProfileEvpnSvi",
        "ProfileEvpnSviNode",
        "ProfileEvpnTenant",
        "ProfileGeneratorTarget",
        "ProfileGenericInterfaceBundle",
        "ProfileGenericMlagDomain",
        "ProfileInterfaceHasSubInterface",
        "ProfileInterfaceLag",
        "ProfileInterfaceLayer2",
        "ProfileInterfaceLayer3",
        "ProfileInterfacePhysical",
        "ProfileInterfaceVirtual",
        "ProfileIpamIPAddress",
        "ProfileIpamL2Domain",
        "ProfileIpamNamespace",
        "ProfileIpamPrefix",
        "ProfileIpamRouteTarget",
        "ProfileIpamVLAN",
        "ProfileIpamVRF",
        "ProfileLocationGeneric",
        "ProfileLocationHall",
        "ProfileLocationHosting",
        "ProfileLocationRack",
        "ProfileLocationSite",
        "ProfileMlagDomain",
        "ProfileMlagInterface",
        "ProfileMonitoringCollector",
        "ProfileMonitoringMeasurement",
        "ProfileMonitoringProfile",
        "ProfileNetworkBuildingBlock",
        "ProfileNetworkDeviceDesign",
        "ProfileNetworkDnsServer",
        "ProfileNetworkFabric",
        "ProfileNetworkFabricDeviceDesign",
        "ProfileNetworkLink",
        "ProfileNetworkLocalUser",
        "ProfileNetworkNtpServer",
        "ProfileNetworkPod",
        "ProfileNetworkPodDeviceDesign",
        "ProfileNetworkRackDeviceDesign",
        "ProfileNetworkSpanningTreePriority",
        "ProfileOrganizationGeneric",
        "ProfileOrganizationManufacturer",
        "ProfileOrganizationProvider",
        "ProfileOrganizationTenant",
        "ProfileRoutingAsn",
        "ProfileRoutingBGPNeighbor",
        "ProfileRoutingBGPPeerGroup",
        "ProfileRoutingPrefixList",
        "ProfileRoutingPrefixListEntry",
        "ProfileRoutingRouteMap",
        "ProfileRoutingRouteMapEntry",
        "ProfileRoutingStaticRoute",
        "ProfileRoutingVrfBgpPeer",
        "ProfileRoutingVrfL3Interface",
        "ProfileRoutingVrfStaticRoute",
        "ProfileSecurityAddressGroup",
        "ProfileSecurityFQDN",
        "ProfileSecurityFirewall",
        "ProfileSecurityFirewallInterface",
        "ProfileSecurityGenericAddress",
        "ProfileSecurityGenericAddressGroup",
        "ProfileSecurityGenericService",
        "ProfileSecurityGenericServiceGroup",
        "ProfileSecurityIPAMIPAddress",
        "ProfileSecurityIPAMIPPrefix",
        "ProfileSecurityIPAddress",
        "ProfileSecurityIPProtocol",
        "ProfileSecurityIPRange",
        "ProfileSecurityPolicy",
        "ProfileSecurityPolicyAssignment",
        "ProfileSecurityPolicyRule",
        "ProfileSecurityPrefix",
        "ProfileSecurityRenderedPolicyRule",
        "ProfileSecurityService",
        "ProfileSecurityServiceGroup",
        "ProfileSecurityServiceRange",
        "ProfileSecurityZone",
        "ProfileServiceAppAccess",
        "ProfileServiceFabricApp",
        "ProfileServiceFabricAppValuesFile",
        "ProfileServiceFabricPeering",
        "ProfileServiceGeneric",
        "ProfileServiceGenericDevice",
        "ProfileServiceGenericInterface",
        "ProfileServiceInternetAccess",
        "ProfileServiceL3vpn",
        "ProfileServiceNetworkSegment",
        "ProfileServiceServerPlacement",
        "ProfileServiceTenantCloud",
        "ProfileServiceTenantOnboarding",
        "ProfileVirtualizationHostVirtualMachine",
        "ProfileVirtualizationVirtualMachine",
        "ProfileWanInternetPeering",
        "ProfileWanSite",
        "RoutingAsn",
        "RoutingBGPNeighbor",
        "RoutingBGPPeerGroup",
        "RoutingPrefixList",
        "RoutingPrefixListEntry",
        "RoutingRouteMap",
        "RoutingRouteMapEntry",
        "RoutingStaticRoute",
        "RoutingVrfBgpPeer",
        "RoutingVrfL3Interface",
        "RoutingVrfStaticRoute",
        "SecurityAddressGroup",
        "SecurityFQDN",
        "SecurityFirewallInterface",
        "SecurityIPAMIPAddress",
        "SecurityIPAMIPPrefix",
        "SecurityIPAddress",
        "SecurityIPProtocol",
        "SecurityIPRange",
        "SecurityPolicy",
        "SecurityPolicyRule",
        "SecurityPrefix",
        "SecurityRenderedPolicyRule",
        "SecurityService",
        "SecurityServiceGroup",
        "SecurityServiceRange",
        "SecurityZone",
        "ServiceAppAccess",
        "ServiceFabricApp",
        "ServiceFabricAppValuesFile",
        "ServiceFabricPeering",
        "ServiceInternetAccess",
        "ServiceL3vpn",
        "ServiceNetworkSegment",
        "ServiceServerPlacement",
        "ServiceTenantCloud",
        "ServiceTenantOnboarding",
        "TemplateComputePhysicalServer",
        "TemplateDcimFabricSwitch",
        "TemplateInterfaceLag",
        "TemplateInterfacePhysical",
        "TemplateInterfaceVirtual",
        "TemplateIpamIPAddress",
        "TemplateSecurityFirewallInterface",
        "TemplateVirtualizationVirtualMachine",
        "VirtualizationVirtualMachine",
        "WanInternetPeering",
        "WanSite",
    ] = Field(alias="__typename")


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServer(
    BaseModel
):
    typename__: Literal["ComputePhysicalServer"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerName"
    ]
    role: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerRole"
    ]
    telemetry_address: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerTelemetryAddress"


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerRole(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerTelemetryAddress(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerTelemetryAddressNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerTelemetryAddressNode(
    BaseModel
):
    address: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerTelemetryAddressNodeAddress"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerTelemetryAddressNodeAddress(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDevice(
    BaseModel
):
    typename__: Literal["DcimDevice"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceName"
    ]
    role: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceRole"
    ]
    telemetry_address: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceTelemetryAddress"
    bgp_neighbors: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighbors"


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceRole(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceTelemetryAddress(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceTelemetryAddressNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceTelemetryAddressNode(
    BaseModel
):
    address: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceTelemetryAddressNodeAddress"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceTelemetryAddressNodeAddress(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighbors(
    BaseModel
):
    edges: list[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighborsEdges"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighborsEdges(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighborsEdgesNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighborsEdgesNode(
    BaseModel
):
    peer_address: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighborsEdgesNodePeerAddress"
    ]
    remote_as: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighborsEdgesNodeRemoteAs"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighborsEdgesNodePeerAddress(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighborsEdgesNodeRemoteAs(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitch(
    BaseModel
):
    typename__: Literal["DcimFabricSwitch"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchName"
    ]
    role: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchRole"
    ]
    mgmt_ip: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchMgmtIp"
    rack: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchRack"
    pod: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchPod"
    avd_artifact: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchAvdArtifact"


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchRole(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchMgmtIp(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchMgmtIpNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchMgmtIpNode(
    BaseModel
):
    address: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchMgmtIpNodeAddress"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchMgmtIpNodeAddress(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchRack(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchRackNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchRackNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchRackNodeName"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchRackNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchPod(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchPodNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchPodNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchPodNodeName"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchPodNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchAvdArtifact(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchAvdArtifactNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchAvdArtifactNode(
    BaseModel
):
    structured_config_file: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchAvdArtifactNodeStructuredConfigFile"


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchAvdArtifactNodeStructuredConfigFile(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchAvdArtifactNodeStructuredConfigFileNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchAvdArtifactNodeStructuredConfigFileNode(
    BaseModel
):
    id: str


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewall(
    BaseModel
):
    typename__: Literal["SecurityFirewall"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallName"
    ]
    role: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallRole"
    ]
    telemetry_address: "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallTelemetryAddress"
    snmp_community: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallSnmpCommunity"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallRole(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallTelemetryAddress(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallTelemetryAddressNode"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallTelemetryAddressNode(
    BaseModel
):
    address: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallTelemetryAddressNodeAddress"
    ]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallTelemetryAddressNodeAddress(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallSnmpCommunity(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryNetworkLink(BaseModel):
    edges: list["TelemetryCollectorConfigQueryNetworkLinkEdges"]


class TelemetryCollectorConfigQueryNetworkLinkEdges(BaseModel):
    node: Optional["TelemetryCollectorConfigQueryNetworkLinkEdgesNode"]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNode(BaseModel):
    connected_endpoints: (
        "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpoints"
    )


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpoints(BaseModel):
    edges: Optional[
        list["TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdges"]
    ]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeDcimEndpoint",
                "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysical",
                "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterface",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeDcimEndpoint(
    BaseModel
):
    typename__: Literal["DcimCircuitEndpoint", "DcimEndpoint"] = Field(
        alias="__typename"
    )


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalName"
    ]
    status: Optional[
        "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalStatus"
    ]
    device: "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice"


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalStatus(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNode"
    ]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNode(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer",
        "DcimDevice",
        "DcimFabricSwitch",
        "DcimGenericDevice",
        "SecurityFirewall",
    ] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeName"
    ]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterface(
    BaseModel
):
    typename__: Literal["SecurityFirewallInterface"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceName"
    ]
    status: Optional[
        "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceStatus"
    ]
    device: "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceDevice"


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceStatus(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceDevice(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceDeviceNode"
    ]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceDeviceNode(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer",
        "DcimDevice",
        "DcimFabricSwitch",
        "DcimGenericDevice",
        "SecurityFirewall",
    ] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceDeviceNodeName"
    ]


class TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceDeviceNodeName(
    BaseModel
):
    value: Optional[str]


TelemetryCollectorConfigQuery.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollector.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdges.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfiles.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdges.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeMeasurements.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeMeasurementsEdges.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeMeasurementsEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroups.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdges.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembers.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdges.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServer.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerTelemetryAddress.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeComputePhysicalServerTelemetryAddressNode.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDevice.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceTelemetryAddress.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceTelemetryAddressNode.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighbors.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighborsEdges.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimDeviceBgpNeighborsEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitch.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchMgmtIp.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchMgmtIpNode.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchRack.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchRackNode.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchPod.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchPodNode.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchAvdArtifact.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchAvdArtifactNode.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeDcimFabricSwitchAvdArtifactNodeStructuredConfigFile.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewall.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallTelemetryAddress.model_rebuild()
TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeDeviceGroupsEdgesNodeMembersEdgesNodeSecurityFirewallTelemetryAddressNode.model_rebuild()
TelemetryCollectorConfigQueryNetworkLink.model_rebuild()
TelemetryCollectorConfigQueryNetworkLinkEdges.model_rebuild()
TelemetryCollectorConfigQueryNetworkLinkEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpoints.model_rebuild()
TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdges.model_rebuild()
TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysical.model_rebuild()
TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice.model_rebuild()
TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNode.model_rebuild()
TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterface.model_rebuild()
TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceDevice.model_rebuild()
TelemetryCollectorConfigQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeSecurityFirewallInterfaceDeviceNode.model_rebuild()

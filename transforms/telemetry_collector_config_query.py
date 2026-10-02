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
    service_generic: "TelemetryCollectorConfigQueryServiceGeneric" = Field(
        alias="ServiceGeneric"
    )
    wan_site: "TelemetryCollectorConfigQueryWanSite" = Field(alias="WanSite")


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
    service_kind: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeServiceKind"
    ]
    timeout_seconds: Optional[
        "TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeTimeoutSeconds"
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


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeServiceKind(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryMonitoringCollectorEdgesNodeMonitoringProfilesEdgesNodeTimeoutSeconds(
    BaseModel
):
    value: Optional[Any]


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


class TelemetryCollectorConfigQueryServiceGeneric(BaseModel):
    edges: list["TelemetryCollectorConfigQueryServiceGenericEdges"]


class TelemetryCollectorConfigQueryServiceGenericEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGeneric",
                "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccess",
                "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricApp",
                "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeering",
                "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpn",
                "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegment",
                "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacement",
                "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloud",
                "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboarding",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGeneric(BaseModel):
    typename__: Literal["ServiceGeneric", "ServiceInternetAccess"] = Field(
        alias="__typename"
    )
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGenericName"
    ]
    status: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGenericStatus"
    ]
    owner: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGenericOwner"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGenericName(BaseModel):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGenericStatus(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGenericOwner(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGenericOwnerNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGenericOwnerNode(
    BaseModel
):
    typename__: Literal[
        "OrganizationGeneric",
        "OrganizationManufacturer",
        "OrganizationProvider",
        "OrganizationTenant",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccess(BaseModel):
    typename__: Literal["ServiceAppAccess"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessName"
    ]
    status: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessStatus"
    ]
    owner: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessOwner"
    requester: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessRequester"
    ]
    application: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessApplication"
    source_zone: (
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceZone"
    )
    source_site: (
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceSite"
    )
    granted_rules: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRules"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessStatus(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessOwner(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessOwnerNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessOwnerNode(
    BaseModel
):
    typename__: Literal[
        "OrganizationGeneric",
        "OrganizationManufacturer",
        "OrganizationProvider",
        "OrganizationTenant",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessRequester(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessApplication(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessApplicationNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessApplicationNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessApplicationNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessApplicationNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceZone(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceZoneNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceZoneNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceZoneNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceZoneNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceSite(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceSiteNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceSiteNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceSiteNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceSiteNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRules(
    BaseModel
):
    edges: list[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdges"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdges(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodeName"
    ]
    destination_zone: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodeDestinationZone"
    policy: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicy"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodeDestinationZone(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodeDestinationZoneNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodeDestinationZoneNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodeDestinationZoneNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodeDestinationZoneNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicy(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicyNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicyNode(
    BaseModel
):
    device_target: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicyNodeDeviceTarget"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicyNodeDeviceTarget(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicyNodeDeviceTargetNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicyNodeDeviceTargetNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicyNodeDeviceTargetNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicyNodeDeviceTargetNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricApp(BaseModel):
    typename__: Literal["ServiceFabricApp"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppName"
    ]
    status: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppStatus"
    ]
    owner: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppOwner"
    namespace_name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppNamespaceName"
    ]
    exposed: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppExposed"
    ]
    policy_default_deny: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppPolicyDefaultDeny"
    ]
    policy_allow_ports: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppPolicyAllowPorts"
    ]
    allowed_source_prefixes: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAllowedSourcePrefixes"
    vip_block: (
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppVipBlock"
    )
    values_file: (
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppValuesFile"
    )
    advertised_services: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServices"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppStatus(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppOwner(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppOwnerNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppOwnerNode(
    BaseModel
):
    typename__: Literal[
        "OrganizationGeneric",
        "OrganizationManufacturer",
        "OrganizationProvider",
        "OrganizationTenant",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppNamespaceName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppExposed(
    BaseModel
):
    value: Optional[bool]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppPolicyDefaultDeny(
    BaseModel
):
    value: Optional[bool]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppPolicyAllowPorts(
    BaseModel
):
    value: Optional[Any]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAllowedSourcePrefixes(
    BaseModel
):
    count: int


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppVipBlock(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppVipBlockNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppVipBlockNode(
    BaseModel
):
    prefix: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppVipBlockNodePrefix"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppVipBlockNodePrefix(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppValuesFile(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppValuesFileNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppValuesFileNode(
    BaseModel
):
    id: str


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServices(
    BaseModel
):
    edges: list[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdges"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdges(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodeName"
    ]
    port: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodePort"
    ]
    ip_protocol: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodeIpProtocol"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodePort(
    BaseModel
):
    value: Optional[Any]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodeIpProtocol(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodeIpProtocolNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodeIpProtocolNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodeIpProtocolNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodeIpProtocolNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeering(
    BaseModel
):
    typename__: Literal["ServiceFabricPeering"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringName"
    ]
    status: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringStatus"
    ]
    owner: (
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringOwner"
    )
    peerings: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeerings"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringStatus(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringOwner(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringOwnerNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringOwnerNode(
    BaseModel
):
    typename__: Literal[
        "OrganizationGeneric",
        "OrganizationManufacturer",
        "OrganizationProvider",
        "OrganizationTenant",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeerings(
    BaseModel
):
    edges: list[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdges"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdges(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNode(
    BaseModel
):
    peer_device: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodePeerDevice"
    svi: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSvi"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodePeerDevice(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodePeerDeviceNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodePeerDeviceNode(
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
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodePeerDeviceNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodePeerDeviceNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSvi(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSviNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSviNode(
    BaseModel
):
    vrf: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSviNodeVrf"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSviNodeVrf(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSviNodeVrfNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSviNodeVrfNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSviNodeVrfNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSviNodeVrfNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpn(BaseModel):
    typename__: Literal["ServiceL3vpn"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnName"
    ]
    status: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnStatus"
    ]
    owner: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnOwner"
    circuits: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnCircuits"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnName(BaseModel):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnStatus(BaseModel):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnOwner(BaseModel):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnOwnerNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnOwnerNode(
    BaseModel
):
    typename__: Literal[
        "OrganizationGeneric",
        "OrganizationManufacturer",
        "OrganizationProvider",
        "OrganizationTenant",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnCircuits(
    BaseModel
):
    edges: list[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnCircuitsEdges"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnCircuitsEdges(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnCircuitsEdgesNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnCircuitsEdgesNode(
    BaseModel
):
    id: str


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegment(
    BaseModel
):
    typename__: Literal["ServiceNetworkSegment"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentName"
    ]
    status: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentStatus"
    ]
    owner: (
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentOwner"
    )
    svi: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSvi"
    avd_tags: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTags"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentStatus(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentOwner(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentOwnerNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentOwnerNode(
    BaseModel
):
    typename__: Literal[
        "OrganizationGeneric",
        "OrganizationManufacturer",
        "OrganizationProvider",
        "OrganizationTenant",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSvi(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNode(
    BaseModel
):
    svi_id: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNodeSviId"
    ]
    vrf: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNodeVrf"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNodeSviId(
    BaseModel
):
    value: Optional[Any]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNodeVrf(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNodeVrfNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNodeVrfNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNodeVrfNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNodeVrfNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTags(
    BaseModel
):
    edges: list[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdges"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdges(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNode(
    BaseModel
):
    racks: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacks"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacks(
    BaseModel
):
    edges: list[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdges"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdges(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNode(
    BaseModel
):
    devices: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevices"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevices(
    BaseModel
):
    edges: Optional[
        list[
            "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevicesEdges"
        ]
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevicesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevicesEdgesNodeDcimPhysicalDevice",
                "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitch",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevicesEdgesNodeDcimPhysicalDevice(
    BaseModel
):
    typename__: Literal["DcimDevice", "DcimPhysicalDevice", "SecurityFirewall"] = Field(
        alias="__typename"
    )


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitch(
    BaseModel
):
    typename__: Literal["DcimFabricSwitch"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitchName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacement(
    BaseModel
):
    typename__: Literal["ServiceServerPlacement"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementName"
    ]
    status: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementStatus"
    ]
    owner: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementOwner"
    server: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementServer"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementStatus(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementOwner(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementOwnerNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementOwnerNode(
    BaseModel
):
    typename__: Literal[
        "OrganizationGeneric",
        "OrganizationManufacturer",
        "OrganizationProvider",
        "OrganizationTenant",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementServer(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementServerNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementServerNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementServerNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementServerNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloud(BaseModel):
    typename__: Literal["ServiceTenantCloud"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudName"
    ]
    status: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudStatus"
    ]
    owner: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudOwner"
    vrf: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudVrf"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudStatus(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudOwner(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudOwnerNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudOwnerNode(
    BaseModel
):
    typename__: Literal[
        "OrganizationGeneric",
        "OrganizationManufacturer",
        "OrganizationProvider",
        "OrganizationTenant",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudVrf(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudVrfNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudVrfNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudVrfNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudVrfNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboarding(
    BaseModel
):
    typename__: Literal["ServiceTenantOnboarding"] = Field(alias="__typename")
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingName"
    ]
    status: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingStatus"
    ]
    owner: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingOwner"
    evpn_tenant: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenant"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingStatus(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingOwner(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingOwnerNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingOwnerNode(
    BaseModel
):
    typename__: Literal[
        "OrganizationGeneric",
        "OrganizationManufacturer",
        "OrganizationProvider",
        "OrganizationTenant",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenant(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNode(
    BaseModel
):
    vrfs: "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNodeVrfs"


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNodeVrfs(
    BaseModel
):
    edges: list[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNodeVrfsEdges"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNodeVrfsEdges(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNodeVrfsEdgesNode"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNodeVrfsEdgesNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNodeVrfsEdgesNodeName"
    ]


class TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNodeVrfsEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryWanSite(BaseModel):
    edges: list["TelemetryCollectorConfigQueryWanSiteEdges"]


class TelemetryCollectorConfigQueryWanSiteEdges(BaseModel):
    node: Optional["TelemetryCollectorConfigQueryWanSiteEdgesNode"]


class TelemetryCollectorConfigQueryWanSiteEdgesNode(BaseModel):
    circuit: "TelemetryCollectorConfigQueryWanSiteEdgesNodeCircuit"
    bgp_sessions: "TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessions"


class TelemetryCollectorConfigQueryWanSiteEdgesNodeCircuit(BaseModel):
    node: Optional["TelemetryCollectorConfigQueryWanSiteEdgesNodeCircuitNode"]


class TelemetryCollectorConfigQueryWanSiteEdgesNodeCircuitNode(BaseModel):
    id: str


class TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessions(BaseModel):
    edges: list["TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdges"]


class TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdges(BaseModel):
    node: Optional["TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNode"]


class TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNode(BaseModel):
    peer_address: Optional[
        "TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodePeerAddress"
    ]
    device: "TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice"


class TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodePeerAddress(
    BaseModel
):
    value: Optional[str]


class TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice(
    BaseModel
):
    node: Optional[
        "TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode"
    ]


class TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode(
    BaseModel
):
    name: Optional[
        "TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeName"
    ]


class TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeName(
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
TelemetryCollectorConfigQueryServiceGeneric.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdges.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGeneric.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceGenericOwner.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccess.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessOwner.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessApplication.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessApplicationNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceZone.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceZoneNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceSite.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessSourceSiteNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRules.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdges.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodeDestinationZone.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodeDestinationZoneNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicy.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicyNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicyNodeDeviceTarget.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceAppAccessGrantedRulesEdgesNodePolicyNodeDeviceTargetNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricApp.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppOwner.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppVipBlock.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppVipBlockNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppValuesFile.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServices.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdges.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodeIpProtocol.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricAppAdvertisedServicesEdgesNodeIpProtocolNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeering.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringOwner.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeerings.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdges.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodePeerDevice.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodePeerDeviceNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSvi.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSviNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSviNodeVrf.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceFabricPeeringPeeringsEdgesNodeSviNodeVrfNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpn.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnOwner.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnCircuits.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceL3vpnCircuitsEdges.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegment.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentOwner.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSvi.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNodeVrf.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentSviNodeVrfNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTags.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdges.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacks.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdges.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevices.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevicesEdges.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceNetworkSegmentAvdTagsEdgesNodeRacksEdgesNodeDevicesEdgesNodeDcimFabricSwitch.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacement.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementOwner.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementServer.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceServerPlacementServerNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloud.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudOwner.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudVrf.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantCloudVrfNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboarding.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingOwner.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenant.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNode.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNodeVrfs.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNodeVrfsEdges.model_rebuild()
TelemetryCollectorConfigQueryServiceGenericEdgesNodeServiceTenantOnboardingEvpnTenantNodeVrfsEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryWanSite.model_rebuild()
TelemetryCollectorConfigQueryWanSiteEdges.model_rebuild()
TelemetryCollectorConfigQueryWanSiteEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryWanSiteEdgesNodeCircuit.model_rebuild()
TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessions.model_rebuild()
TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdges.model_rebuild()
TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNode.model_rebuild()
TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice.model_rebuild()
TelemetryCollectorConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode.model_rebuild()

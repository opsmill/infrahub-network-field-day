from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class GenerateAvdDeviceInputsQuery(BaseModel):
    dcim_fabric_switch: "GenerateAvdDeviceInputsQueryDcimFabricSwitch" = Field(
        alias="DcimFabricSwitch"
    )
    network_link: "GenerateAvdDeviceInputsQueryNetworkLink" = Field(alias="NetworkLink")


class GenerateAvdDeviceInputsQueryDcimFabricSwitch(BaseModel):
    edges: list["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdges"]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdges(BaseModel):
    node: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNode"]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeName"]
    role: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRole"]
    evpn_gateway_group: (
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroup"
    )
    asn: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeAsn"
    node_id: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeNodeId"]
    avd_custom_hostvars: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeAvdCustomHostvars"
    ]
    loopback_ip: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIp"
    vtep_loopback_ip: (
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIp"
    )
    mgmt_ip: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMgmtIp"
    mlag_domain: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomain"
    rack: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRack"
    pod: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePod"
    interfaces: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfaces"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRole(BaseModel):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroup(BaseModel):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNode(
    BaseModel
):
    id: str
    display_label: Optional[str]
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeName"
    ]
    resiliency_model: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeResiliencyModel"
    ]
    evpn_l_2_enabled: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeEvpnL2Enabled"
    ] = Field(alias="evpn_l2_enabled")
    evpn_l_3_enabled: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeEvpnL3Enabled"
    ] = Field(alias="evpn_l3_enabled")
    evpn_l_3_inter_domain: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeEvpnL3InterDomain"
    ] = Field(alias="evpn_l3_inter_domain")
    d_path_enabled: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeDPathEnabled"
    ]
    all_active_multihoming_enabled: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeAllActiveMultihomingEnabled"
    ]
    ethernet_segment_identifier: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeEthernetSegmentIdentifier"
    ]
    ethernet_segment_rt_import: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeEthernetSegmentRtImport"
    ]
    local_domain: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomain"
    pod: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePod"
    members: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembers"
    remote_domain: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomain"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeResiliencyModel(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeEvpnL2Enabled(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeEvpnL3Enabled(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeEvpnL3InterDomain(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeDPathEnabled(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeAllActiveMultihomingEnabled(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeEthernetSegmentIdentifier(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeEthernetSegmentRtImport(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomain(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNode(
    BaseModel
):
    id: str
    display_label: Optional[str]
    domain_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNodeDomainId"
    ]
    fabric: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNodeFabric"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNodeDomainId(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNodeFabric(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNodeFabricNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNodeFabricNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNodeFabricNodeName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNodeFabricNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePod(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeName"
    ]
    evpn_domain: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomain"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomain(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNode(
    BaseModel
):
    id: str
    display_label: Optional[str]
    domain_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNodeDomainId"
    ]
    fabric: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNodeFabric"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNodeDomainId(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNodeFabric(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNodeFabricNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNodeFabricNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNodeFabricNodeName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNodeFabricNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembers(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodeName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodeRole"
    ]
    pod: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodePod"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodeRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodePod(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodePodNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodePodNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodePodNodeName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodePodNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomain(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNode(
    BaseModel
):
    id: str
    display_label: Optional[str]
    domain_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeDomainId"
    ]
    fabric: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeFabric"
    remote_gateway_groups: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroups"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeDomainId(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeFabric(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeFabricNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeFabricNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeFabricNodeName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeFabricNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroups(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNode(
    BaseModel
):
    id: str
    display_label: Optional[str]
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeName"
    ]
    local_domain: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomain"
    pod: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePod"
    members: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembers"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomain(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNode(
    BaseModel
):
    id: str
    display_label: Optional[str]
    domain_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNodeDomainId"
    ]
    fabric: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNodeFabric"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNodeDomainId(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNodeFabric(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNodeFabricNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNodeFabricNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNodeFabricNodeName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNodeFabricNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePod(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeName"
    ]
    evpn_domain: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomain"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomain(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNode(
    BaseModel
):
    id: str
    display_label: Optional[str]
    domain_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNodeDomainId"
    ]
    fabric: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNodeFabric"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNodeDomainId(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNodeFabric(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNodeFabricNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNodeFabricNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNodeFabricNodeName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNodeFabricNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembers(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodeName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodeRole"
    ]
    pod: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodePod"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodeRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodePod(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodePodNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodePodNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodePodNodeName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodePodNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeAsn(BaseModel):
    node: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeAsnNode"]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeAsnNode(BaseModel):
    asn: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeAsnNodeAsn"]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeAsnNodeAsn(BaseModel):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeNodeId(BaseModel):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeAvdCustomHostvars(BaseModel):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIp(BaseModel):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNode(BaseModel):
    id: str
    address: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNodeAddress"
    ]
    ip_prefix: (
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNodeIpPrefix"
    )


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNodeAddress(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNodeIpPrefix(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNodeIpPrefixNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNodeIpPrefixNode(
    BaseModel
):
    typename__: Literal[
        "BuiltinIPPrefix", "InternalIPPrefixAvailable", "IpamPrefix"
    ] = Field(alias="__typename")
    prefix: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNodeIpPrefixNodePrefix"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNodeIpPrefixNodePrefix(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIp(BaseModel):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNode(
    BaseModel
):
    id: str
    address: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNodeAddress"
    ]
    ip_prefix: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNodeIpPrefix"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNodeAddress(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNodeIpPrefix(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNodeIpPrefixNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNodeIpPrefixNode(
    BaseModel
):
    typename__: Literal[
        "BuiltinIPPrefix", "InternalIPPrefixAvailable", "IpamPrefix"
    ] = Field(alias="__typename")
    prefix: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNodeIpPrefixNodePrefix"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNodeIpPrefixNodePrefix(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMgmtIp(BaseModel):
    node: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMgmtIpNode"]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMgmtIpNode(BaseModel):
    id: str
    address: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMgmtIpNodeAddress"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMgmtIpNodeAddress(BaseModel):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomain(BaseModel):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNode(BaseModel):
    id: str
    domain_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeDomainId"
    ]
    asn: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeAsn"
    virtual_router_mac: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeVirtualRouterMac"
    ]
    peers: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodePeers"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeDomainId(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeAsn(BaseModel):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeAsnNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeAsnNode(
    BaseModel
):
    asn: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeAsnNodeAsn"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeAsnNodeAsn(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeVirtualRouterMac(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodePeers(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodePeersEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodePeersEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodePeersEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodePeersEdgesNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodePeersEdgesNodeName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodePeersEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRack(BaseModel):
    node: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNode"]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNode(BaseModel):
    id: str
    name: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeName"]
    mlag: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeMlag"]
    devices: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevices"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeName(BaseModel):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeMlag(BaseModel):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevices(BaseModel):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdgesNodeDcimPhysicalDevice",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdgesNodeDcimFabricSwitch",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdgesNodeDcimPhysicalDevice(
    BaseModel
):
    typename__: Literal["DcimDevice", "DcimPhysicalDevice", "SecurityFirewall"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdgesNodeDcimFabricSwitch(
    BaseModel
):
    typename__: Literal["DcimFabricSwitch"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdgesNodeDcimFabricSwitchName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdgesNodeDcimFabricSwitchRole"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdgesNodeDcimFabricSwitchName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdgesNodeDcimFabricSwitchRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePod(BaseModel):
    node: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNode"]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNode(BaseModel):
    id: str
    name: Optional["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeName"]
    pod_ip_pools: (
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPools"
    )
    mlag_peer_pool: (
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagPeerPool"
    )
    mlag_l_3_pool: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagL3Pool" = Field(
        alias="mlag_l3_pool"
    )
    racks: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeRacks"
    avd_custom_hostvars: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeAvdCustomHostvars"
    ]
    parent: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParent"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeName(BaseModel):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPools(BaseModel):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreResourcePool",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPool",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPool",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreResourcePool(
    BaseModel
):
    typename__: Literal["CoreNumberPool", "CoreResourcePool"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPool(
    BaseModel
):
    typename__: Literal["CoreIPAddressPool"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolName"
    ]
    resources: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResources"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPool(
    BaseModel
):
    typename__: Literal["CoreIPPrefixPool"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolName"
    ]
    resources: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResources"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagPeerPool(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagPeerPoolNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagPeerPoolNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagPeerPoolNodeName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagPeerPoolNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagL3Pool(BaseModel):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagL3PoolNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagL3PoolNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagL3PoolNodeName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagL3PoolNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeRacks(BaseModel):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeRacksEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeRacksEdges(BaseModel):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeRacksEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeRacksEdgesNode(
    BaseModel
):
    id: str
    mlag: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeRacksEdgesNodeMlag"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeRacksEdgesNodeMlag(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeAvdCustomHostvars(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParent(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkBuildingBlock",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabric",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkBuildingBlock(
    BaseModel
):
    typename__: Literal["NetworkBuildingBlock", "NetworkPod"] = Field(
        alias="__typename"
    )
    id: Optional[str]
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkBuildingBlockName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkBuildingBlockName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabric(
    BaseModel
):
    typename__: Literal["NetworkFabric"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricName"
    ]
    children: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildren"
    mgmt_gateway: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricMgmtGateway"
    ]
    mgmt_routes: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricMgmtRoutes"
    ]
    virtual_router_mac: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVirtualRouterMac"
    ]
    underlay_routing_protocol: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUnderlayRoutingProtocol"
    ]
    overlay_routing_protocol: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricOverlayRoutingProtocol"
    ]
    evpn_vlan_aware_bundles: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricEvpnVlanAwareBundles"
    ]
    p_2_p_uplinks_mtu: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricP2PUplinksMtu"
    ] = Field(alias="p2p_uplinks_mtu")
    uplink_pool: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUplinkPool"
    fabric_ip_pools: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPools"
    vtep_pool: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVtepPool"
    loopback_pool: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLoopbackPool"
    spanning_tree_mode: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreeMode"
    ]
    spanning_tree_priorities: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePriorities"
    bgp_evpn_overlay_password: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricBgpEvpnOverlayPassword"
    ]
    bgp_underlay_password: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricBgpUnderlayPassword"
    ]
    bgp_mlag_password: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricBgpMlagPassword"
    ]
    avd_custom_hostvars: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdCustomHostvars"
    ]
    dns_servers: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServers"
    ntp_servers: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServers"
    local_users: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsers"
    avd_evpn: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdEvpn"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildren(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkBuildingBlock",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPod",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkBuildingBlock(
    BaseModel
):
    typename__: Literal["NetworkBuildingBlock", "NetworkFabric"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPod(
    BaseModel
):
    typename__: Literal["NetworkPod"] = Field(alias="__typename")
    id: str
    devices: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevices"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevices(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeRole"
    ]
    node_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeNodeId"
    ]
    interfaces: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfaces"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeNodeId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfaces(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeDcimInterface",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysical",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeDcimInterface(
    BaseModel
):
    typename__: Literal[
        "DcimInterface", "InterfaceLag", "InterfaceVirtual", "SecurityFirewallInterface"
    ] = Field(alias="__typename")
    id: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalRole"
    ]
    connector: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnector"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnector(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNode(
    BaseModel
):
    typename__: Literal["DcimConnector", "NetworkLink"] = Field(alias="__typename")
    id: Optional[str]
    connected_endpoints: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpoints"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpoints(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimEndpoint",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterface",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimEndpoint(
    BaseModel
):
    typename__: Literal[
        "DcimCircuitEndpoint",
        "DcimEndpoint",
        "InterfacePhysical",
        "SecurityFirewallInterface",
    ] = Field(alias="__typename")
    id: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterface(
    BaseModel
):
    typename__: Literal["DcimInterface"] = Field(alias="__typename")
    id: Optional[str]
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceName"
    ]
    device: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDevice"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDevice(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNode(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer",
        "DcimDevice",
        "DcimFabricSwitch",
        "DcimGenericDevice",
        "SecurityFirewall",
    ] = Field(alias="__typename")
    id: Optional[str]
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricMgmtGateway(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricMgmtRoutes(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVirtualRouterMac(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUnderlayRoutingProtocol(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricOverlayRoutingProtocol(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricEvpnVlanAwareBundles(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricP2PUplinksMtu(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUplinkPool(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUplinkPoolNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUplinkPoolNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUplinkPoolNodeName"
    ]
    default_prefix_length: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUplinkPoolNodeDefaultPrefixLength"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUplinkPoolNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUplinkPoolNodeDefaultPrefixLength(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPools(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreResourcePool",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPool",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreResourcePool(
    BaseModel
):
    typename__: Literal["CoreNumberPool", "CoreResourcePool"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPool(
    BaseModel
):
    typename__: Literal["CoreIPAddressPool"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolName"
    ]
    resources: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResources"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool(
    BaseModel
):
    typename__: Literal["CoreIPPrefixPool"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolName"
    ]
    resources: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVtepPool(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVtepPoolNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVtepPoolNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVtepPoolNodeName"
    ]
    default_prefix_length: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVtepPoolNodeDefaultPrefixLength"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVtepPoolNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVtepPoolNodeDefaultPrefixLength(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLoopbackPool(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLoopbackPoolNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLoopbackPoolNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLoopbackPoolNodeName"
    ]
    default_prefix_length: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLoopbackPoolNodeDefaultPrefixLength"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLoopbackPoolNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLoopbackPoolNodeDefaultPrefixLength(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreeMode(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePriorities(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePrioritiesEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePrioritiesEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePrioritiesEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePrioritiesEdgesNode(
    BaseModel
):
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePrioritiesEdgesNodeRole"
    ]
    priority: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePrioritiesEdgesNodePriority"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePrioritiesEdgesNodeRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePrioritiesEdgesNodePriority(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricBgpEvpnOverlayPassword(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricBgpUnderlayPassword(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricBgpMlagPassword(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdCustomHostvars(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServers(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdgesNode(
    BaseModel
):
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdgesNodeName"
    ]
    ip_address: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdgesNodeIpAddress"
    ]
    vrf: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdgesNodeVrf"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdgesNodeIpAddress(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdgesNodeVrf(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServers(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdgesNode(
    BaseModel
):
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdgesNodeName"
    ]
    server_vrf: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdgesNodeServerVrf"
    ]
    iburst: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdgesNodeIburst"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdgesNodeServerVrf(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdgesNodeIburst(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsers(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNode(
    BaseModel
):
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNodeName"
    ]
    privilege: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNodePrivilege"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNodeRole"
    ]
    password_type: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNodePasswordType"
    ]
    password: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNodePassword"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNodePrivilege(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNodeRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNodePasswordType(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNodePassword(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdEvpn(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdEvpnNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdEvpnNode(
    BaseModel
):
    ebgp_multihop: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdEvpnNodeEbgpMultihop"
    ]
    overlay_bgp_rtc: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdEvpnNodeOverlayBgpRtc"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdEvpnNodeEbgpMultihop(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdEvpnNodeOverlayBgpRtc(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfaces(BaseModel):
    edges: Optional[
        list["GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdges"]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeDcimInterface",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysical",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeDcimInterface(
    BaseModel
):
    typename__: Literal[
        "DcimInterface", "InterfaceLag", "InterfaceVirtual", "SecurityFirewallInterface"
    ] = Field(alias="__typename")
    id: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalRole"
    ]
    spanning_tree_portfast: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalSpanningTreePortfast"
    ]
    spanning_tree_bpduguard: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalSpanningTreeBpduguard"
    ]
    description: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalDescription"
    ]
    tagged_vlan: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlan"
    untagged_vlan: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalUntaggedVlan"
    lag: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLag"
    connector: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnector"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalSpanningTreePortfast(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalSpanningTreeBpduguard(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalDescription(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlan(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlanEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlanEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlanEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlanEdgesNode(
    BaseModel
):
    vlan_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlanEdgesNodeVlanId"
    ]
    status: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlanEdgesNodeStatus"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlanEdgesNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlanEdgesNodeStatus(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalUntaggedVlan(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalUntaggedVlanNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalUntaggedVlanNode(
    BaseModel
):
    vlan_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalUntaggedVlanNodeVlanId"
    ]
    status: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalUntaggedVlanNodeStatus"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalUntaggedVlanNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalUntaggedVlanNodeStatus(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLag(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeName"
    ]
    channel_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeChannelId"
    ]
    lacp_mode: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeLacpMode"
    ]
    evpn_ethernet_segment: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeEvpnEthernetSegment"
    ]
    tagged_vlan: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlan"
    untagged_vlan: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeUntaggedVlan"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeChannelId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeLacpMode(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeEvpnEthernetSegment(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlan(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNode(
    BaseModel
):
    vlan_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeVlanId"
    ]
    status: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeStatus"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeStatus(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeUntaggedVlan(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNode(
    BaseModel
):
    vlan_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeVlanId"
    ]
    status: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeStatus"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeStatus(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnector(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNode(
    BaseModel
):
    typename__: Literal["DcimConnector", "NetworkLink"] = Field(alias="__typename")
    id: Optional[str]
    connected_endpoints: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpoints"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpoints(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimEndpoint",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterface",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysical",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimEndpoint(
    BaseModel
):
    typename__: Literal[
        "DcimCircuitEndpoint", "DcimEndpoint", "SecurityFirewallInterface"
    ] = Field(alias="__typename")
    id: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterface(
    BaseModel
):
    typename__: Literal["DcimInterface"] = Field(alias="__typename")
    id: Optional[str]
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceName"
    ]
    device: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDevice"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDevice(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimGenericDevice",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimFabricSwitch",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimGenericDevice(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer", "DcimDevice", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    id: Optional[str]
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimGenericDeviceName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimGenericDeviceName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimFabricSwitch(
    BaseModel
):
    typename__: Literal["DcimFabricSwitch"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimFabricSwitchName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimFabricSwitchRole"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimFabricSwitchName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimFabricSwitchRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalName"
    ]
    device: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice"
    lag: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLag"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer", "DcimDevice", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    id: Optional[str]
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDeviceName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDeviceName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch(
    BaseModel
):
    typename__: Literal["DcimFabricSwitch"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchRole"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLag(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeName"
    ]
    channel_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeChannelId"
    ]
    lacp_mode: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLacpMode"
    ]
    evpn_ethernet_segment: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeEvpnEthernetSegment"
    ]
    tagged_vlan: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlan"
    untagged_vlan: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlan"
    lag_members: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembers"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeChannelId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLacpMode(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeEvpnEthernetSegment(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlan(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNode(
    BaseModel
):
    vlan_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeVlanId"
    ]
    status: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeStatus"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeStatus(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlan(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNode(
    BaseModel
):
    vlan_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeVlanId"
    ]
    status: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeStatus"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeStatus(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembers(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeName"
    ]
    connector: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnector"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnector(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNode(
    BaseModel
):
    typename__: Literal["DcimConnector", "NetworkLink"] = Field(alias="__typename")
    id: Optional[str]
    connected_endpoints: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpoints"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpoints(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeDcimEndpoint",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysical",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeDcimEndpoint(
    BaseModel
):
    typename__: Literal[
        "DcimCircuitEndpoint", "DcimEndpoint", "SecurityFirewallInterface"
    ] = Field(alias="__typename")
    id: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalRole"
    ]
    spanning_tree_portfast: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalSpanningTreePortfast"
    ]
    spanning_tree_bpduguard: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalSpanningTreeBpduguard"
    ]
    description: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDescription"
    ]
    lag: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLag"
    tagged_vlan: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlan"
    untagged_vlan: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalUntaggedVlan"
    device: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalSpanningTreePortfast(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalSpanningTreeBpduguard(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDescription(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLag(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeName"
    ]
    channel_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeChannelId"
    ]
    lacp_mode: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLacpMode"
    ]
    evpn_ethernet_segment: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeEvpnEthernetSegment"
    ]
    tagged_vlan: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlan"
    untagged_vlan: "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlan"


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeChannelId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLacpMode(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeEvpnEthernetSegment(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlan(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNode(
    BaseModel
):
    vlan_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeVlanId"
    ]
    status: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeStatus"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNodeStatus(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlan(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNode(
    BaseModel
):
    vlan_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeVlanId"
    ]
    status: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeStatus"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNodeStatus(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlan(
    BaseModel
):
    edges: list[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlanEdges"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlanEdges(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlanEdgesNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlanEdgesNode(
    BaseModel
):
    vlan_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlanEdgesNodeVlanId"
    ]
    status: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlanEdgesNodeStatus"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlanEdgesNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlanEdgesNodeStatus(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalUntaggedVlan(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalUntaggedVlanNode"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalUntaggedVlanNode(
    BaseModel
):
    vlan_id: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalUntaggedVlanNodeVlanId"
    ]
    status: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalUntaggedVlanNodeStatus"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalUntaggedVlanNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalUntaggedVlanNodeStatus(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice",
                "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer", "DcimDevice", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    id: Optional[str]
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDeviceName"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDeviceName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch(
    BaseModel
):
    typename__: Literal["DcimFabricSwitch"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchRole"
    ]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLink(BaseModel):
    edges: list["GenerateAvdDeviceInputsQueryNetworkLinkEdges"]


class GenerateAvdDeviceInputsQueryNetworkLinkEdges(BaseModel):
    node: Optional["GenerateAvdDeviceInputsQueryNetworkLinkEdgesNode"]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNode(BaseModel):
    id: str
    display_label: Optional[str]
    name: Optional["GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeName"]
    role: Optional["GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeRole"]
    include_in_underlay_protocol: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeIncludeInUnderlayProtocol"
    ]
    connected_endpoints: (
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpoints"
    )


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeRole(BaseModel):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeIncludeInUnderlayProtocol(
    BaseModel
):
    value: Optional[bool]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpoints(BaseModel):
    edges: Optional[
        list["GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdges"]
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeDcimEndpoint",
                "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysical",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeDcimEndpoint(
    BaseModel
):
    typename__: Literal[
        "DcimCircuitEndpoint", "DcimEndpoint", "SecurityFirewallInterface"
    ] = Field(alias="__typename")
    id: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalRole"
    ]
    device: "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice"


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice",
                "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer", "DcimDevice", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    id: Optional[str]
    name: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDeviceName"
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDeviceName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch(
    BaseModel
):
    typename__: Literal["DcimFabricSwitch"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchName"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchRole"
    ]
    asn: "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchAsn"
    pod: "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPod"


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchRole(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchAsn(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchAsnNode"
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchAsnNode(
    BaseModel
):
    asn: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchAsnNodeAsn"
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchAsnNodeAsn(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPod(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNode"
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNode(
    BaseModel
):
    parent: "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParent"


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParent(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkBuildingBlock",
                "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabric",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkBuildingBlock(
    BaseModel
):
    typename__: Literal["NetworkBuildingBlock", "NetworkPod"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabric(
    BaseModel
):
    typename__: Literal["NetworkFabric"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricName"
    ]
    dci_pool: "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricDciPool"
    fabric_ip_pools: "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPools"


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricDciPool(
    BaseModel
):
    node: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricDciPoolNode"
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricDciPoolNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricDciPoolNodeName"
    ]
    default_prefix_length: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricDciPoolNodeDefaultPrefixLength"
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricDciPoolNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricDciPoolNodeDefaultPrefixLength(
    BaseModel
):
    value: Optional[Any]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPools(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreResourcePool",
                "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreResourcePool(
    BaseModel
):
    typename__: Literal["CoreIPAddressPool", "CoreNumberPool", "CoreResourcePool"] = (
        Field(alias="__typename")
    )
    id: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool(
    BaseModel
):
    typename__: Literal["CoreIPPrefixPool"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolName"
    ]
    resources: "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources"


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolName(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges"
        ]
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix",
                "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


GenerateAvdDeviceInputsQuery.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitch.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroup.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomain.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNodeFabric.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeLocalDomainNodeFabricNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePod.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomain.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNodeFabric.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodePodNodeEvpnDomainNodeFabricNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembers.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodePod.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeMembersEdgesNodePodNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomain.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeFabric.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeFabricNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroups.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomain.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNodeFabric.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeLocalDomainNodeFabricNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePod.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomain.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNodeFabric.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodePodNodeEvpnDomainNodeFabricNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembers.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodePod.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeEvpnGatewayGroupNodeRemoteDomainNodeRemoteGatewayGroupsEdgesNodeMembersEdgesNodePodNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeAsn.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeAsnNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIp.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNodeIpPrefix.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeLoopbackIpNodeIpPrefixNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIp.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNodeIpPrefix.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeVtepLoopbackIpNodeIpPrefixNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMgmtIp.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMgmtIpNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomain.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeAsn.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodeAsnNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodePeers.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodePeersEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeMlagDomainNodePeersEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRack.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevices.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeRackNodeDevicesEdgesNodeDcimFabricSwitch.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePod.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPools.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPool.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResources.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPool.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResources.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagPeerPool.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagPeerPoolNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagL3Pool.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeMlagL3PoolNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeRacks.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeRacksEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeRacksEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParent.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkBuildingBlock.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabric.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildren.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPod.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevices.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfaces.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysical.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnector.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpoints.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterface.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDevice.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricChildrenEdgesNodeNetworkPodDevicesEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUplinkPool.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricUplinkPoolNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPools.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPool.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResources.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVtepPool.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricVtepPoolNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLoopbackPool.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLoopbackPoolNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePriorities.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePrioritiesEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricSpanningTreePrioritiesEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServers.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricDnsServersEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServers.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricNtpServersEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsers.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricLocalUsersEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdEvpn.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodePodNodeParentNodeNetworkFabricAvdEvpnNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfaces.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysical.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlan.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlanEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalTaggedVlanEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalUntaggedVlan.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalUntaggedVlanNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLag.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlan.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeUntaggedVlan.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnector.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpoints.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterface.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDevice.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimGenericDevice.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeDcimInterfaceDeviceNodeDcimFabricSwitch.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysical.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLag.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlan.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlan.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembers.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnector.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpoints.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysical.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLag.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlan.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeTaggedVlanEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlan.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeUntaggedVlanNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlan.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlanEdges.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalTaggedVlanEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalUntaggedVlan.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalUntaggedVlanNode.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice.model_rebuild()
GenerateAvdDeviceInputsQueryDcimFabricSwitchEdgesNodeInterfacesEdgesNodeInterfacePhysicalConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalLagNodeLagMembersEdgesNodeConnectorNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLink.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdges.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNode.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpoints.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdges.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysical.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchAsn.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchAsnNode.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPod.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNode.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParent.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabric.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricDciPool.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricDciPoolNode.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPools.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdges.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges.model_rebuild()
GenerateAvdDeviceInputsQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix.model_rebuild()

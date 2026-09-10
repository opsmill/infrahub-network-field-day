# Schema Design Specification: Technical and Service Layers for the Full NFD41 Lab

> **This is a schema design spec.** The implementing agent MUST use the `infrahub-managing-schemas` skill to build and validate all schema definitions.

**Feature Branch**: `nfd41-fabric-model`
**Created**: 2026-09-10
**Status**: Draft
**Input**: User description: "we have a lab in ../labs i believe we have modeled the AVD part is correct. However we need to start looking at the Kubernetes part and Cilium maybe so that we can start generating the crossplane configuration in Infrahub. Note that we should have a technical layer and a services layer, like a services schema with a generator that sits underneath the services schema. That would be nice. Essentially we want to ensure that we can contain all of the information that is in the lab: the ISP, the branches, and the firewall. We can model it in Infrahub and then have services deployed on top for different components altogether."

## Context

The NFD41 lab (sibling repo `../lab`) is a 30-node ContainerLab topology with 41 links
and 108 verification assertions. Infrahub currently models only the Arista EVPN/VXLAN
fabric: `NetworkFabric` -> `NetworkPod` -> `LocationRack` -> `DcimDevice`, plus VRFs,
EVPN tenants, SVIs, and the per-VRF handoffs in `objects/27_nfd41_vrf_services.yml`.

Four domains of the lab are not modeled at all, and each is currently held in a
hand-maintained file outside Infrahub:

| Lab domain | Where the truth lives today | What renders it |
| --- | --- | --- |
| ISP, WAN tenants, sites, internet, branch | `../lab/wan/tenants.yml` | `wan/render.py` -> FRR configs |
| Perimeter firewall zones, address book, policies | `../lab/configs/fw/vsrx/junos.conf` | hand-written, pushed as-is |
| Kubernetes cluster, Cilium CNI, BGP peering | `../lab/crossplane/platform/10-peering.yaml` | Crossplane compositions |
| Applications, VIPs, network policy, access grants | `../lab/crossplane/apps/`, `../lab/crossplane/access/` | Crossplane compositions |

There is also no layering distinction in the current schema. Every node is a technical
fact about a device; nothing expresses "acme buys internet access" or "the branch may
reach Kanboard" as an intent object that materializes technical facts beneath it.

This specification defines the data model for both layers. Generators that materialize
technical objects from service intent, and transforms that render Crossplane manifests
from the resulting graph, are separate cycles that depend on this one.

### Layering contract

- **Technical layer** — what exists, per device: interfaces, addresses, zones,
  address-book entries, cluster nodes, BGP sessions, attachment circuits. Every
  attribute maps to something a renderer emits into a device or cluster config.
- **Service layer** — what was ordered, per consumer: an L3VPN, an internet-access
  product, an isolated tenant cloud, a fabric-peered cluster, an exposed application,
  an access grant. A service names its consumer, its status, and its intent; it does
  not carry per-device detail.
- Services reference technical objects through relationships. A generator sitting
  underneath each service kind reads the service and upserts the technical objects that
  realize it. No renderer reads the service layer directly.

## Schema Files

All schema definitions live in `schemas/*.yml`. Each file must start with:

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"
```

Planned file layout, following the existing split between `schemas/base/` and
per-feature directories:

| File | Contents |
| --- | --- |
| `schemas/service/service.yml` | `ServiceGeneric` and the binding generics (US1) |
| `schemas/kubernetes/kubernetes.yml` | Cluster, nodes, CNI, CIDRs, BGP peering (US2) |
| `schemas/service/kubernetes_services.yml` | `ServiceFabricPeering`, `ServiceFabricApp` (US3) |
| `schemas/security/security.yml` | Zones, address objects, groups, policies, rules (US4) |
| `schemas/service/access_services.yml` | `ServiceAppAccess` (US5) |
| `schemas/wan/wan.yml` | ISP, PE role, attachment circuits, branch circuit (US6) |
| `schemas/service/wan_services.yml` | `ServiceL3vpn`, `ServiceInternetAccess`, `ServiceTenantCloud` (US7) |

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Services layer foundation (Priority: P1)

Introduce the abstraction that separates ordered intent from device fact: a
`ServiceGeneric` generic carrying the identity, lifecycle status, and owner that every
service kind shares, plus binding generics that let a service attach to the devices,
interfaces, and VRFs that realize it.

**Why this priority**: Every other service story inherits from this generic. Without it
each service kind re-declares name, status, and owner, and there is no single kind a
menu, a query, or a generator-target group can select on to answer "what services exist
and what state are they in".

**Independent Test**: `uv run infrahubctl schema check schemas/` passes, and after
loading, a GraphQL query on `ServiceGeneric` returns an empty typed result set with
`name`, `status`, and `owner` selectable — proving the abstraction is queryable across
service kinds before any concrete kind exists.

**Acceptance Scenarios**:

1. **Given** no service abstraction exists, **When** `schemas/service/service.yml` is loaded, **Then** `ServiceGeneric` exists as a generic with `name`, `status`, and an `owner` relationship to `OrganizationGeneric`
2. **Given** `ServiceGeneric` exists, **When** a concrete node declares `inherit_from: [ServiceGeneric]`, **Then** it acquires the shared attributes and appears in a query on `ServiceGeneric`
3. **Given** the binding generics exist, **When** a service is related to a `DcimDevice`, **Then** the device's own view lists the services that touch it via the matching bidirectional identifier
4. **Given** a service is created without a status, **When** it is saved, **Then** it defaults to the pre-deployment state rather than being rejected

---

### User Story 2 - Kubernetes and Cilium technical layer (Priority: P1)

Model the k3s cluster as a first-class routing participant in the fabric: the cluster,
its nodes, the CNI in use, the node/pod/service CIDRs, the VIP pool, and the BGP
sessions Cilium holds with the two `k8s-leaf` switches.

**Why this priority**: This is the domain the request names first, and it is the one
whose truth is most duplicated today. `../lab/crossplane/platform/10-peering.yaml`
carries five values (local ASN 65401, peer addresses 10.110.0.2 and 10.110.0.3, peer
ASN 65101, the auth secret, and the advertised communities) that each have a
counterpart the fabric generators already emit onto the leaves. Modeling the cluster
side in the same graph is what makes the two halves checkable rather than
comment-linked.

**Independent Test**: Schema check passes; the cluster, its three nodes, and its two
BGP peerings can be created as objects and the peering's leaf-side neighbour resolves
to an existing `DcimDevice` in the fabric, so the cross-domain link is proven without
any service kind or renderer existing.

**Acceptance Scenarios**:

1. **Given** the fabric is modeled but no cluster is, **When** `schemas/kubernetes/kubernetes.yml` is loaded, **Then** a cluster node exists carrying the local ASN, the CNI kind and version, and the pod, service and node CIDRs
2. **Given** a cluster exists, **When** cluster nodes are added, **Then** each node relates to the `DcimDevice` or `ComputePhysicalServer` it runs on and carries whether it participates in fabric BGP
3. **Given** a cluster and the fabric both exist, **When** a fabric peering is created, **Then** it names the cluster's local ASN, the leaf device, the leaf's SVI address, and the leaf's BGP ASN, and rejects a duplicate peering to the same leaf
4. **Given** a peering names a leaf SVI address, **When** that address is the MLAG pair's shared VARP gateway rather than a leaf's unique SVI, **Then** the model records the unique address because the peering relates to exactly one device
5. **Given** a VIP pool is defined, **When** its CIDR falls outside the range the leaves' inbound route policy accepts, **Then** the mismatch is representable and detectable in the graph rather than only discoverable as a silently rejected advertisement

---

### User Story 3 - Kubernetes platform and application services (Priority: P2)

Add the two service kinds that render Crossplane manifests: a fabric-peering service
that expresses "this cluster peers with the fabric", and a fabric-application service
that expresses "this application is a participant in the fabric" — its namespace,
tenant, workload source, exposed VIP block, service selector, and network policy
baseline.

**Why this priority**: These are the service kinds the request's stated goal depends on.
They are P2 rather than P1 only because they inherit from US1 and reference the
technical objects from US2.

**Independent Test**: Schema check passes, and the lab's existing `FabricPeering` and
`FabricApp` custom resources can each be represented as a single Infrahub object with
no field left unmodeled — verified by transcribing `../lab/crossplane/platform/10-peering.yaml`
and `../lab/crossplane/apps/10-demo.yaml` into objects and confirming a lossless
round trip of every field the compositions consume.

**Acceptance Scenarios**:

1. **Given** a cluster and its fabric peerings exist, **When** a fabric-peering service is created, **Then** it relates to exactly one cluster and to the peerings that realize it, and carries the advertised communities and the advertisement selector label
2. **Given** the peering service exists, **When** a fabric-application service is created, **Then** it carries its namespace, its fabric tenant, its VIP block, its service selector, and its network-policy baseline as structured attributes
3. **Given** an application service declares source networks it accepts traffic from, **When** those sources are recorded, **Then** they are relationships to IPAM prefixes rather than free-text CIDRs, so the same prefix that the firewall policy and the route policy reference is the one the network policy names
4. **Given** an application service is created without an exposure block, **When** it is saved, **Then** it is valid and represents a cluster-internal application with no VIP, no advertisement, and no route off the cluster
5. **Given** an application service names a workload source, **When** that source is an upstream Helm chart, raw manifests, or both, **Then** all three combinations are representable

---

### User Story 4 - Firewall and security technical layer (Priority: P2)

Model the perimeter vSRX as data: its six security zones, the interface each zone
binds to, the address-book entries and groups, and the zone-pair policies with their
ordered rules, match criteria, and actions.

**Why this priority**: The firewall is the enforcement point every other domain routes
through, and it is the one device in the lab with no model at all — its entire
configuration is a hand-written 600-line file. It is also a hard dependency of US5:
an access grant cannot name a source zone or a source address object that Infrahub
does not know about.

**Independent Test**: Schema check passes, and all six zones, all thirteen address-book
entries, all four address groups, and all eleven zone-pair policies with their
nineteen rules in `../lab/configs/fw/vsrx/junos.conf` can be represented as objects with
rule ordering preserved — verified by transcription without a renderer existing.

**Acceptance Scenarios**:

1. **Given** the firewall device exists in DCIM, **When** `schemas/security/security.yml` is loaded, **Then** security zones exist, each relating to the firewall device and to the interfaces bound into it
2. **Given** zones exist, **When** address objects are created, **Then** each references an IPAM prefix or IP address rather than restating a CIDR as text
3. **Given** address objects exist, **When** an address group is created, **Then** it can contain address objects, prefixes, and other groups
4. **Given** zones and address objects exist, **When** a zone-pair policy is created with several rules, **Then** the rules carry an explicit sequence so first-match evaluation order is deterministic and reviewable
5. **Given** a policy rule is created, **When** it names source addresses, destination addresses, applications, and an action, **Then** all four are modeled, and the deny action is distinguishable from the absence of a permit
6. **Given** two zone-pair policies exist for the same zone pair, **When** they are created, **Then** the uniqueness constraint rejects the duplicate

---

### User Story 5 - Self-service application access (Priority: P3)

Model the access grant: a request naming a requester, an application, a source, a
destination VIP, and a set of ports, gated by an approval flag, that composes the
application deployment and the firewall rule as two halves of one declaration.

**Why this priority**: This is the workflow layer on top of US3 and US4 and cannot be
modeled before either. It is also the one service whose lifecycle a human drives, which
makes it the natural first candidate for the service portal.

**Independent Test**: Schema check passes, and the lab's `AppAccess` and the
`FirewallAccess` it emits can both be represented — an unapproved grant is inert and
composes nothing, and an approved grant names every object a reviewer would need to
revoke it.

**Acceptance Scenarios**:

1. **Given** an application service and firewall zones exist, **When** an access-grant service is created, **Then** it names the requester, the application, the source zone, the source address object, the destination VIP, and the permitted ports
2. **Given** a grant is created, **When** it has not been approved, **Then** its status reflects that it is pending and nothing downstream is expected to have been materialized
3. **Given** a pending grant, **When** it is approved, **Then** the approver and the approval are recorded on the object, so the audit trail lives with the grant rather than only in a change history
4. **Given** an approved grant, **When** its destination VIP falls outside the range the border leaf re-advertises to the source, **Then** the grant is representable and the unreachability is detectable from the graph
5. **Given** an approved grant, **When** it is decommissioned, **Then** the objects it caused to exist are identifiable from its relationships so revocation removes the firewall rule with the application

---

### User Story 6 - Provider, WAN and branch technical layer (Priority: P3)

Model everything outside the fabric that `../lab/wan/tenants.yml` currently holds: the
ISP and its autonomous system, the customer-facing and DC-facing PE roles, the internet
autonomous system and its peering, each tenant site's attachment circuit and how it is
attached, and the branch office's private circuit.

**Why this priority**: This is the largest domain by object count and the one furthest
from the stated Kubernetes goal, but it is explicitly named in the request as
information the model must be able to contain. It is independent of US2 through US5.

**Independent Test**: Schema check passes, and every field of `../lab/wan/tenants.yml`
— both tenants, all three sites, both attachment kinds, the internet peering, and the
branch — can be represented as objects, verified by transcription against the file.

**Acceptance Scenarios**:

1. **Given** the ISP is not modeled, **When** `schemas/wan/wan.yml` is loaded, **Then** the provider, its ASN, and its PE devices are representable with the customer-facing and DC-facing roles distinguished
2. **Given** the provider exists, **When** a tenant site's attachment circuit is created, **Then** it carries the PE-side and CE-side interfaces and addresses as two distinct endpoints on two distinct devices
3. **Given** a site is attached, **When** its attachment is a dynamic-routing handoff, **Then** the site's own ASN and the BGP session are modeled; **When** it is a statically routed handoff, **Then** no session exists and the static route is modeled instead — and both normalize into the same tenant VPN
4. **Given** a tenant has more than one site, **When** both are attached, **Then** they share one tenant VPN, so their mutual reachability follows from shared membership rather than from any leaked route
5. **Given** the branch office exists, **When** its circuit is modeled, **Then** it terminates on the border leaf with no provider in the path, and its switched LAN segment is modeled as a segment shared by three hosts rather than as a link per host

---

### User Story 7 - Provider and tenant services (Priority: P3)

Add the service kinds that sit on top of US6: the tenant L3VPN, the internet-access
product a tenant either buys or does not, and the isolated tenant cloud that couples a
fabric VRF, a firewall zone, and a subnet.

**Why this priority**: Completes the layering across the last domain. Depends on US1
and US6, and on the firewall zones from US4 for the tenant cloud.

**Independent Test**: Schema check passes, and the difference between the two lab
tenants is expressible purely as the presence or absence of one internet-access service
— acme has one, globex does not — with no other field differing between them.

**Acceptance Scenarios**:

1. **Given** the provider and sites exist, **When** an L3VPN service is created, **Then** it relates to one tenant, one VRF on the provider edge, and the attachment circuits of its member sites
2. **Given** an L3VPN exists, **When** an internet-access service is attached to it, **Then** the tenant is understood to receive a default route and to have its prefixes announced upstream
3. **Given** two L3VPNs exist and only one has an internet-access service, **When** they are compared, **Then** that single service is the only difference between them
4. **Given** a tenant buys isolated cloud resources, **When** a tenant-cloud service is created, **Then** it relates to its fabric VRF, its firewall zone, and its subnet as three existing technical objects
5. **Given** two tenant-cloud services exist, **When** they are inspected, **Then** neither imports the other's route targets, so the isolation is structural in the model rather than a policy that could be relaxed

---

### Edge Cases

- What happens when a service is deleted but the technical objects its generator created still exist — are they orphaned, cascaded, or blocked?
- How does the model represent a technical object that a service did *not* create, such as the hand-written anti-spoofing rule repeated at the head of every zone pair, so a generator does not delete it as unmanaged?
- What if two services claim the same technical object — for example two application services selecting overlapping VIP blocks inside the same pool?
- How does a service in the pre-deployment state differ from one whose generator ran and failed, given both have no technical objects beneath them?
- What happens when a policy rule references an address group that is later emptied — is an empty group a match-nothing rule or a match-anything rule?
- What if a firewall zone is deleted while an access grant still names it as its source zone?
- How is rule ordering preserved when two rules are inserted with the same sequence number?
- What happens when a cluster's pod CIDR overlaps an existing IPAM prefix already allocated to the fabric?
- What if a cluster node's underlying device is decommissioned while the node remains in the cluster?
- What happens when a mandatory attribute is added to an existing node and instances already exist without it?
- How does the model handle the branch office, which is deliberately neither a WAN tenant nor a fabric tenant, without forcing it into either shape?
- What if a tenant site is attached to a PE interface that another site's circuit already claims?

## Requirements *(mandatory)*

### Functional Requirements

#### Nodes & Generics

- **FR-001**: Schema MUST define `ServiceGeneric` as a generic under the `Service` namespace, holding the attributes and relationships every service kind shares
- **FR-002**: Schema MUST define binding generics under the `Service` namespace that let a service attach to devices, interfaces, and VRFs, so a device's own view can list the services that touch it
- **FR-003**: Schema MUST define concrete service nodes under the `Service` namespace for: fabric peering, fabric application, application access, tenant L3VPN, internet access, and tenant cloud
- **FR-004**: Schema MUST define technical nodes under the `Kubernetes` namespace for the cluster, its nodes, and its fabric BGP peerings
- **FR-005**: Schema MUST define technical nodes under the `Security` namespace for zones, address objects, address groups, applications, zone-pair policies, and policy rules
- **FR-006**: Schema MUST define technical nodes under the `Wan` namespace for the tenant, the site, the attachment circuit, and the internet peering, reusing `OrganizationProvider` for the ISP rather than introducing a parallel provider kind
- **FR-007**: Every concrete service node MUST inherit from `ServiceGeneric` via `inherit_from`
- **FR-008**: All node and generic names MUST be PascalCase (pattern `^[A-Z][a-zA-Z0-9]+$`, 2-32 chars)
- **FR-009**: All namespaces MUST match `^[A-Z][a-z0-9]+$` (3-32 chars), which the four new namespaces `Service`, `Kubernetes`, `Security`, and `Wan` satisfy
- **FR-010**: Schema MUST NOT redefine anything the fabric already models — VRFs (`IpamVRF`), EVPN tenants (`EvpnTenant`), SVIs (`EvpnSvi`), prefixes and addresses (`IpamPrefix`, `IpamIPAddress`), ASNs (`RoutingAsn`), devices (`DcimDevice`), or interfaces (`DcimInterface`) — and MUST relate to those kinds instead

#### Attributes

- **FR-020**: `ServiceGeneric` MUST define a `name` attribute of kind Text, and MUST define a lifecycle `status` attribute of kind Dropdown whose choices distinguish at minimum a pre-deployment state, an active state, and a decommissioning state, with a default of the pre-deployment state
- **FR-021**: The Kubernetes cluster node MUST carry its local BGP autonomous system number as kind Number, and its CNI kind and version as attributes
- **FR-022**: The Kubernetes cluster node's pod, service, and node ranges MUST be relationships to `IpamPrefix`, not IPNetwork attributes, so the same prefix the fabric route policy accepts is the object the cluster references
- **FR-023**: The fabric-peering node MUST carry the peer autonomous system number as kind Number and relate to the leaf `DcimDevice` and to the leaf-side `IpamIPAddress`
- **FR-024**: The fabric-application service MUST carry its Kubernetes namespace name, its fabric tenant, and its network-policy baseline flags as discrete attributes rather than as one opaque blob
- **FR-025**: The fabric-application service's workload source MUST support an upstream chart reference, raw manifest content, or both, and MUST NOT require either
- **FR-026**: The security policy rule node MUST carry an explicit ordering attribute of kind Number, and an action attribute of kind Dropdown whose choices include at minimum permit and deny
- **FR-027**: The security zone node MUST carry a name and MAY carry a trust level of kind Number to order zones by trust
- **FR-028**: The WAN site node MUST carry an attachment kind of kind Dropdown distinguishing a dynamic-routing handoff from a statically routed handoff
- **FR-029**: The access-grant service MUST carry an approval flag of kind Boolean defaulting to false, an approver, a requester, a justification, and the permitted ports
- **FR-030**: All Dropdown attributes MUST include a `choices` list with at least `name` per choice
- **FR-031**: All attribute names MUST be snake_case (pattern `^[a-z0-9\_]+$`, 3-64 chars)
- **FR-032**: Attribute kinds MUST come from the supported set (Text, TextArea, Number, Boolean, Dropdown, IPHost, IPNetwork, DateTime, URL, Email, JSON, List, and the rest) and MUST NOT use the deprecated `String` kind
- **FR-033**: Text and Number validation MUST be expressed in a `parameters` block rather than as deprecated top-level `regex`, `min_length`, `max_length`, `min_value`, or `max_value` keys

#### Relationships

- **FR-040**: `ServiceGeneric` MUST relate to `OrganizationGeneric` with cardinality one as the service's owner
- **FR-041**: The Kubernetes cluster MUST own its nodes and its fabric peerings with `Component` relationships, and each MUST point back with a matching `Parent` relationship
- **FR-042**: The security zone-pair policy MUST own its rules with a `Component` relationship, and each rule MUST point back with a matching `Parent` relationship
- **FR-043**: All `Component`/`Parent` pairs MUST use matching `identifier` values on both sides, in `parent__children` snake_case form
- **FR-044**: Security address objects MUST relate to `IpamPrefix` or `IpamIPAddress` with cardinality one, so no CIDR is restated as text
- **FR-045**: The security zone MUST relate to the firewall `DcimDevice` and to the `DcimInterface` set bound into it
- **FR-046**: The WAN attachment circuit MUST model the provider-edge side and the customer-edge side as two distinct interface relationships on two distinct devices
- **FR-047**: The tenant-cloud service MUST relate to its `IpamVRF`, its security zone, and its `IpamPrefix`
- **FR-048**: The L3VPN service MUST relate to its WAN tenant with cardinality one and to the attachment circuits of its member sites with cardinality many
- **FR-049**: The access-grant service MUST relate to the fabric-application service it grants access to, to its source security zone, and to its source address object
- **FR-050**: All relationship `peer` values MUST use the full kind (namespace + name, e.g. `DcimDevice`, `IpamPrefix`)
- **FR-051**: All relationship names MUST be snake_case (pattern `^[a-z0-9\_]+$`, 3-64 chars)
- **FR-052**: Relationships added to nodes defined in other schema files — the `device_services` and `interface_services` back-references on `DcimGenericDevice` and `DcimInterface` — MUST be declared in an `extensions:` block rather than by editing `schemas/base/dcim.yml`
- **FR-053**: Relationships from a service to a technical object MUST set `on_delete: no-action`, so deleting a service does not cascade into infrastructure the service merely referenced

#### Display & Identification

- **FR-060**: Every user-facing node MUST define `human_friendly_id` using attribute paths, and nodes that are unique only within a parent MUST include the parent path (e.g. `["policy__name__value", "name__value"]` for a policy rule)
- **FR-061**: Every node MUST define `display_label`, as an attribute path or a Jinja2 template
- **FR-062**: Every node MUST define `order_by`
- **FR-063**: Attributes and relationships MUST use `order_weight` following the project convention: 900-999 primary relationships, 1000-1099 primary identifiers, 1100-1499 secondary, 1500-1999 tertiary, 2000+ computed and metadata, 3000+ tags
- **FR-064**: Every user-facing node MUST set an `icon` and a `label`
- **FR-065**: Service nodes MUST be placed in the menu beneath a service grouping, and technical nodes beneath their domain grouping, so the UI reflects the two-layer split

#### Uniqueness Constraints

- **FR-070**: `ServiceGeneric` MUST constrain `name` to be unique across services
- **FR-071**: The Kubernetes fabric peering MUST be unique per cluster and leaf device
- **FR-072**: The security zone-pair policy MUST be unique per source and destination zone pair
- **FR-073**: The security policy rule MUST be unique per policy and name, and its ordering attribute MUST be unique within its policy
- **FR-074**: The WAN site MUST be unique per tenant and name; the attachment circuit MUST be unique per provider-edge interface
- **FR-075**: Uniqueness constraints MUST use the `__value` suffix for attribute references and bare names for relationship references

#### Layering

- **FR-080**: No technical node MUST carry a relationship whose peer is a concrete service kind; the technical layer MUST remain usable with the service layer absent
- **FR-081**: Every concrete service kind MUST be reachable as a generator target, so a generator can sit underneath it and materialize the technical objects it implies
- **FR-082**: Service nodes MUST record which technical objects realize them through relationships, so the objects a service caused to exist are identifiable for revocation
- **FR-083**: Every service kind whose intent is delivered to the cluster as a Crossplane manifest MUST be capable of acting as an artifact target, so a later cycle can attach an artifact definition without a schema change

#### Migration

- **FR-090**: Removed attributes MUST use `state: absent` rather than being deleted from the YAML
- **FR-091**: New mandatory attributes on existing nodes MUST either carry a `default_value` or be introduced as `optional: true` first
- **FR-092**: After every schema change, protocols MUST be regenerated with `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py`

### Key Entities

**Service layer (`Service` namespace)**

- **ServiceGeneric** *(generic)*: what every service shares — name, lifecycle status, owning organization. The kind a menu, a query, or a report selects on to answer "what is deployed and in what state".
- **ServiceFabricPeering**: a cluster's routing contract with the fabric. Relates to one Kubernetes cluster and the peerings that realize it; carries advertised communities and the advertisement selector.
- **ServiceFabricApp**: an application that is a participant in the fabric. Carries namespace, fabric tenant, workload source, VIP block, service selector, and network-policy baseline; relates to the source prefixes permitted to reach it.
- **ServiceAppAccess**: one grant of "this person may use that application". Carries requester, justification, approval, approver, destination VIP, and ports; relates to the application service, the source zone, and the source address object.
- **ServiceL3vpn**: a tenant's VPN across the provider. Relates to one WAN tenant, the provider-edge VRF, and its member sites' attachment circuits.
- **ServiceInternetAccess**: the internet-access product, attached to an L3VPN. Its presence or absence is the entire difference between the lab's two tenants.
- **ServiceTenantCloud**: a tenant's isolated compute in the datacentre. Relates to a fabric VRF, a firewall zone, and a subnet.

**Kubernetes technical layer (`Kubernetes` namespace)**

- **KubernetesCluster**: the k3s cluster. Local BGP ASN, CNI kind and version; relates to its pod, service, and node prefixes and owns its nodes and peerings.
- **KubernetesNode**: one cluster member. Relates to the device or server it runs on; records whether it participates in fabric BGP.
- **KubernetesFabricPeering**: one BGP session between the cluster and one leaf. Relates to the leaf device and the leaf-side SVI address; carries the peer ASN and session timers.

**Security technical layer (`Security` namespace)**

- **SecurityZone**: one firewall security zone. Relates to the firewall device and the interfaces bound into it; carries an optional trust level.
- **SecurityAddress** / **SecurityAddressGroup**: address-book entries and their groups. Each entry references an IPAM prefix or address; groups may nest.
- **SecurityApplication**: a port and protocol tuple a rule matches on.
- **SecurityPolicy**: one zone-pair policy, unique per source and destination zone; owns its rules.
- **SecurityPolicyRule**: one ordered rule — sequence, source and destination addresses, applications, action.

**WAN technical layer (`Wan` namespace)**

- **WanTenant**: the unit of isolation on the provider edge. One tenant, one VRF, one identity, one policy; may hold several sites.
- **WanSite**: one location of a tenant, with its attachment kind and its LAN prefix.
- **WanCircuit**: one attachment circuit — the provider-edge interface and address on one device, the customer-edge interface and address on another.
- **WanInternetPeering**: the provider's peering with the internet autonomous system, and the aggregate it announces on its tenants' behalf.

## Assumptions

1. **Namespaces.** `Service`, `Kubernetes`, `Security`, and `Wan` are new and all satisfy the `^[A-Z][a-z0-9]+$` namespace pattern. `Security` follows `opsmill/infrahub-demo-dc`, which uses the same namespace for the same concepts, so the two repositories stay comparable.
2. **The ISP is an organization, not a new kind.** `OrganizationProvider` already exists and is reused for the ISP and the internet autonomous system. The PE role is a device role, not a device kind.
3. **The fabric side is done.** VRFs, EVPN tenants, SVIs, the per-VRF default routes, and the handoffs in `objects/27_nfd41_vrf_services.yml` are treated as correct and are referenced, never re-modeled.
4. **Addresses are IPAM objects.** Every prefix and address a new node needs is a relationship to `IpamPrefix` or `IpamIPAddress`. Free-text CIDRs are the failure mode this model exists to remove — three enforcement points in the lab match on the same networks and must reference the same objects.
5. **Structured content is JSON where structure is user-defined.** Helm values, raw manifests, and label selectors have no fixed shape, so they are JSON attributes. Anything with a fixed shape is a discrete attribute or a relationship.
6. **Generators materialize; renderers read technical objects.** A service's generator upserts the technical objects the service implies. Transforms and artifacts read the technical layer. This keeps the existing renderers unaware of the service layer.
7. **This cycle is schema only.** No generator, transform, artifact definition, object data, or menu file is written here. The `.infrahub.yml` registrations, the seed objects transcribed from `wan/tenants.yml` and `junos.conf`, and the Crossplane transforms are the next cycles in the chain.
8. **Infrahub owns the whole firewall configuration.** *(Confirmed with the requester.)* All six zones, every address-book entry and group, and all eleven zone-pair policies — including the anti-spoofing baseline repeated at the head of the first six pairs — are modeled, so `junos.conf` becomes a rendered artifact rather than a hand-maintained file. This extends the fabric's "nothing is configured by hand" property to the perimeter, and it is why US4 models policies and rules rather than only the grants issued against them. The alternative — modeling zones while leaving the baseline policies hand-written — was rejected because it leaves two sources of truth for one device.
9. **Crossplane manifests are delivered as artifacts reconciled by the Vidra operator.** *(Confirmed with the requester.)* This follows `opsmill/infrahub-dogfooding`, which renders AWS and GCP instance manifests as Infrahub artifacts from a Python transform and has the Vidra operator pull and reconcile them in-cluster. FR-083 is what this assumption costs the schema: service kinds must be able to act as artifact targets. The artifact definitions and the transform belong to a later cycle.
10. **The lab is the acceptance oracle.** `../lab/wan/tenants.yml`, `../lab/configs/fw/vsrx/junos.conf`, and the four files under `../lab/crossplane/` define what "contains all of the information that is in the lab" means. A field in those files with nowhere to go in the model is a gap in this specification.

## Out of Scope

- Generators that materialize technical objects from service intent (next cycle).
- Transforms and artifact definitions that render Crossplane manifests, FRR configs, or Junos configuration (later cycles).
- Object data seeding the model from the lab files (later cycle).
- Menu definitions (later cycle, though FR-065 states the placement the schema must support).
- Any change to the AVD pipeline, the fabric generators, or the EOS rendering path.
- The Guacamole and branch-desktop containers, which are lab plumbing for demonstrating access rather than modeled infrastructure.
- Replacing the lab's Crossplane compositions. Infrahub renders their inputs; the compositions stay where they are.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv run infrahubctl schema check schemas/` passes with zero validation errors
- **SC-002**: `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py` regenerates cleanly, and `uv run mypy --show-error-codes src/solution_arista_avd` passes against the regenerated protocols
- **SC-003**: Every field in `../lab/wan/tenants.yml` has a modeled destination — both tenants, all three sites, both attachment kinds, the internet peering, and the branch — with no field left unrepresentable
- **SC-004**: Every zone, address-book entry, address group, and zone-pair policy in `../lab/configs/fw/vsrx/junos.conf` has a modeled destination — 6 zones, 13 addresses, 4 groups, 11 zone pairs and 19 rules — with rule evaluation order preserved
- **SC-005**: Every field the lab's `FabricPeering`, `FabricApp`, `AppAccess`, and `FirewallAccess` resources consume has a modeled destination
- **SC-006**: A reviewer can answer "which services exist, who owns them, and what state are they in" from a single query on `ServiceGeneric`
- **SC-007**: The difference between the lab's two WAN tenants is expressible as the presence of one internet-access service and nothing else
- **SC-008**: No new node restates a prefix or an address as text where an IPAM object exists for it
- **SC-009**: Loading the technical-layer schema files without the service-layer files succeeds, proving the layers are separable
- **SC-010**: Every new user-facing node renders a readable identifier in the UI, and no node is reachable only by internal UUID
- **SC-011**: `uv run invoke lint` passes, including `yamllint` over the new schema files

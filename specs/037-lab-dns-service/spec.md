# Schema Design Specification: Lab DNS Service

> **This is a schema design spec.** The implementing agent MUST use the `infrahub-managing-schemas` skill to build and validate all schema definitions. The DNS records are a transform and the delivery is a generator and a Vidra sync; the specify command is run again for each of those after this cycle (see [Decisions](#decisions)).

**Feature Branch**: `037-lab-dns-service`
**Created**: 2026-10-07
**Status**: Draft
**Input**: User description: "A DNS service for the OTTERNET lab that runs as an application in the Kubernetes lab cluster and answers DNS queries for the branch ubuntu machine. The resolver's records and configuration are rendered as an artifact from Infrahub data, not typed on the resolver, and reach the cluster through the existing Vidra/Crossplane delivery. Every application requested through the portal gets a name such as otter-shop.int.otternet.lab that resolves to its allocated VIP, with no extra input from the requester; the name is added when the proposed change merges and removed when the application is withdrawn. The branch machine is configured to use this resolver for the zone."

## Summary

A branch user who requests an application through the service portal receives an IP address from the application's VIP block and has to remember it. This cycle gives each application a name such as `otter-shop.int.otternet.lab` that resolves to that address. The requester enters nothing extra: the name comes from the application name and a zone that the network team defines once in Infrahub.

The names are answered by a DNS server that runs as an application in the lab's Kubernetes cluster. Its zone file is an artifact that Infrahub renders from the applications it holds, and Vidra delivers it to the cluster as it delivers the telemetry collector's configuration. Nobody types a record on the resolver. The branch ubuntu machine (`branch-desktop`) is the first client and uses this resolver for the zone.

Three choices were made on 2026-10-07 and are listed under [Decisions](#decisions): one name per application pointing at the first address of its VIP block, `branch-desktop` as the only client, and the zone stored on the resolver application with the existing `fqdn` attribute filled.

## Background: what exists today

Every statement below comes from a file in this repository. Where the files say nothing, this document says so.

- An application is a `ServiceFabricApp`. It owns a `vip_block` (an `IpamPrefix`) that `generate-fabric-app` allocates, and an optional list of `advertised_services` ([schemas/service/kubernetes_services.yml](../../schemas/service/kubernetes_services.yml)).
- `IpamIPAddress` already has an optional `fqdn` attribute with a hostname pattern ([schemas/base/ipam.yml](../../schemas/base/ipam.yml)). No file in the repository fills it from an application.
- The telemetry collector's whole configuration is an artifact, `Telemetry Collector Configuration`, rendered by [transforms/telemetry_collector_config.py](../../transforms/telemetry_collector_config.py) and delivered into the namespace `otternet-telemetry` by the Vidra `InfrahubSync` named `telemetry-collector-config` ([vidra/infrahub-syncs.yaml](../../vidra/infrahub-syncs.yaml)). `generate-monitoring-collector` re-renders it on every proposed change and after every merge because its target is the collector rather than the devices ([.infrahub.yml](../../.infrahub.yml)).
- Applications are built on their branch by event rules and withdrawn by setting `status`; `decommissioning` counts as gone ([AGENTS.md](../../AGENTS.md)).
- No trigger rule may name a `Deployment*` or `Monitoring*` kind ([AGENTS.md](../../AGENTS.md)).
- The branch machine is the ContainerLab node `branch-desktop` ([lab/Makefile](../../lab/Makefile)).
- The repository does not say how `branch-desktop` resolves names today, whether any resolver exists in the lab, or which address it would reach a Kubernetes VIP through. This is not known.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A requested application gets a name (Priority: P1)

A branch user requests `otter-shop` through the portal. After the proposed change merges, the user opens `otter-shop.int.otternet.lab` from the branch machine and reaches the application. The user entered no name and no address.

**Why this priority**: it is the outcome the user asked for, and the other stories depend on the names existing.

**Independent Test**: merge a request for one application, then resolve its name from `branch-desktop` and compare the answer with the address in the application's VIP block in Infrahub.

**Acceptance Scenarios**:

1. **Given** an application with an allocated VIP block and an `active` status, **When** its proposed change merges, **Then** a name built from the application name and the zone resolves to the application's address from `branch-desktop`.
2. **Given** an application whose request has not merged, **When** a user resolves its name, **Then** the name does not resolve, because the branch is not yet part of `main`.
3. **Given** the requester filled in only the fields the portal asks for, **When** the application is built, **Then** the name exists without any further input.

---

### User Story 2 - A withdrawn application loses its name (Priority: P1)

A network engineer sets an application's `status` to `decommissioning`. After the change merges, its name no longer resolves.

**Why this priority**: a name that points at an address another application may later receive sends users to the wrong service.

**Independent Test**: withdraw an application, merge, and resolve its former name.

**Acceptance Scenarios**:

1. **Given** a resolving name, **When** the application's `status` becomes `decommissioning` or `decommissioned` and the change merges, **Then** the name returns no answer.
2. **Given** two applications, **When** one is withdrawn, **Then** the other's name is unchanged.

---

### User Story 3 - The resolver's records come only from Infrahub (Priority: P1)

A network engineer wants to know why a name resolves to an address. The engineer views the application in Infrahub and the rendered zone artifact and finds the answer there. Nothing on the resolver was edited by hand.

**Why this priority**: the user asked for the resolver to be configured by artifacts, and a hand-edited record would be overwritten or hidden.

**Independent Test**: compare the zone served by the resolver with the artifact on `main`; they must match record for record.

**Acceptance Scenarios**:

1. **Given** a merged change, **When** the artifact is rendered, **Then** the resolver serves exactly the records in it, once delivery completes.
2. **Given** a proposed change that adds an application, **When** a reviewer opens the change, **Then** the reviewer views the zone artifact difference that adds its name.
3. **Given** a record added by hand on the resolver, **When** the next artifact is delivered, **Then** the hand-added record is gone.

---

### User Story 4 - The branch machine uses the resolver (Priority: P2)

The branch machine is configured so queries for the zone go to the resolver, and other queries behave as they do today.

**Why this priority**: without it the names resolve only for someone who points a client at the resolver by hand.

**Independent Test**: from `branch-desktop`, resolve a name in the zone and a name outside it.

**Acceptance Scenarios**:

1. **Given** `branch-desktop` after a lab build, **When** a name in the zone is resolved, **Then** it is answered by the resolver without the user naming a server.
2. **Given** the same machine, **When** a name outside the zone is resolved, **Then** the answer is the one the machine returned before this cycle.

---

### Edge Cases

- Two applications whose names produce the same label in the zone. The schema already makes `name` unique on `ServiceGeneric`; whether that is enough once a label is derived from it is checked in planning.
- An application with no VIP block yet. The barrier in the portal template waits for the block, but an application created another way may have none. It must get no record rather than an empty or wrong one.
- An application that is not `exposed`. It has no VIP block, so it gets no name. Not confirmed from the files; checked in planning.
- An application name that is not a valid DNS label. The portal already restricts it to lower-case letters, digits and dashes ([backstage/catalog/exposed-app-with-access.yaml](../../backstage/catalog/exposed-app-with-access.yaml)). Applications created through the MCP server or the Infrahub interface are not covered by that pattern.
- The resolver is down or the artifact is empty. An empty zone would remove every name, as an empty SR Linux or Junos artifact erases the device ([AGENTS.md](../../AGENTS.md)). The renderer must refuse an empty result instead of delivering it.
- The resolver's own name. Whether the resolver has a name in the zone is not decided; planning settles it.
- A name changes because the application is renamed. Not known whether a rename is possible once an application exists.

## Requirements *(mandatory)*

### Functional Requirements

#### Zone and names

- **FR-001**: Infrahub MUST hold the DNS zone name (for example `int.otternet.lab`) as data, not as a constant in a transform.
- **FR-002**: Every `ServiceFabricApp` that is `exposed`, has an allocated VIP block and is not withdrawn MUST have exactly one name in the zone, built from the application's `name` and the zone name.
- **FR-003**: The requester MUST NOT be asked for a name or an address. The portal form is unchanged.
- **FR-004**: An application whose `status` is `decommissioning` or `decommissioned` MUST have no name in the zone.
- **FR-005**: The answer for an application's name MUST be an address from that application's VIP block. When several services are advertised, the name still points at the first address of the block ([Decisions](#decisions)).

#### Rendering and delivery

- **FR-010**: The resolver's zone data and its configuration MUST be rendered as one artifact from Infrahub data. The resolver MUST serve nothing that is not in the artifact.
- **FR-011**: The renderer MUST refuse to produce an artifact with no records, and MUST report the reason in the artifact's error.
- **FR-012**: The artifact MUST be delivered to the cluster by a Vidra `InfrahubSync`, as the telemetry collector's configuration is.
- **FR-013**: An application change MUST re-render the artifact on its proposed change, so a reviewer views the new name before merging. The artifact's target is the resolver, not the application, so a generator is needed for the same reason `generate-monitoring-collector` exists.
- **FR-014**: No trigger rule may name a `Deployment*` or `Monitoring*` kind, and nothing may generate from them.
- **FR-015**: The resolver MUST run in the lab's Kubernetes cluster as an application, and MUST itself be requestable and withdrawable in the same way as other applications. Whether it is a `ServiceFabricApp` is not decided.

#### The branch machine

- **FR-022**: The firewall MUST allow the branch zone to reach the resolver on UDP and TCP 53 in the bootstrapped version, as seed data, with no request step ([research R-1](./research.md#r-1)). Added 2026-10-07.
- **FR-020**: After a lab build, `branch-desktop` MUST send queries for the zone to the resolver and MUST NOT change how it resolves other names.
- **FR-021**: The resolver's address that `branch-desktop` uses MUST be held equal to the address Infrahub holds, by a test. It appears once in `lab/wan/tenants.yml` because the host configuration is rendered from that file alone ([research R-4](./research.md#r-4)). Amended 2026-10-07 from "MUST NOT be typed into the lab's ContainerLab files".

#### Schema

- **FR-030**: The schema MUST record the zone and, for each name, the application it belongs to and the address it answers with. This uses the existing `IpamIPAddress.fqdn`; a new kind is added only if planning finds it cannot express withdrawal ([Decisions](#decisions)).
- **FR-031**: Any new node MUST be named in PascalCase under a namespace that starts with an uppercase letter followed by lower-case letters, MUST define `human_friendly_id` and `display_label`, and MUST NOT make an attribute mandatory on a kind that already holds data (it is refused).
- **FR-032**: Any new node MUST be added to the groups its artifact and generator definitions target, and MUST inherit `CoreArtifactTarget` if it is a target.
- **FR-033**: `protocols.py` and the `*_query.py` files MUST be regenerated, not edited.

### Key Entities

- **DNS zone**: the domain the resolver answers for, such as `int.otternet.lab`. One exists for the lab. It is stored on the resolver application ([Decisions](#decisions)).
- **DNS resolver**: the application in the Kubernetes cluster that serves the zone. It owns its own VIP.
- **DNS record**: a name in the zone, the application it belongs to, and the address it answers with. A record exists only while the application is not withdrawn.
- **Application (`ServiceFabricApp`)**: already exists. Supplies the name and the VIP block.
- **Zone artifact**: the rendered zone data and resolver configuration, delivered by Vidra.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a requested application's proposed change merges, its name resolves from `branch-desktop` within the time the telemetry collector's configuration takes to reach its cluster (about one minute after the merge; [vidra/infrahub-syncs.yaml](../../vidra/infrahub-syncs.yaml)). Measured, not assumed, in planning.
- **SC-002**: For 100 percent of exposed, active applications on `main`, the zone artifact holds one record, and for 0 withdrawn applications it holds a record.
- **SC-003**: The records served by the resolver and the records in the artifact on `main` are identical when compared after delivery.
- **SC-004**: A requester completes the portal request with no more fields than before this cycle.
- **SC-005**: A reviewer opening a proposed change that adds an application views the added name in the artifact difference.
- **SC-006**: `infrahubctl schema check schemas/` passes with no errors.
- **SC-007**: A name outside the zone resolves from `branch-desktop` exactly as it did before this cycle.

## Decisions

Alex Gittings chose the recommended answer to each question on 2026-10-07.

1. **Several services: one name per application.** The name points at the first address in the application's VIP block. An extra name per advertised service is a later cycle, if one is needed.
2. **Clients: `branch-desktop` only.** The sites, the tooling cluster and the other lab hosts are later cycles.
3. **Zone and resolver VIP: stored on the resolver application, and the existing `IpamIPAddress.fqdn` is filled on the application's VIP address.** A new kind is added only if planning finds this cannot express withdrawal.

## Assumptions

- The Kubernetes lab cluster can run a DNS server image and give it a `LoadBalancer` VIP in the same way it does for other applications. [CLAUDE RECOMMENDED – based on the existing `ServiceFabricApp` delivery] Not verified.
- The branch machine can reach the resolver's VIP through the fabric and the firewall. Not known; the firewall rules for it are not modelled.
- The renderer and the generator are specified in their own cycles, after the schema, as the routing hook requires one artifact type per cycle.

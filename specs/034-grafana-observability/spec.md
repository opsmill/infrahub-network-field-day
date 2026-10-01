# Schema Design Specification: Grafana Observability, Requested Like Any Other Application

> **This is a schema design spec.** The implementing agent MUST use the `infrahub-managing-schemas` skill to build and validate all schema definitions.

**Feature Branch**: `034-grafana-observability`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "I want to add grafana in the k8's cluster with metrics about the lab/organistation dashboards etc. Maybe we can have network telemetry, https://docs.infrahub.app/exporter etc, please provision through infrahub and ensure that when bootstrapped everything is spun up working and then in the demo we can give alice access through a request to grafana, grafana must work through dex login"

## Schema Files

All schema definitions live in `schemas/*.yml`. Each file must start with:

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"
```

The kinds in scope are the new monitoring-intent kinds, in a new file under `schemas/`, and
`ServiceFabricApp` in `schemas/service/kubernetes_services.yml`. `ServiceAppAccess` is
**unchanged**: alice's request is an ordinary network grant.

This feature spans several Infrahub artifact types. Schema comes first because everything else
depends on it: seed objects, the collector-configuration transforms and artifact definitions,
the device renderers (AVD, `frr_config`, `junos_config`), and the bootstrap and verification
scripts.

---

## Context

Today the cluster has **no observability that Infrahub can account for**. The lab repository's
installer applies `otternet-observability`, a kube-prometheus-stack carrying Grafana and
Prometheus. `invoke cluster`'s handover then deletes it, deliberately, because nothing models
it: a workload no service object declares is state no proposed change can explain. Its VIP block
(`10.112.240.64/28`) was also picked by hand, outside Infrahub, and has already collided once
with a block the portal allocated.

Three further gaps:

- **Nothing collects metrics.** There are no metrics about the organisation's intent (devices,
  services, tenants, requests), and nothing collects telemetry from the devices. The cEOS boot
  template enables gNMI, but no collector reads from it.
- **Monitoring is not intent.** Even where something is collected (the lab's Cilium and Hubble
  metrics), what is watched is a hand-written scrape list, so it cannot follow the model.
- **Branch users already have a dead Grafana bookmark.** The branch desktop has a "Grafana
  (needs access)" bookmark pointing at an address no Infrahub-owned application occupies.

This feature makes observability an **Infrahub-owned application**, and makes Infrahub the thing
that decides what is monitored, as well as what is configured. Infrahub renders the telemetry
collectors' configuration as **artifacts**, which Telegraf and similar collectors consume as-is,
the same way it renders device configuration. Bootstrap delivers all of it working. In the demo,
alice asks for Grafana through the portal. Merging that request opens the network path, and she
signs in through Dex.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Observability is an Infrahub-owned application (Priority: P1)

The cluster's Grafana and Prometheus are declared as a seeded `ServiceFabricApp` and delivered by
the same path as every other application: rendered into an artifact and delivered by Vidra. Its
VIP block is recorded in Infrahub, so no allocation can collide with it.

**Why this priority**: Without this nothing else exists. It also closes the "unmodelled workload"
exception that the handover exists to remove.

**Independent Test**: Load schema and objects on a branch. The observability application renders
a `FabricApp` artifact naming a chart, a version, values, and an Infrahub-recorded VIP block.
After merge and delivery the cluster runs it, and `verify_bootstrap.sh` counts it.

**Acceptance Scenarios**:

1. **Given** a fresh `invoke bootstrap`, **When** it completes, **Then** the observability
   application is running in the cluster, was delivered by Vidra, and Infrahub reports it
   `active`.
2. **Given** the observability application's VIP block, **When** the portal allocates a block for
   a new application, **Then** the allocation never overlaps the observability block.
3. **Given** the lab's own `otternet-observability` claim, **When** the handover runs, **Then** it
   is still removed and the Infrahub-owned application replaces it. There is never more than one
   Grafana in the cluster.

---

### User Story 2 - Grafana signs in through Dex (Priority: P1)

Grafana authenticates against the lab's single Dex issuer. A person signs in with the same alice
or bob identity they use for the portal and Infrahub, and lands with a read-only role. No separate
local Grafana accounts exist for people.

**Why this priority**: The user stated it as a hard requirement. Grafana with a shared admin
password is the very pattern the identity work removed elsewhere.

**Independent Test**: From the branch desktop, open Grafana, choose the Dex sign-in, and
authenticate as alice. Grafana shows that user's identity. No Grafana login form
accepts a person's password directly.

**Acceptance Scenarios**:

1. **Given** Grafana is delivered, **When** a branch user opens it, **Then** they are offered a
   Dex sign-in and arrive back in Grafana signed in as themselves, with the read-only role.
2. **Given** Grafana's sign-in callback, **When** Dex completes a login, **Then** the token
   exchange between Grafana and Dex succeeds. That exchange crosses from the cluster to the
   tooling zone, and the path is modelled in Infrahub.
3. **Given** the Dex client credential for Grafana, **When** the application artifact is
   rendered, **Then** the credential appears nowhere in the graph or in the artifact.

---

### User Story 3 - Alice gets Grafana by asking for it (Priority: P1)

At the start of the demo, alice cannot reach Grafana from the branch desktop: there is no route
and no firewall permit. She requests access through the portal, using the existing
`ServiceAppAccess` request with no new fields. The request lands on a branch with a proposed
change showing its consequences: the firewall rule, the fabric advertisement, the application's
network policy and the re-rendered artifacts. Once it merges and delivery converges, she opens
Grafana and signs in through Dex.

**Why this priority**: This is the demo the user asked for, and it is the reason Grafana is
modelled rather than installed.

**Independent Test**: Before the request, Grafana's VIP does not answer from the branch desktop.
After the request merges and the reconciler and Vidra converge, alice opens it, signs in and sees
dashboards. When the grant is withdrawn through `status`, the VIP stops answering again.

**Acceptance Scenarios**:

1. **Given** no grant for Grafana, **When** alice opens it from the branch desktop, **Then** it
   does not answer.
2. **Given** alice submits the request, **When** the proposed change is opened, **Then** it shows
   the grant and every consequence of it before anyone merges.
3. **Given** the change is merged, **When** delivery converges, **Then** alice reaches Grafana,
   signs in through Dex and sees the lab dashboards.
4. **Given** alice's grant is set to `decommissioning`, **When** delivery converges, **Then**
   Grafana no longer answers from the branch. Nothing another grant relies on is withdrawn.

---

### User Story 4 - Dashboards about the lab and the organisation (Priority: P2)

Grafana ships with dashboards provisioned as part of the application, not clicked together by
hand. They show:

- **Organisation intent**, from Infrahub through the Infrahub exporter: devices by kind and role,
  service objects by kind and status, tenants, and open proposed changes.
- **Cluster health**: nodes, Cilium and Hubble flows.
- **Fabric reachability state**: deployment records showing whether each device is in sync.

**Why this priority**: Grafana with no data is a login page. These dashboards also cost little,
because Infrahub already holds the data.

**Independent Test**: After a fresh bootstrap, each provisioned dashboard loads with non-empty
panels. A change merged in Infrahub, such as a new service object, appears in the organisation
dashboard within a stated interval.

**Acceptance Scenarios**:

1. **Given** a fresh bootstrap, **When** a signed-in user opens the organisation dashboard,
   **Then** every panel shows data and none shows "No data".
2. **Given** a service object is created and merged, **When** the exporter next polls, **Then**
   the count by kind and status moves accordingly.
3. **Given** a device the reconciler reports out of sync, **When** the fabric dashboard is
   viewed, **Then** that device is shown as differing.

---

### User Story 5 - Infrahub drives monitoring: what to watch, and on which devices (Priority: P2)

The telemetry collectors (Telegraf, Prometheus, or whatever suits each device family) take **both
their targets and their instructions** from Infrahub. Infrahub renders each collector's
configuration as an artifact, in the collector's own format, so the collector consumes it
unchanged. Nobody maintains a scrape list, a sensor list, or a dashboard of "expected" values by
hand.

Every device kind is in scope:

- **EOS fabric switches** (`DcimFabricSwitch`)
- **FRR WAN routers** (`DcimDevice`)
- **The Junos firewall** (`SecurityFirewall`)
- **The Kubernetes nodes** (`ComputePhysicalServer`)

Where a device must be told to export telemetry, that configuration comes from the device's own
rendered artifact.

- **Discovery.** The devices to collect from are derived from the graph through the exporter's
  service discovery, carrying their kind, role, rack and pod as labels. A switch added to the
  model is collected. One removed is dropped.
- **What to monitor.** Infrahub records monitoring intent: which measurements apply to which
  devices, typically by role or group. Examples: interface counters on every fabric port, BGP
  session state on spines, leaves and WAN routers, EVPN route counts on leaves, security-policy
  hit counts on the firewall, node resource use on the Kubernetes nodes. Each collector's
  configuration is an artifact rendered from that intent, the same way device configuration is
  rendered from design intent.
- **Expected state.** Infrahub already knows what *should* be true: which BGP sessions exist,
  which links are cabled, which interfaces are enabled. That expectation is exported beside the
  live measurement, so a dashboard shows "intended vs observed" and an established session that
  Infrahub never intended is as visible as a missing one.

**Why this priority**: This is what turns Grafana from a generic monitoring install into the
lab's argument. Intent drives the device configuration, and the same intent drives how the
device is watched. It is P2 rather than P1 for two reasons. The cluster has no collection path to
the device management network today, which is the largest unknown in this feature. And four
device families mean four collection mechanisms.

**Independent Test**: After bootstrap, the collector's targets equal the modelled device set,
with zero hand-listed targets. Its collected measurements equal what the monitoring intent names
for each device. Changing the intent on a branch and merging it changes what is collected, with
no file edited outside Infrahub. The fabric dashboard shows every intended BGP session, and
shutting one turns it red within a stated interval.

**Acceptance Scenarios**:

1. **Given** every device in Infrahub, **When** the collectors discover targets, **Then** exactly
   the modelled devices of each in-scope kind are collected, labelled from the graph. That is the
   seven switches, six FRR routers, the firewall and three Kubernetes nodes.
2. **Given** monitoring intent naming BGP state for spines only, **When** it is changed on a
   branch to include leaves and merged, **Then** the rendered collector configuration and the
   collected series change accordingly. The proposed change shows the rendered difference before
   merge.
3. **Given** a BGP session Infrahub intends, **When** it is down on the device, **Then** the
   dashboard shows it as intended-but-down. **Given** a session Infrahub does not intend,
   **When** it is up, **Then** the dashboard shows it as unintended.
4. **Given** a device that needs telemetry enabled on it (for example, gNMI on cEOS or an SNMP or
   streaming stanza on the vSRX), **When** the reconciler pushes its rendered configuration,
   **Then** telemetry flows. The enabling configuration is in the device's artifact, not applied
   out of band.
5. **Given** a collector's configuration artifact, **When** it is downloaded, **Then** it is a
   complete file in the collector's native format, which the collector runs with no edits.
6. **Given** a device the monitoring intent does not cover, **When** discovery runs,
   **Then** it is not silently collected with a default profile.

---

### User Story 6 - Bootstrap delivers it working, and verification proves it (Priority: P1)

`invoke bootstrap` ends with Grafana up, signed-in-capable, and showing data, with no manual
step. `scripts/verify_bootstrap.sh` asserts this through state, not exit status: dashboards
return data, a Dex sign-in completes, and the application count includes observability.

**Why this priority**: The user stated it explicitly. In this lab, "it worked once" and "it comes
up from nothing" have repeatedly been different claims.

**Independent Test**: `scripts/verify_bootstrap.sh` passes from a destroyed environment. Every
new assertion is shown failing when its condition is broken.

**Acceptance Scenarios**:

1. **Given** `invoke bootstrap --fresh`, **When** it finishes, **Then** Grafana answers on its
   VIP from the branch side once a grant exists. The organisation dashboard has data, a Dex
   sign-in completes for a provisioned user, and every in-scope device reports telemetry.
2. **Given** the existing assertions in `verify_bootstrap.sh`, **When** observability is added,
   **Then** they are updated deliberately rather than loosened: exactly one FabricApp becomes the
   modelled set, and four `K8S_PROD` routes becomes the modelled count.

---

### Edge Cases

- **The redirect URI must be known before the VIP is.** The Dex client is registered by
  `invoke tooling`, which Infrahub cannot deliver. A Grafana VIP allocated at merge time would
  not be known when Dex is configured. The observability block is therefore declared in seed
  data, like `otternet-demo`'s, not allocated.
- **The grant is per source, not per person.** Once alice's request merges, anyone at the branch
  reaches Grafana, and any Dex user can sign in read-only. This is accepted for this cycle. The
  demo shows a request opening a path, not per-user authorization.
- **Two pinned renderers.** `junos_config` is held byte-for-byte against the device file, and
  `frr_config` against `../lab/wan/rendered/*/frr.conf`. Telemetry-enabling configuration moves
  both pins. The pins must be updated deliberately, together with the files they are pinned
  against, not loosened.
- **The reconciler's normalisation allowlist.** New telemetry lines that a device does not echo
  back would read as a permanent difference and cause a push on every cycle. Each new line must
  be covered by a normalisation rule, with captured device output proving it.
- **Junos `load replace` touches only tagged hierarchies.** A new telemetry hierarchy that is not
  tagged `replace:` is merged, not replaced, so removing it from the model would never remove it
  from the device.
- **An empty collector artifact.** An unrendered artifact exists, reports `Ready` and is empty. A
  collector loading it would collect nothing and report healthy. The collector must refuse an
  empty or unparseable configuration and keep its previous one.
- **Collection credentials.** SNMP communities, gNMI usernames and similar values are
  credentials. They are injected from Secrets and never rendered into an artifact.
- **Exporter credentials.** The exporter reads Infrahub with a token. That token must be
  read-only and must not belong to `admin` or to the task-worker `agent` super administrator,
  for the same reason `mcp-agent` exists.
- **Exporter port.** The exporter's documented default port (8001) is the port `infrahub-mcp`
  already uses.
- **Loss of the Infrahub API.** The organisation dashboard should show stale data or gaps, not
  crash Grafana or block sign-in.
- **The stale branch bookmark.** The bookmark lives in the lab repository and points at
  `10.112.240.16`. It must be updated to the modelled VIP, or demo act one opens the wrong
  application.

## Requirements *(mandatory)*

### Functional Requirements

#### Nodes & Generics

- **FR-001**: Observability MUST be expressed as a `ServiceFabricApp` instance, not a new
  application kind. An application is a Helm chart (cycle 033), and Grafana and Prometheus are
  charts.
- **FR-002**: The schema MUST model monitoring intent: a node, in an approved namespace, that
  names a set of measurements and the devices it applies to (by device group or role, not by
  listing devices). One device MAY match several intents, and their measurements combine. It
  MUST be able to address all four device kinds.
- **FR-003**: All node and namespace names MUST follow the project conventions
  (`^[A-Z][a-zA-Z0-9]+$` and `^[A-Z][a-z0-9]+$`).

#### Attributes

- **FR-010**: A `ServiceFabricApp` MUST be able to declare that it authenticates people through
  the lab identity provider. The renderer MUST NOT infer this from the chart name.
- **FR-012**: No attribute MAY hold a credential: not the Dex client secret, not the Grafana
  admin password, not the exporter token, not an SNMP community or a gNMI password. The graph and the artifact carry references to secrets
  that bootstrap creates, mirroring how `vidra/` records only the shape of the credential Secret.
  *Exception recorded in the plan*: the firewall's read-only SNMPv2c community, which the device
  must receive in its configuration.
- **FR-013**: New attributes on existing kinds MUST be optional or defaulted, so existing
  `ServiceFabricApp` objects, including portal-created ones absent from `objects/`, load without
  a migration.

- **FR-014**: A monitoring intent MUST carry a collection interval and a set of measurements
  drawn from a Dropdown of measurements the collector can render (for example interface counters,
  BGP session state, EVPN route counts, security-policy hit counts, system CPU and memory).
  Free-text sensor paths MUST NOT be the interface a requester uses. A measurement that does not
  apply to a matched device's family MUST be skipped for that device, and the skip reported, not
  rendered.

#### Relationships

- **FR-020**: The observability application MUST reference the existing `otternet` cluster, the
  `K8S_PROD` VRF, and a VIP block recorded as an `IpamPrefix` inside the cluster's `vip_pools`.
- **FR-021**: The observability application MUST name its advertised services through
  `advertised_services`, so a grant's firewall rule permits the port the VIP answers on.
- **FR-021a**: A monitoring intent MUST relate to the device groups it applies to, peering
  `CoreStandardGroup` (or `DcimGenericDevice` membership), so that every device kind can be
  reached. A relationship to `DcimDevice` alone would miss the fabric switches.
- **FR-022**: All relationship peers MUST use full kinds. Any new bidirectional relationship MUST
  carry matching `identifier`s.

#### Display & Identification

- **FR-040**: Any new node MUST define `human_friendly_id` and `display_label`. If its HFID would
  have more than one element, the spec records that Backstage's generated templates cannot pick
  it, as with `IpamPrefix`.

#### Delivery & Behaviour (consequences of the schema, specified here so the model is shaped for them)

- **FR-050**: The `crossplane_fabric_app` artifact for an application that authenticates through
  Dex MUST render the identity-provider settings. Every Dex user who signs in MUST receive the
  read-only role, and no one MAY receive an administrative role through sign-in.
- **FR-051**: Alice's request MUST be the existing `ServiceAppAccess` grant on the observability
  application, with no new fields. The generator, triggers, withdrawal semantics and curated
  portal template apply unchanged.
- **FR-053**: `invoke tooling` MUST register Grafana as a Dex client whose redirect URI is the
  observability application's modelled VIP.
- **FR-054**: The paths Grafana needs to Dex (for the token exchange) and Prometheus needs to
  the Infrahub API MUST NOT be opened by hand. *Amended by plan research R3*: both use the
  cluster's existing management-network egress, which Vidra already uses to reach Infrahub.
  Neither crosses fw1, so there is no firewall intent to model. The application's own pod
  policy, which is modelled, is what permits them.
- **FR-055**: Organisation metrics MUST come from the Infrahub exporter, reading with a
  dedicated read-only account. `invoke bootstrap` MUST start it with no manual step.
- **FR-056**: `invoke bootstrap` MUST deliver the observability application with no manual step.
  `scripts/verify_bootstrap.sh` MUST assert that it is running, that a dashboard query returns
  data, and that a Dex sign-in completes. The handover tests and assertions MUST be updated to
  account for it.
- **FR-057**: `docs/docs/demo-runbook.md` MUST gain an act in which alice requests Grafana, the
  proposed change is read, the change merges, and alice signs in. It MUST also cover the grant
  being revoked.
- **FR-058**: No grant for Grafana MAY be seeded. `test_no_grant_is_seeded` continues to hold,
  so alice starts with nothing.

- **FR-059**: Collector targets MUST come from Infrahub (exporter service discovery or a rendered
  artifact). Collector instructions MUST be rendered from monitoring intent as an artifact in the
  collector's native format, such as a Telegraf configuration, registered in `.infrahub.yml` like
  every other artifact. A change to what is monitored is then reviewed in a proposed change like
  any other intent. No target or sensor list MAY be hand-maintained.
- **FR-059c**: Collector configuration artifacts MUST reach the collector with no manual step,
  and a change MUST be picked up without redeploying anything by hand. Planning chooses between
  Vidra delivering them and the collector fetching them from Infrahub.
- **FR-059d**: Telemetry-enabling device configuration MUST come from each family's existing
  renderer: AVD hostvars for EOS, `frr_config`, `junos_config`, and whatever configures the
  Kubernetes nodes. It is then pushed by the existing reconciler.
- **FR-059a**: Intended state (intended BGP sessions, cabled links, enabled interfaces) MUST be
  exported as metrics alongside observed state, so dashboards compare the two rather than display
  either alone.
- **FR-059b**: Monitoring intent and its artifacts MUST NOT become a generator trigger source, and
  neither may collected telemetry. The rule `DeploymentState` follows applies here for the same
  reason: an observation that triggers regeneration closes a loop.

#### Migration

- **FR-060**: The change MUST be additive to the schema. Nothing is marked `state: absent`.
- **FR-061**: The lab's `otternet-observability` claim stays in `LAB_ONLY_APPS` and is still
  deleted by the handover. The Infrahub-owned application MUST use a different name, so Vidra
  never meets a resource another writer created.

### Key Entities

- **ServiceFabricApp (observability instance)**: The Grafana and Prometheus workload. It is a
  chart, a version and values, in cluster `otternet` and VRF `K8S_PROD`, with a seeded VIP block
  and its advertised HTTP service. It newly declares that it signs people in through Dex.
- **ServiceAppAccess (unchanged)**: The grant alice requests. It opens the route, the firewall and
  the pod policy from the branch to Grafana's VIP.
- **Monitoring intent (new)**: A statement that a set of devices, chosen by group or role, is
  watched for a set of measurements at an interval. It is the input to the collector's rendered
  configuration, just as design intent is the input to a device's.
- **Collector configuration (artifact)**: Rendered from monitoring intent in the collector's
  native format (for example, a Telegraf configuration) and delivered to the collector. A change
  to it is visible in a proposed change before merge.
- **Dex client (outside Infrahub)**: Grafana's registration with the one issuer, created by
  `invoke tooling`. It is referenced by the model but never stored in it.
- **Infrahub exporter (outside the graph)**: Turns the graph into metrics and Prometheus targets.
  It reads with its own least-privilege account.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `infrahubctl schema check schemas/` passes with zero validation errors, and every
  existing object loads unchanged.
- **SC-002**: From a destroyed environment, one `invoke bootstrap --fresh` produces a running
  Grafana with provisioned dashboards and no manual step. `verify_bootstrap.sh` passes.
- **SC-003**: In the demo, the time from alice submitting her request to her signing in to
  Grafana, including review and merge, is under 5 minutes, of which the automation's share is
  under 2 minutes.
- **SC-004**: Before her grant, alice cannot reach Grafana. After it, she reaches it and signs in
  through Dex. Both outcomes are observed from the branch desktop, not inferred.
- **SC-005**: 100% of panels on the organisation dashboard show data after bootstrap. A merged
  change appears in it within 2 minutes.
- **SC-006**: Withdrawing alice's grant removes branch reachability within one reconcile and
  delivery interval, and leaves every other grant's access intact.
- **SC-007**: No credential appears in any schema attribute, seed object, rendered artifact or
  committed file.
- **SC-008**: Every device of all four kinds reports telemetry, with zero hand-listed targets and zero
  hand-written sensor lists. The collected set equals the set the monitoring intent names.
- **SC-009**: A monitoring-intent change merged in Infrahub changes what is collected within 5
  minutes, with no edit outside Infrahub.
- **SC-010**: Every BGP session Infrahub intends appears on the fabric dashboard with its observed
  state. A deliberately downed session is shown as down within 1 minute.

## Assumptions

- Grafana and Prometheus are delivered together as one application, a kube-prometheus-stack chart
  or equivalent, mirroring the lab's own values where they already solved a problem (node
  placement, memory limit, readiness probe).
- The VIP block is declared in seed data, not allocated, because Dex must know the redirect URI
  before Infrahub merges anything. It is chosen inside `10.112.240.0/24`, clear of `.0/28` and of
  any block the portal has handed out.
- Collectors run in the cluster beside Prometheus unless planning finds the device management
  network unreachable from there. In that case they run where the devices are already reachable,
  still configured only from Infrahub artifacts.
- Telegraf is the default collector because it covers gNMI, SNMP and Prometheus inputs in one
  configuration format. Planning may choose per family.
- Grafana and Prometheus reach the Infrahub API the way Vidra already does, from the cluster to
  the host at `172.20.41.1:8000`.
- Grafana runs over plain HTTP on its VIP. Unlike Backstage, its frontend does not need a secure
  context. Revisit this if a browser feature forces it.
- The exporter runs beside Infrahub in the compose stack, as `infrahub-mcp` does, on a port other
  than 8001. If planning finds a published image or chart, running it in the cluster is
  acceptable.
- The Grafana break-glass admin account exists for operators, and its password is generated into
  a Secret by bootstrap. People never use it.

## Dependencies & Downstream Impact

- **`tooling/10-dex.yaml`**: a new static client. `invoke tooling` must run after the
  observability VIP is fixed, which it is, because the VIP is seeded.
- **`transforms/crossplane_fabric_app.py`**: renders identity settings. Its
  byte-for-byte expectations for `otternet-demo` must not move.
- **`generators/generate_app_access.py` and `backstage/`**: unchanged. The existing grant and its
  templates are the request path.
- **`tasks.py`**: handover lists, the bootstrap order (exporter account and Secrets), and
  `scripts/verify_bootstrap.sh`.
- **The lab repository**: the branch desktop's Grafana bookmark must point at the modelled VIP.
- **New transforms and artifact definitions** render each collector's configuration from
  monitoring intent.
- **Device renderers**: AVD hostvars gain the telemetry-enabling settings, which must be accepted
  by the pinned PyAVD. `frr_config` and `junos_config` gain telemetry stanzas, which moves their
  byte-for-byte pins and the lab repository files they are pinned against.
- **`src/solution_arista_avd/deployment/normalise.py`**: covers any telemetry line a device does
  not echo back.
- **Collection reachability**: the cluster has no route to the device management network
  today. Planning must choose between routing the cluster there and running the collector where
  the devices are already reachable.
- **`docs/`**: the demo runbook, the vidra-delivery page, and supported capabilities.

## Out of Scope

- Alerting, Alertmanager routing and notifications. Monitoring intent could later carry alert
  thresholds, but this cycle does not render alert rules.
- Long-term metric retention or remote write.
- Per-user authorization of any kind. There are no per-person Grafana roles, teams or folder
  permissions, and the firewall permits a source, not a person. Every Dex user who reaches
  Grafana gets the same read-only role.
- A Dex groups claim. That would require replacing the static-password connector.
- Re-platforming the WAN routers from FRR to SR Linux. It is feasible, since SR Linux has
  inter-instance route leaking and a free image (26.7.2), but it rewrites `frr_config`, its pins
  and the reconciler's FRR family. It is the named follow-up, cycle 035. The monitoring design
  carries over unchanged: the routers' measurements move from `inputs.prometheus` to
  `inputs.gnmi`, and the `frr_exporter` sidecars are removed.

# Arista AVD Reference Design

## Project context

This repository is the Arista AVD Reference Design for Infrahub. It models datacenter
fabric intent, topology, addressing pools, EVPN services, and per-device AVD data in
Infrahub, then renders EOS configurations and documentation through PyAVD.

Key docs to read before larger changes:

- `README.md` and `docs/docs/home.md` for the current product overview.
- `docs/docs/quick-start.md` for stack/load commands.
- `docs/docs/supported-capabilities.md` before assuming a feature is supported.
- `docs/docs/developer-guide/architecture.md` for the data model and generator chain.
- `docs/docs/developer-guide/schemas.md` for schema kinds and dropdown values.
- `docs/docs/developer-guide/generators.md` for generator structure and execution order.
- `docs/docs/developer-guide/transforms.md` for transform structure and artifacts.
- `docs/docs/developer-guide/avd/overview.md` for the two-phase AVD pipeline.
- `docs/docs/developer-guide/avd/extending.md` for extension workflows.
- `docs/docs/developer-guide/avd/debugging.md` for pipeline debugging.

## Repository layout

- `src/solution_arista_avd/` - core Python library: AVD helpers, cabling,
  addressing, sorting, generator utilities, and generated protocols.
- `generators/` - Infrahub generators and their GraphQL queries / generated
  query models.
- `transforms/` - Python transforms, GraphQL queries, generated query models,
  and templates.
- `checks/` - proposed-change checks (CloudVision validation and its workspace
  lifecycle helpers).
- `ansible/` - playbooks Semaphore runs, including ContainerLab deployment.
- `schemas/` - Infrahub schema definitions, split between base schemas and
  project/feature extensions.
- `objects/` - seed data loaded in filename order. This repository models one
  fabric, `NFD41_FABRIC`, which is the containerlab lab in the NFD41 lab repo;
  the upstream reference design's example fabrics were removed.
- `menus/` - Infrahub UI menu definitions.
- `docs/` - Docusaurus documentation.
- `lab/` - ContainerLab artifact/deployment helpers.
- `queries/` - GraphQL queries with no Python consumer in this repository. Currently
  one: `artifact_ids.gql`, polled by the Vidra operator.
- `vidra/` - deployment assets for the Vidra operator, which applies the Crossplane
  artifacts into the lab's Kubernetes cluster on merge. Helm values, the operator
  ConfigMap, the two `InfrahubSync` declarations, and the **shape** of the credential
  Secret - never the credential itself.
- `.infrahub.yml` - menus, queries, generators, transforms, and artifact
  definitions.
- `repository.yml` - CoreRepository definition.
- `tasks.py` - Invoke task definitions.

## Architecture summary

- Data model hierarchy: `NetworkFabric` -> `NetworkPod` -> `LocationRack` ->
  `DcimFabricSwitch` -> `DcimInterface` / `NetworkLink` / `IpamIPAddress`.
- **Four device kinds exist, and they are siblings.** `DcimFabricSwitch` is
  the fabric's EOS switches, `DcimDevice` the WAN's FRR routers,
  `SecurityFirewall` the perimeter firewall, `ComputePhysicalServer` the hosts
  and Kubernetes nodes. All four inherit `DcimGenericDevice`; none inherits
  another, because Infrahub inheritance targets generics and these are nodes.
  **A query naming `DcimDevice` does not see a fabric switch and reports
  nothing** — peer or spread `DcimGenericDevice` to reach every kind.
- The fabric generator chain is `generate-fabric` -> `generate-pod` ->
  `generate-rack` -> `generate-avd-device-hostvar` ->
  `generate-avd-device-structured-config`.
- Hostvars are stored as `AvdHostvarFile` nodes under `AvdArtifact`; structured
  configs are stored as `AvdStructuredConfigFile` nodes under the same artifact.
- AVD transforms render artifacts from the stored files: EOS config, device docs,
  fabric docs, cabling plan, ANTA catalog, and computed interface descriptions.
- PyAVD is version-sensitive; the project targets `pyavd>=6.4.0,<6.5.0`.
- The service portal is a Streamlit app for day-2 workflows; every workflow should
  operate on an Infrahub branch and produce a proposed change for review.

## Generator and transform inventory

The service layer offers seven kinds, each described where its generator or renderer is.
`ServiceNetworkSegment` is the newest: a segment is the three technical objects that always
appear together and are always consistent — an `IpamPrefix`, an `IpamVLAN`, and an `EvpnSvi`
giving it a gateway in a VRF. **It allocates rather than selects**, which is what separates it
from the WAN kinds: leaving `vlan_id` or the subnet empty is the normal case, and
`generate-network-segment` takes the next free one from `NFD41-Segment-VLAN-Pool` and
`NFD41-Segment-Subnet-Pool`.

`service_catalog/pages/1_Create_Segment.py` is the request path. It creates a single
`ServiceNetworkSegment` on a branch and opens a proposed change; the generator builds the three
technical objects on merge. It previously wrote `IpamVLAN`, `IpamVRF` and `EvpnSvi` itself — no
requester, no status, nothing to withdraw, and **no `avd_tags`, so every SVI it created rendered
on no switch**. The form now asks for a size and a set of tags, labelled with the racks each tag
selects, and refuses an empty tag list rather than defaulting it.

**Resource pools are branch-agnostic and their resources are not**, which is worth knowing before
testing one on a branch. `CoreIPPrefixPool` and `CoreNumberPool` carry `branch: agnostic`, so a pool
created on a branch is live on `main` the moment it exists and deleting that branch does not remove
it. The `IpamPrefix` it draws from is branch-aware and *does* go with the branch — leaving a pool
that exists globally, has empty `resources`, and can never allocate. Two further traps sit behind it:

- A pool needs `default_prefix_type: IpamPrefix`. Omitting it costs nothing at load time and fails at
  allocation with `A prefix_type or a default_value type must be provided`, naming the pool but not
  the file that declares it.
- The caller passes the role: `allocate_next_ip_prefix(..., data={"role": "tenant_host"})`, because
  `IpamPrefix.role` is mandatory here and depends on what the prefix is for rather than on the pool.

What is **not** a trap, having been measured: an allocation made on a branch is branch-aware and
invisible on `main`, so a proposed change that is opened and then rejected does not burn a subnet.

Current generator definitions are registered in `.infrahub.yml`:
`generate-fabric`, `generate-pod`, `generate-rack`, `generate-server-cabling`,
`generate-avd-device-hostvar`, `generate-avd-device-structured-config`,
`backfill-structured-config`, `generate-fabric-peering`, `generate-app-access`, and
`generate-network-segment`.

`generate-fabric-app` gives an exposed `ServiceFabricApp` a LoadBalancer VIP block from its
cluster's pool. It closes a harder edge than the other allocating generator, because an exposed
application with no block does not degrade — `crossplane_fabric_app.py` **raises**
`is exposed but has no vip_block; the XRD requires expose.vipBlock`. Two things to know:

- **`vip_block_managed` is what makes withdrawal safe.** `vip_block` holds either a block a
  human declared in `objects/` — `10.112.240.0/28` for `nfd41-demo` — or one this generator took
  from the pool, and only the second is ever safe to delete. The flag records which, is set only
  on the allocating path, and is the only thing withdrawal consults; it plays exactly the role
  `managed_by_service` plays on `SecurityPolicyRule`. It is written in the **same save** as the
  block, because two saves leave a window in which the block exists and nothing records who owns
  it. A block that already exists is kept whoever created it, which is how the seeded
  application's manifest stays byte-identical.
- **The pool is resolved through the CLUSTER**, not by name and not by role. A cluster's
  `vip_pools` are the only supernets the leaves' inbound route policy permits
  (`10.112.240.0/24 le 32`), so a block from anywhere else is advertised by the cluster and
  refused by the fabric.

`generate-network-segment` and `generate-fabric-app` are the two generators that **allocate
rather than select**: every other one here derives from objects that already exist, while these
take the next free resource from a pool. Two things to know before changing the segment one:

- **`ServiceNetworkSegment.avd_tags` is what decides whether the segment renders at all.** AVD
  puts an SVI on a device only where `svis[].tags` intersects that device's node-group
  `filter.tags`, and in this fabric those filters are the racks' own `AvdTag`s — `k8s`, `app`,
  `cloud`, `border`. `EvpnSvi.rack_tags` exists, looks like the scoping relationship, and
  contributes the rack's *name*, `K8S_LEAFS`, which matches no filter. Measured: an untagged SVI
  rendered on zero switches; tagged `k8s` the same SVI rendered on exactly the two K8S leaves.
  Nothing errors on that path, so the relationship is mandatory and the generator checks it again.
- **Its pools are resolved by role rather than by name** — the prefix pool whose resources carry
  `tenant_host`, and the number pool allocating `IpamVLAN.vlan_id` — and both demand exactly one
  candidate. A hard-coded `NFD41-Segment-Subnet-Pool` would fail naming a string that appears in
  no schema.

**`status` is honoured by one generator and inert everywhere else, and that is a gap rather
than a design.** `ServiceGeneric.status` offers `decommissioning` and `decommissioned` on every
service kind, but only `generate-network-segment` branches on them. Setting a
`ServiceFabricPeering`, `ServiceFabricApp`, `ServiceL3vpn`, `ServiceTenantCloud` or
`ServiceInternetAccess` to `decommissioned` changes nothing: the sessions stay, the Crossplane
resource is still delivered, and the provider edge still imports the tenant's prefixes.
`crossplane_fabric_peering.gql` even selects the field and its transform never reads it.

Closing it means teaching each renderer to withdraw, and the WAN renderers are pinned
byte-for-byte against `../lab/wan/rendered/*/frr.conf` — so it is a deliberate decision about
what the service layer promises, not a tidy-up. Until it is made, treat `status` on those kinds
as a label, and do not assume the segment generator's behaviour generalises.

`generate-app-access` sits underneath `ServiceAppAccess` and turns an **approved** grant into
the firewall objects permitting the session: an address-book entry for the destination VIP, a
`SecurityService` per permitted port, and the `SecurityPolicyRule` joining them, linked back
through `granted_rules`. Generated objects render into the existing Junos artifact, because
`junos_config.gql` queries `SecurityGenericAddress` and `SecurityPolicy` unfiltered. Six things
to know before changing it:

- **It asks for the firewall's artifact to be re-rendered, and must.** An artifact regenerates
  when its *target* changes, and the target is `fw1` — a new `SecurityPolicyRule` is not a
  change to the firewall. Without the explicit request the objects appear, the artifact keeps
  its old checksum, and the reconciler compares the device against stale output and reports no
  difference. Infrahub's trigger rules cannot close this: `CoreGeneratorAction` and
  `CoreGroupAction` are the only actions and neither renders an artifact.
- **A generated service object needs `junos_config` to declare it.** Every service in the
  hand-written baseline is a Junos built-in (`junos-http`, `junos-https`, `junos-ping`), so for
  three cycles the renderer referenced applications and declared none. A policy naming an
  undeclared application is refused with `commit failed: (statements constraint check failed)`,
  which names no object and points at no line. `_applications` now emits the stanza for any
  service without the `junos-` prefix, and renders nothing when they are all built-ins — which
  is what keeps the artifact byte-identical to the device file.
- **An unapproved grant is a deliberate no-op, and that is the seeded state.** `approved` is
  the gate, so `objects/38_nfd41_access_grants.yml` generates nothing and the rendered Junos
  artifact stays byte-identical to what `tests/unit/test_junos_config.py` holds against
  `junos.conf`. Approving it in the seed data would add a rule the device file has no
  counterpart for, so there would be nothing true to update those assertions to —
  `test_the_seeded_grant_is_unapproved` fails when someone tries. The cost is that "ran
  successfully and created nothing" is the normal outcome, which reads exactly like a broken
  generator. Check `approved` before debugging anything else.
- **Two allocation floors, and both are load bearing.** Rule `index` starts at 100 because
  Junos is first-match within a zone pair and the baseline puts `deny-spoofed-infra` at index
  10 — a generated permit below it would turn every grant into a bypass for a spoofed
  `fabric-infra` source. Address `book_index` starts at 1000 because hand-written entries
  occupy 10–130 and their order is pinned; an entry with **no** `book_index` is skipped by
  `junos_config.py::_addresses` entirely, so it would be referenced by a rule and never
  declared, and the configuration would not load.
- **The destination zone comes from the VRF, not from interface containment.**
  `ServiceFabricApp.vrf` and `SecurityZone.vrf` both peer `IpamVRF`. Deriving it from "the
  firewall interface whose subnet contains the VIP" cannot work — the handoff interfaces are
  `/30` point-to-points and contain no service VIP, so containment matches nothing.
- **Adoption fetches and modifies; it never upserts.** The firewall already declares
  `junos-http` and `junos-https`, so a grant for 443 references the existing object rather than
  declaring a second application for the same port. An adopted object is never marked
  `managed_by_service` and so is never deleted by the tracking context when the grant is
  revoked — which is what keeps `junos-https` alive for the baseline rules that share it.

Current Python transforms are: `computed_interface_description`, `cabling_plan`,
`avd_eos_config`, `avd_fabric_doc`, `avd_device_doc`, `avd_anta_catalog`,
`containerlab_topology`, `cv_workspace_submission_webhook_payload`, `crossplane_fabric_peering`,
`crossplane_fabric_app`, `frr_config`, and `junos_config`.

`frr_config` renders the WAN's FRR configuration — the two ISP provider-edge routers, the
internet router, the two customer edges and the branch router — as one `text/plain` artifact per
device, targeting the `frr_routers` group. It is the half of the lab PyAVD does not cover, and
it is held byte-for-byte against `../lab/wan/rendered/*/frr.conf` by
`tests/unit/test_frr_config.py`. Two things to know before changing it:

- It reads the **service** layer as well as the technical one. A provider edge's per-tenant
  import route-map is assembled from `ServiceL3vpn.dc_service_prefixes`,
  `ServiceTenantCloud.prefix` and whether a `ServiceInternetAccess` exists. That is the
  documented exception to "renderers read technical objects" — the provider edge's policy *is*
  the service intent.
- Its templates are ported from `../lab/wan/templates/` with exactly one line changed, the
  provenance header. Every comment is deliberate; they are most of the teaching value of those
  configs.

`junos_config` renders the perimeter firewall's Junos configuration as one `text/plain` artifact
targeting the `junos_firewalls` group. Three things to know:

- **It covers 592 of `junos.conf`'s 677 lines, and the 85 it does not are two different things.**
  The `system` stanza (13 lines) is *configuration deliberately never modelled*: two credential
  hashes that must never enter the model, and the query must never ask. The file header (72 lines)
  is *not configuration at all* — 68 comments and 4 blanks of lab documentation about the file,
  including how vrnetlab appends it to `init.conf`; the artifact replaces it with its own
  provenance line, because reproducing it would make a false claim about where the file came from.
  Grouping the two as "excluded lines" hides that difference, which is why they are named
  separately here and asserted separately in `test_the_exclusions_add_up`.

  Everything else matches the device byte for byte, **with one exception the model cannot close**:
  the *sequence* of the eleven zone-pair blocks. A zone pair is derived from each rule's source and
  destination zone, so no pair object exists to carry an order, and `SecurityPolicyRule.index`
  orders rules *within* a pair — it holds only 10, 20 and 30 across all nineteen. Junos matches a
  packet to its pair by zone, not by position, so the sequence is presentation. Every pair is
  present and each is byte-for-byte identical.

  The eight static routes are held against three sources by
  `tests/unit/test_fw_static_route_objects.py`, and the third is the interesting one: every next
  hop must lie on a subnet `fw1` has an interface on. A comparison against `junos.conf` cannot
  catch a typo *in* `junos.conf`, so the interface addresses are an independent witness.
  `test_the_exclusions_add_up` makes the total an assertion rather than a caveat, so it is the
  thing to update when those twelve lines move in scope.
- **Order is checked where it is behaviour and relaxed where it is not.** Junos evaluates
  first-match within a zone pair, so rule order is semantic and pinned; the sequence *between*
  pairs is presentational and asserted as a set. The address book's order *is* pinned, through
  `book_index` — added locally because Junos writes it in authoring order and nothing derives it.
- **Two attributes are local additions** in `schemas/security_extensions.yml`: `book_index` on
  `SecurityGenericAddress` and `log_session_close` on `SecurityPolicyRule`. Upstream models `log`
  as a Boolean; the device distinguishes `session-init` from `session-init` plus `session-close`.

Check definitions are `cv-config-validation` (`checks/cv_config_check.py`), with its
workspace lifecycle and helpers in `checks/cv_workspace_lifecycle.py` and
`checks/cv_helpers.py`; `fabric-pool-validation` (`checks/fabric_pool_check.py`); and
`peering-consistency` (`checks/peering_consistency_check.py`); `zone-advertisement`
(`checks/zone_advertisement_check.py`); and `wan-service-consistency`
(`checks/wan_service_check.py`). The first two are targeted on `fabrics`; the last three
are **global** — they have no `targets`, because their rules are statements about the whole
graph rather than about one fabric.

`wan-service-consistency` guards the lab's central claim. The WAN service kinds **name**
technical objects rather than creating them — which is why no generator sits beneath them, and
also why every one of their references was unverified. `schemas/service/wan_services.yml` says
the isolation is *structural*: no VRF imports another's route targets anywhere, so there is no
east-west path to filter in the first place. That is only true while the services are wired
correctly, and nothing checked that they were. Four rules:

- **A circuit belonging to another tenant.** `ServiceL3vpn.circuits` is not a label, it is the
  routing domain — two of a tenant's sites reach each other because both circuits are in the
  list. A foreign one joins two tenants directly across the provider edge, which is what cycle
  019's FR-005 warns about.
- **Two L3VPNs sharing a provider-edge VRF**, which is the same collapse by another route.
- **A tenant cloud whose zone governs a different VRF.** `generate-app-access` derives a grant's
  destination zone by matching the application's VRF against `SecurityZone.vrf`, so a mismatch
  silently writes grants into a policy for somewhere else.
- **Two clouds sharing a VRF or a zone** — the one that most looks like tidy reuse.

**It judges decommissioned services too**, deliberately. Everywhere except
`generate-network-segment`, `status` is inert, so a decommissioned `ServiceL3vpn` still
assembles the provider edge's import policy; skipping it would excuse a live misconfiguration
because of a label.

A thing worth knowing before extending it: **`IpamVRF.tenant` cannot identify a tenant here.**
Every tenant VRF in this lab points at the `EvpnTenant` named `TENANT_CLOUD`, not at the
`OrganizationTenant` — so VRFs are compared by identity and never attributed to an owner.
`DcimCircuit.tenant` *does* resolve to the organization tenant, which is what makes the first
rule possible at all.

`zone-advertisement` discharges the condition cycle 032 attached to its own design. A zone
names its prefix list rather than relating to one, because no `RoutingPrefixList` object
exists — the fabric's whole BGP policy lives inside `avd_custom_hostvars` — and that was only
defensible if a wrong name were detectable. It reports four things: a zone naming a list the
fabric does not declare, a zone carrying one half of the policy, an approved grant whose VIP
falls outside its application's `vip_block`, and an approved grant on an application that is
not exposed.

**It counts fabric scope only, and that is the whole subtlety.** `generate-app-access` creates
the named list at device scope whenever it advertises, so once a grant has run the device
declares the very name the rule questions. Reading device scope made the reference
self-fulfilling: a branch naming a nonexistent list failed the check before a grant ran and
passed it afterwards.

## Repository sync, and the one thing that wedges it

Infrahub clones the repository over git and imports what it finds: queries, generators,
transforms, checks, artifact definitions, and menus. Two behaviours are worth knowing before
debugging a change that never arrives.

**A failed import is not retried until the commit changes.** Infrahub compares the commit it
has against the repository's HEAD, and an unchanged hash means there is nothing to do — even
when the last import failed halfway. The repository sits at `sync_status: error-import`
indefinitely and polling does not help. Recovery is a new commit, not patience.

**A partial import leaves the graph inconsistent and reports nothing.** One observed run
registered the new `CoreGraphQLQuery` and not the `CoreGeneratorDefinition` beside it, because
the import failed on an unrelated menu upsert after the queries and before the generators. That makes
"the query is there, the generator is not" a symptom of a failed import rather than of a
malformed definition. Check `sync_status` on the `CoreRepository` first:

```bash
# sync_status should be `in-sync`; `error-import` means the last import failed
uv run infrahubctl repository list
docker compose logs task-worker --since 10m | grep -i "Failed to synchronize"
```

The failure seen here was a race between the two `task-worker` replicas importing the same
repository, surfacing as `Multiple CoreMenuItem nodes have the same hfid` on a menu item whose
HFID is not in fact duplicated.

## Deployment state, and the one rule about it

`DeploymentState` and `DeploymentDiffFile` (`schemas/deployment.yml`) record whether each
device matches the configuration Infrahub renders for it. **Nothing may generate from them:
no generator input, no artifact target, no trigger source.** Writing state onto a device
emits an event, `triggers.yml` turns node events into generator runs, a generator run
regenerates artifacts, and a moved artifact is what the reconciler acts on — so a trigger on
a deployment kind closes a loop that currently stays open only because nothing happens to
watch these kinds. `tests/unit/test_deployment_schema_contract.py` fails, naming the rule,
when someone adds one.

Three properties of that file are deliberate and each looks like an oversight:

- **No `on_delete`.** Its only value, `cascade`, deletes the *peer* when the node is deleted,
  so on `DeploymentState.device` it would mean deleting a deployment record deletes the
  switch. `infrahubctl schema check` accepts the line without complaint.
- **`device` is optional, and identity lives on a copied `name` attribute instead.** An
  `human_friendly_id` or uniqueness constraint over a relationship requires that relationship
  to be mandatory, and a mandatory `device` makes any device that has ever held a record
  permanently undeletable — Infrahub keeps refusing the delete *after* the record is gone,
  naming a record that no longer exists. The reconciler owns `name`, refreshing it from the
  device, and sweeps records whose device no longer resolves.
- **Both kinds are `branch: agnostic`.** Deployment state is a fact about the physical world,
  not about a branch: modelled branch-aware, a branch cut on Monday and merged on Friday
  would carry Monday's deployment state into `main`, and every proposed change would display
  deployment records as proposed intent.

## The deployment reconciler

`src/solution_arista_avd/deployment/` compares every device against its rendered artifact on a
timer and pushes the ones that differ — the loop half of what `invoke provision` does by hand.
It is behind a compose profile (`--profile reconcile`) so nothing starts it by accident, and
`invoke provision` is unchanged: cycle 030 **lifted** the push path out of
`scripts/provision_lab.py` into `deployment/devices.py` so both callers share one copy rather
than two that drift.

**Run `invoke build` before starting the profile if dependencies have moved.** The service runs
`python scripts/reconcile.py` with the *image's* interpreter, so it needs the project's runtime
dependencies baked in. An image built predating `nornir-infrahub` crash-loops on
`ModuleNotFoundError: No module named 'infrahub_sdk'` — the SDK arrives transitively through
`nornir-infrahub`, and the host virtualenv bind-mounted at `/source` cannot stand in for it:
the image is Python 3.13 and that virtualenv is 3.12.

The device layer is **Nornir** (`deployment/inventory.py`), with the inventory built from
Infrahub by `nornir-infrahub`: hosts are `DcimGenericDevice` so all four device kinds appear,
and groups come from each node's `member_of_groups`, which `objects/00_groups.yml` already
seeds. **No `schema_mappings` is configured, deliberately** — `mgmt_ip` is a relationship on
`DcimFabricSwitch` alone, so a mapping for it against the generic is rejected outright; the
address each device is reached by comes from `Target` instead.

**Where the thread boundary sits is the design.** Nornir runs hosts in a `ThreadPoolExecutor`
while the SDK's client context is a contextvar bound to the async task, so a Nornir task does
device I/O only and returns plain data; every Infrahub write happens afterwards in the caller's
coroutine. `test_the_nornir_layer_never_touches_infrahub` asserts that by walking the module's
imports rather than trusting the comment. The firewall is never parallelised — its comparison
takes an exclusive lock, so it runs alone after the fabric.

**Read `deployment/normalise.py` before changing anything in this package.** Two of the three
device families report a difference against an artifact the device already matches:

- **FRR** reports `neighbor <addr> activate`, `service integrated-vtysh-config` and `line vty`
  every time — the artifact states them and `show running-config` never echoes them back.
- **Junos** reports changed lines every time: zone-pair ordering and comment round-tripping.

Read raw, that means "differs," and the reconciler would replace the configuration of every FRR
router and the firewall on every cycle forever while logging success. `differs` is therefore computed
from normalised output, never raw text, and the rules are an **allowlist** — anything
unrecognised counts as a difference, so a gap causes an unnecessary push rather than a missed
one. `tests/unit/test_deployment_normalise.py` holds real captured device output for both the
in-sync and the changed case; an empty result is only evidence when a non-empty one is proven
beside it.

Three things worth knowing before debugging it:

- **`fxp0` is modelled, and that is what makes `load replace` on `interfaces` safe.** The
  hierarchy is replaced wholesale, so it deletes everything the artifact omits -- which is how
  removing an interface from the model removes it from the device. While the model owned only
  the data interfaces, that same behaviour deleted the firewall's management interface on
  *every* push, and it survived only because vrnetlab restored it as root before the
  `commit confirmed` had to be confirmed, visible as a `root via other` commit wedged between
  the two `admin` commits.
  **The consequence is that the model is now authoritative for the firewall's management
  address**, and its values came from an `init.conf` vrnetlab generates inside the container
  that no repository holds. If they drift from what vrnetlab assigns, a push sets the wrong
  address and nothing restores it -- recovery is the container console.
  `tests/unit/test_junos_config.py::FXP0_FROM_INIT_CONF` is the only thing asserting they still
  agree, and it is hand-maintained. `SecurityZone` on a firewall interface became optional in
  `schemas/security/security.yml` to allow this: a deliberate change to the upstream contract,
  because a management interface is in no zone.
- **`frr-reload.py --test` returns `0` whether or not the configuration matches**, and its
  output is `Lines To Add` / `Lines To Delete` sections rather than `+`/`-` prefixes. A parser
  written against diff prefixes reports "no differences" for a device that has genuinely
  changed.
- **An empty FRR artifact is an instruction to erase the router**, because the reload applies
  the difference between the running configuration and the file. Artifact generation is
  asynchronous and an unrendered artifact exists, reports `Ready`, and is empty — so a
  provision run at the wrong moment would wipe all six WAN routers and report success. EOS was
  already protected by `_assert_eos_lifeline` and Junos by the shape of `load replace`, which
  only touches hierarchies the file tags; FRR had nothing until `_assert_frr_lifeline`. It keys
  on `hostname`, which every FRR template emits, rather than on `router bgp` — a future FRR
  device running no BGP is plausible, and a guard that refuses a legitimate configuration is a
  worse failure than the one it prevents.
- **`scp -O` is load-bearing on the Junos path.** Without it the copy fails, `load replace` does
  nothing, and `show | compare` comes back empty — which reads exactly like "in sync."

State goes to `DeploymentState` (cycle 029). `last_confirmed_at` moves only when the device
reported no difference, never because a push was sent; `last_checked_at` moves every cycle so a
stale confirmation is distinguishable from a dead loop. The service never writes `suspend` or
`suspend_reason` — those are the operator's break-glass.

## Development workflow

1. Prefer schema-first changes: add or update YAML under `schemas/` before code uses
   new nodes, attributes, relationships, or dropdown values.
2. Regenerate generated files rather than hand-editing them:
   - `src/solution_arista_avd/protocols.py` is generated.
   - `*_query.py` Pydantic models next to `.gql` files are generated.

   **`infrahubctl protocols` does not apply the `extensions:` block.** It renders
   `SecurityZone` with `name` and `interfaces` only — no `trust_level`, no `vrf`, none
   of the advertisement fields — even though all of those are loaded and queryable.
   Regenerating after an extension-only schema change therefore produces an empty diff, and
   **no extension-added field is reachable through the generated protocols**. Code that
   needs one reads it through a generated `*_query.py` model instead.
3. Implement generators, transforms, object data, menus, checks, or docs using the
   matching local Infrahub skills when a task touches those artifact types.
4. Keep generators idempotent: use upserts/natural keys, deterministic ordering,
   checksum comparisons, and repeated-run validation.
5. Keep GraphQL responses typed: update `.gql`, regenerate return types, and use the
   generated Pydantic models in production code.
6. Add or update unit tests for changed generator, transform, hostvars, role mapping,
   or utility behavior.
7. Run local unit/lint validation, integration tests and generator idempotence test as applicable.

## Running the AVD chain

`invoke load` seeds objects and runs **no generators**. A freshly loaded instance
therefore has no spine-to-leaf cabling, and PyAVD renders switches with no
uplinks and no underlay or overlay BGP — about 155 lines for a spine instead of
239 — while every artifact still reports `Ready`. Nothing errors. Use
`invoke avd --topology` once after a fresh load to build the fabric.

Thereafter use `invoke avd`, which runs only the two idempotent stages:

| Stage | Idempotent | When |
| --- | --- | --- |
| `generate-fabric`, `generate-pod`, `generate-rack` | **No — destructive on re-run** | `--topology`, build time only |
| `generate-avd-device-hostvar`, `generate-avd-device-structured-config` | Yes | every run |

The topology generators must not be re-run against a fabric that already has
cabling. `generate-pod` takes each spine from nine interfaces to four, deleting
the leaf-role ports racks 1 and 2 are cabled to, and `generate-rack` then fails
on rack 3 with an `IndexError` because its slice of spine ports is empty. That
is why they are behind a flag rather than in the default path.

**Use `--branch` for anything you intend to review.** The chain writes a great
deal of derived data, and doing that straight onto `main` leaves nowhere to see
what changed first. Artifact regeneration passes the branch through to
`POST /api/artifact/generate/{id}`; omit it and the endpoint regenerates against
`main`, which produces the confusing result that
`infrahubctl transform --branch X` renders your change while the stored artifact
never moves.

## Bootstrapping the whole environment

```bash
uv run invoke bootstrap            # everything, in one command
uv run invoke bootstrap --fresh    # ... destroying the stack and the lab first
```

That runs `start` → `load` → `avd` (on a branch, then merged) → `lab` →
`reconcile --converge` → `cluster`. Each step is still available on its own;
`bootstrap` only removes the need to remember the order and the flags.

**The device step is the reconciler, not `invoke provision`.** Cycle 030 swapped
it so the bootstrap exercises the same code path that keeps the fabric correct
afterwards, which also means `scripts/verify_bootstrap.sh` validates that path
rather than a second one. `invoke provision` remains as the manual command and
is unchanged.

`--converge` rather than a single cycle, because of a semantic that matters: a
cold device differs, so the first cycle **pushes** it — and `last_confirmed_at`
deliberately does not move on a push. Confirmation needs a later comparison that
finds no difference, so one cycle would leave a freshly built fabric correct but
unconfirmed. Converge also compares the firewall on every cycle rather than one
in four; the cadence is a steady-state economy and during a build nobody else is
using the box.

**The AVD chain runs on a branch and `--merge` merges it, rather than you
running `infrahubctl branch merge` by hand.** That is not ceremony. The topology
generators write a great deal of derived data, and running them onto `main`
leaves nowhere to see what changed — and no way back if they damage a fabric
that already has cabling. The merge then **waits for the artifacts to render**,
because generation is asynchronous: the REST endpoint returns 200 and the
rendering happens afterwards. Without that wait `provision` can read an artifact
that exists, reports `Ready`, and is empty — and push nothing onto a switch.

**That wait requires the artifacts to be non-empty AND stable over a window**, and both
halves were added after being measured, in that order:

- An artifact still holding its *pre-merge* content is populated, so a merge that REMOVED
  something returned from the wait immediately. A reconcile cycle run straight afterwards
  compared every device against stale output, printed `compared=14 differed=0`, and left the
  deleted interface on both leaves. Nothing errored, and the next cycle ten minutes later
  cleaned it up — so the only symptom was a deletion that appeared not to take.
- Requiring two consecutive agreeing checksum samples **did not fix it**, because the two
  samples agreed on the *old* checksums: the post-merge render had not begun ten seconds after
  the merge, so the wait settled on exactly the stale values it was meant to exclude. Same
  `differed=0`, same interface left behind.

`_wait_for_artifacts` therefore asserts stability over `STABLE_SAMPLES` samples rather than one,
and any movement resets the count. That is an empirical floor, not a guarantee, which is why the
timeout path says what it could not establish rather than claiming success. Waiting instead for
every checksum to **move** would be exact and would never terminate — an artifact whose content
genuinely did not change never moves, which is most of them on most merges.

`invoke avd --branch X --merge` does the same thing outside a bootstrap.

### Verifying a bootstrap

```bash
scripts/verify_bootstrap.sh          # ~20 minutes, destroys and rebuilds everything
```

Tears the environment down, rebuilds it with `invoke bootstrap --fresh`, and
asserts sixteen things about the result. Use it after changing anything in the
bootstrap path; "it worked" and "it is stable" are different claims, and only a
full teardown distinguishes them.

Several checks are deliberately about **state rather than exit status**, because
every bug this found was quiet:

- It counts **established BGP sessions**, not artifact size. An AVD artifact can
  be 239 lines, contain `router bgp`, report `Ready`, and describe a fabric that
  does not exist — which is exactly what a half-run topology chain produces.
- It **downloads** every configuration artifact. Generation is asynchronous, and
  an empty artifact still reports `Ready`.
- It checks the **delivered resources**, not `syncState`. A sync over an empty
  set is still `Succeeded`.

Six runs of it found the tolerated-502, the topology double-run and the CoreDNS
race, none of which failed in a way that pointed at its cause.

**Two more races live in `invoke cluster`, and both are timing-dependent rather
than deterministic.** Seen on a cycle-030 rebuild, one after the other:

- **Vidra can beat the lab's installer to a resource.** Vidra goes up before
  Crossplane, so once the XRDs land its next retry may create
  `fabricpeering/nfd41` in the window between the lab installer's
  `kubectl apply` reading the resource and creating it. Apply then fails
  `AlreadyExists` — from `apply`, not `create` — and the script `die`s, leaving
  the lab's two FabricApps unapplied and the handover unrun. Re-running
  `invoke cluster` clears it, because by then `apply` finds the resource and
  updates instead.
- **The lab's Crossplane installer preflights in-cluster networking itself.**
  `invoke cluster` already waits for the CoreDNS rollout, but
  `install-crossplane.sh` separately runs a busybox pod checking API ClusterIP,
  external DNS and egress. A Cilium that is up but still settling fails it. The
  same preflight run by hand a few minutes later passes, so the failure says
  "too early," not "broken."

Neither is caused by the device step, whichever command runs it: both parties to
each race are inside `invoke cluster`, which starts only after the devices are
done.

**Compose commands are pinned to the real project directory.** `docker compose`
derives its project name from the working directory, so from a git worktree
`invoke destroy` used to address a project that does not exist and silently do
nothing, while `invoke start` raised a second stack fighting for port 8000.
`compose_root()` resolves the main checkout through
`git rev-parse --git-common-dir`, which also matters because
docker-compose.override.yml mounts `./:/upstream` and Infrahub clones that path
over git — a worktree's `.git` is a file pointing into the main repository, so a
clone of it fails outright.

## Bringing the lab up from Infrahub

Two tasks, in order. The topology belongs to the sibling NFD41 lab repository;
the configuration belongs here.

```bash
uv run invoke lab          # deploy ../lab/nfd41.clab.yml, wait for eAPI
uv run invoke provision    # push every rendered artifact onto the devices
```

`invoke lab` deploys the lab repository's committed topology **as-is**. Nothing
renders a topology from Infrahub. The fabric comes up unconfigured on purpose:
the cEOS nodes are given no `startup-config`, only `CLAB_MGMT_VRF` and a
management address, so they boot reachable and empty. `../lab` is resolved by
walking up from this checkout, because a plain `../lab` is wrong from a git
worktree; set `NFD41_LAB_DIR` to override.

`invoke provision` then makes each device match its artifact. Three families,
three routes in, because the lab gives them three different front doors:

| Kind | Artifact | Route | Mechanism |
| --- | --- | --- | --- |
| `DcimFabricSwitch` | AVD EOS Configuration | `mgmt_ip`, eAPI | config session + `rollback clean-config` |
| `DcimDevice` | FRR Configuration | container name | `frr-reload.py --reload` |
| `SecurityFirewall` | Junos Configuration | container name | `load replace` + `commit confirmed` |

**The switches are reached by address and the rest by name, deliberately.**
Infrahub calls a switch `leaf-nfd41-pod1-1-1` and ContainerLab calls the same box
`k8s-leaf1`; there is no renaming layer, so names cannot match them. Their
`mgmt_ip` does equal the lab's management address, so eAPI needs no name. The FRR
routers and the firewall have no address modelled at all, but their Infrahub
names *are* their ContainerLab node names.

Every push is a replace, not a merge, so deleting something from the model
deletes it from the device. Three things are worth knowing before changing
`scripts/provision_lab.py`:

- **The EOS artifact ends with `end`.** Left in place it returns the CLI to
  enable mode and the commit that follows is rejected as an invalid command, so
  the session is abandoned and the switch silently keeps its old configuration.
  `_eos_config_lines` strips it and appends its own.
- **The firewall must use `load replace` with `replace:` tags.** `load override`
  and `load update` were both measured against the running vSRX and both delete
  the `system` stanza -- including `services { ssh; netconf; }`, the management
  path this script arrives on. The artifact has no `system` stanza because those
  are credential hashes that are never modelled. `_assert_junos_scope` fails
  loudly if one ever appears, rather than letting the push start overwriting
  credentials.
- **Junos re-serialises `## SECRET-DATA` with a fresh salt on any load**, so a
  diff showing the password hashes changing is Junos, not a credential rewrite.
  Re-loading the device's own unmodified configuration produces the same diff.

## The Kubernetes half, and who owns which resource

```bash
uv run invoke cluster      # Cilium, then Vidra, then Crossplane, then the handover
uv run invoke vidra        # the operator on its own, for a re-install
```

`invoke cluster` runs the **lab repository's** installers for the CNI and
Crossplane rather than reimplementing them — those are the lab's, the same way
the topology is. Cilium has to be first and cannot be managed by Crossplane: it
*is* the pod network, so a controller needing a pod network cannot be what
creates one. The k3s nodes sit `NotReady` until it lands; that is expected, not
a fault.

**Vidra goes up second, before the platform it delivers into.** Its syncs fail
while the XRDs are absent and retry every `requeueSyncAfter`, so the ordering
costs nothing — and it buys the thing that matters: the resources Infrahub
models are created by Vidra first-hand rather than adopted from another writer.
Three measured behaviours are why that is worth arranging:

- **It refuses to adopt a resource it did not create** (`already exists but is
  not managed by this operator`), so whichever writer gets there first keeps it.
- **A resource deleted after a successful sync stays missing for up to
  `requeueResourcesAfter` — ten minutes — while the sync reports `Succeeded`
  throughout.** An unchanged checksum skips the download and the apply, so the
  sync never notices the resource is gone. Verified by deleting a delivered
  `FabricPeering` and its CRD: both the sync and the `VidraResource` read
  `Succeeded` for two minutes with nothing in the cluster.
- **Deleting the `VidraResource` does not cause redelivery at all.** The sync
  still considers itself current, and there is no longer a resource to
  reconcile, so it wedges silently. Recovery is to delete and re-apply the
  `InfrahubSync`, which resets its checksum state — the peering came back
  within 15 seconds of doing so.
- **You cannot delete a resource Vidra owns; it puts it back.** That is drift
  correction working as intended, but it means cleanup has to delete the
  `InfrahubSync` first. Deleting the claim while the sync is live restores it
  mid-teardown, and the new composed resources then collide with a namespace
  still `Terminating` — which leaves two composed `Namespace` objects and a
  `FabricApp` stuck `Ready=False`.

**The handover is the remaining seam.** The lab's bootstrap applies
`crossplane/platform/10-peering.yaml` and `crossplane/apps/10-demo.yaml`, which
declare the same two resources Infrahub models, and its script has no flag to
skip them. `invoke cluster` deletes those two afterwards — and then **deletes
and re-applies `vidra/infrahub-syncs.yaml`**, which is not optional. Deleting a
delivered resource does not move the artifact's checksum, so the next sync skips
the apply, reports `Succeeded`, and leaves the cluster without it. Recreating the
sync resets its checksum state and delivery follows in seconds. This was
measured twice: first by deleting a resource by hand, then by `invoke cluster`
itself walking into it before the reset was added.

The wait afterwards checks **the resources**, not `syncState`, for the same
reason — a wait on the sync state returns happily from a cluster where nothing
was delivered:

| Resource | Owner |
| --- | --- |
| `fabricpeering.nfd41.lab/nfd41` | **Infrahub**, via `ServiceFabricPeering` |
| `fabricapp.nfd41.lab/nfd41-demo` | **Infrahub**, via `ServiceFabricApp` |
| `fabricapp.nfd41.lab/nfd41-observability` | the lab repository |
| `fabricapp.nfd41.lab/nfd41-access` | the lab repository |

The lab's two are safe because the operator only ever deletes a resource that
leaves a manifest **it delivered**. Pass `--no-handover` to keep the lab in
charge of all four; Vidra will then never adopt them.

`scripts/install_vidra.sh` follows the order the
operator requires: namespace, ConfigMap, Secret and the CRD shim **before** the
chart, because `InitConfigWithClient` reads the configuration once at startup.
Install the chart first and the operator keeps `queryName: ArtifactIDs`, which
this repository does not register, and every sync returns
`query failed with status 404 Not Found`.

Three failure modes worth knowing before debugging a merge that does not arrive:

- **`syncState: Succeeded` is not evidence anything arrived.** The sync compares
  a checksum, and an `artefactName` that does not match `.infrahub.yml` exactly
  returns an empty set — which succeeds. Check the `VidraResource` count, which
  is what `invoke vidra` prints alongside the sync state.
- **The Secret's label is the bare host**, no scheme and no port, because a colon
  is not legal in a label value. `http://172.20.41.1:8000` becomes
  `172.20.41.1`. Get it wrong and the operator reports `no secret found`, having
  looked straight past an otherwise perfect Secret.
- **Those are a username and password, not an API token.** The operator exchanges
  them at `POST /api/auth/login`; an `INFRAHUB_API_TOKEN`-shaped Secret does not
  authenticate.

See [docs/docs/developer-guide/vidra-delivery.md](docs/docs/developer-guide/vidra-delivery.md)
for the full loop and its diagnostics.

## Naming conventions

- Generators: `generate_<entity>.py`.
- Generator GraphQL queries: matching `.gql` files.
- Generated query models: `*_query.py`; regenerate them from `.gql` files rather
  than hand-editing.
- Node namespaces commonly used here: `Network.*`, `Location.*`,
  `Organization.*`, `Ipam.*`, `Dcim.*`, `Avd.*`, `Routing.*`, `Evpn.*`,
  `Interface.*`, `Compute.*`.

## Extension checklist

When adding an **AVD-rendered fabric** device role:

1. Add the role value to the **`DcimFabricSwitch`** dropdown in
   `schemas/dcim_extensions.yml`. That list must stay equal to `ROLE_TO_AVD_TYPE`;
   `tests/unit/test_dcim_schema_contract.py` asserts it.
2. Load/check schema and regenerate generated files.
3. Update `ROLE_TO_AVD_TYPE` in `src/solution_arista_avd/avd.py`.
4. Update `generators/generate_avd_device_hostvar.py` for role-specific fields.
5. Update whichever upstream generator creates devices of that role and group membership.
6. Add tests, especially `tests/unit/test_avd.py` and hostvars tests when needed.
7. Update `docs/docs/developer-guide/avd/role-mapping.md` and hostvars docs.

When adding a **non-EOS** device role, steps 3 to 5 and 7 do not apply, and the role
goes on **`DcimDevice`'s** dropdown rather than `DcimFabricSwitch`'s — cycle 027 split
the one dropdown into two, so "add the role value in `schemas/dcim_extensions.yml`"
now requires choosing which kind. The role values `isp_edge`, `isp_core`,
`internet_edge`, `customer_edge`, `branch_router` and `k8s_node` describe equipment
pyAVD never renders, and they are deliberately absent from `ROLE_TO_AVD_TYPE` (there is
no `firewall` value at all: a firewall is a `SecurityFirewall`):

- `get_avd_type` raises `ValueError` for an unmapped role. That loud failure is the
  wanted behaviour here; mapping one would instead let a firewall or an FRR router be
  rendered as an EOS switch, which fails silently.
- Devices with these roles must never join the `avd_devices` group, which is the only
  path into the AVD hostvar generator. Membership is set in one place,
  `src/solution_arista_avd/generator.py`, on the device-creation path the fabric and
  rack generators run from device designs — so a manually loaded device stays out.
- Add the role to `NON_AVD_DEVICE_ROLES` in `tests/unit/test_avd.py`, which keeps
  `test_schema_roles_all_mapped` guarding the fabric roles while excluding these, and
  update `docs/docs/developer-guide/schemas.md` instead of the AVD role-mapping doc.

When adding a transform output:

1. Add the `.gql` query under `transforms/`.
2. Regenerate the matching `*_query.py`; do not hand-write it.
3. Implement the transform class in `transforms/`.
4. Register the query, transform, and artifact definition in `.infrahub.yml`.
5. Add unit tests and integration coverage when appropriate.

When adding a hostvars field:

1. Add schema if the source data is not already represented.
2. Reload/check schema and regenerate protocols / GraphQL schema / return types.
   Use `graphql export-schema --destination schema.graphql` with the current CLI.
3. Update `generators/avd_device_hostvar.gql`.
4. Map the field in `generators/generate_avd_device_hostvar.py`.
5. Confirm the field is accepted by the pinned PyAVD version.
6. Add tests and update `docs/docs/developer-guide/avd/hostvars.md`.

## Commands agents may use

Install and discovery:

```bash
uv sync --all-packages
uv run invoke --list
```

Invoke tasks:

```bash
uv run invoke build
uv run invoke start
uv run invoke stop
uv run invoke destroy
uv run invoke restart
uv run invoke restart --component=infrahub-server
uv run invoke restart --component=service-catalog
uv run invoke load
uv run invoke load-schema
uv run invoke load-menu
uv run invoke avd                       # regenerate AVD hostvars, structured configs and artifacts
uv run invoke avd --branch my-change    # ... on a branch, so the result can be reviewed
uv run invoke avd --topology            # BUILD-TIME ONLY: also build the fabric and its cabling
uv run invoke avd --branch b --merge    # ... on a branch, merged when it succeeds
uv run invoke bootstrap                 # the whole environment, one command
uv run invoke bootstrap --fresh         # ... destroying the stack and the lab first
scripts/verify_bootstrap.sh             # rebuild from nothing and assert the result
uv run invoke lab                       # deploy ../lab's topology with management connectivity
uv run invoke lab --destroy             # tear it down
uv run invoke provision                 # push every rendered artifact onto the running devices
uv run invoke provision --dry-run       # ... showing what would be pushed, changing nothing
uv run invoke provision --kind eos      # ... one family only: eos, frr, or junos
uv run invoke reconcile --converge      # cycle until every device is confirmed (the bootstrap path)
uv run invoke reconcile --once          # a single reconcile cycle
uv run invoke reconcile --dry-run --branch X  # report differences, change nothing
uv run invoke reconcile                 # the loop, 600s default, 60s floor
uv run invoke cluster                   # Cilium, Vidra, Crossplane, then the handover
uv run invoke cluster --no-handover     # ... leaving the lab in charge of all four
uv run invoke vidra                     # the operator on its own, for a re-install
uv run invoke init-semaphore
uv run invoke test
uv run invoke lint
uv run invoke lint-ruff
uv run invoke lint-yaml
uv run invoke lint-mypy
uv run invoke lint-markdown
uv run invoke lint-prose
uv run invoke format
uv run invoke docs
```

Local tests and linters:

```bash
uv run pytest tests/unit
uv run pytest tests/unit/test_avd.py
uv run pytest tests/unit/test_hostvar_ordering.py
uv run ruff check .
uv run ruff format --check .
uv run ruff format .
uv run mypy --show-error-codes src/solution_arista_avd
uv run yamllint .
uv run rumdl check README.md AGENTS.md docs/ lab/README.md schemas/
uv run rumdl fmt README.md AGENTS.md docs/ lab/README.md schemas/
```

Markdown linting covers authored files only; vendored agent content, `specs/`, and
PyAVD-rendered output under `lab/avd/` are excluded in `[tool.rumdl]`.

Prose linting uses Vale, which is a Go binary rather than a `uv` dependency. Install the
pinned version before running `invoke lint-prose`:

```bash
curl -sL "https://github.com/errata-ai/vale/releases/download/v3.17.1/vale_3.17.1_Linux_64-bit.tar.gz" \
  -o /tmp/vale.tar.gz && tar -xzf /tmp/vale.tar.gz -C ~/.local/bin vale
vale sync
```

Use local `uv run pytest tests/integration` only for ad-hoc local/lab debugging when explicitly
appropriate.

`infrahubctl` examples:

```bash
uv run infrahubctl branch list
uv run infrahubctl branch create <branch-name>
uv run infrahubctl schema check schemas/ --branch <branch-name>
uv run infrahubctl schema load schemas --branch <branch-name>
uv run infrahubctl menu load menus/ --branch <branch-name>
uv run infrahubctl object load objects/ --branch <branch-name>
uv run infrahubctl object load repository.yml --branch <branch-name>
uv run infrahubctl object load triggers.yml --branch <branch-name>
uv run infrahubctl graphql export-schema --destination schema.graphql
uv run infrahubctl graphql generate-return-types generators/avd_device_hostvar.gql
uv run infrahubctl graphql generate-return-types transforms/<query>.gql
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
```

For repeated `infrahubctl` calls, define a temporary shell alias in the current session only:

```bash
alias ihctl='uv run infrahubctl'
```

The documentation site uses pnpm, not npm. Prefer `uv run invoke docs`, which runs the same
commands CI runs. To work inside `docs/` directly:

```bash
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
```

pnpm settings for the site live in `docs/pnpm-workspace.yaml`, not in `docs/package.json` -
pnpm no longer reads the `pnpm` field there, so overrides placed in it are ignored.

## Documentation publishing

`docs/docs/` is synced to `opsmill/infrahub-docs` by `.github/workflows/sync-docs.yml` on
every push to `main`, and published at `docs.infrahub.app/arista-avd`. That site mounts this
content under a `/arista-avd` route rather than at the site root, so two rules apply to
anything added under `docs/docs/`:

- Link between pages with relative Markdown paths (`](./quick-start.md)`,
  `](../troubleshooting.md)`), never root-absolute ones (`](/quick-start)`). Absolute paths
  resolve locally because `routeBasePath` is `/` here, but on the aggregation site they point
  at core Infrahub pages and fail its build, which sets `onBrokenLinks: 'throw'`.
- Keep the sidebar key in `docs/sidebars.ts` named `aristaAvdSidebar`. The aggregation site's
  navbar references it by name, and sidebar keys must be unique across that site.

Edits made directly in `infrahub-docs` are overwritten by the next sync.
